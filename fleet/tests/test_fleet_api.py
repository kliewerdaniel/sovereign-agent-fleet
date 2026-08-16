"""Tests for the fleet API layer (Phase 1).

Covers request/response shape for every read endpoint, SSE sanity, the
adversarial beat runner, and that write paths (decide / run) behave correctly
and never accept unsigned/invalid input.

The live API keeps a singleton control plane; tests that mutate shared state
(approvals) use their own fresh fixture where needed, but most checks are
read-only projections.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from fleet.api import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# --- health + shape -------------------------------------------------------
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_agents_shape(client):
    r = client.get("/agents")
    assert r.status_code == 200
    body = r.json()
    assert "root_public_pem" in body and "root_epoch" in body
    assert {a["agent_id"] for a in body["agents"]} >= {
        "researcher", "analyst", "operator", "human-approver"
    }
    for a in body["agents"]:
        assert set(a) >= {"agent_id", "role", "capabilities", "cert_seq", "status"}


def test_ledger_pagination(client):
    # seed a couple of runs so the ledger has entries + a working cursor
    client.post("/run/incident", json={"verification": "VERIFIED", "severity": "LOW"})
    r = client.get("/ledger?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert "entries" in body and "head" in body and "chain_valid" in body
    assert body["chain_valid"] is True
    # every entry is well-formed
    for e in body["entries"]:
        assert set(e) >= {"id", "seq", "prev", "ts", "kind", "payload", "sig"}
    # cursor fetch returns a subset after the cursor
    if body["entries"]:
        last = body["entries"][-1]["id"]
        r2 = client.get(f"/ledger?since={last}&limit=5")
        assert r2.status_code == 200
        assert all(e["id"] > last for e in r2.json()["entries"])


def test_chain_integrity(client):
    r = client.get("/chain/integrity")
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["audit_pubkey_pem"].startswith("-----BEGIN")


def test_ledger_stream_emits(client):
    # Verify the SSE generator emits a real audit.append event after a run,
    # WITHOUT blocking on a live stream (bounded generator drain).
    import asyncio

    async def drain():
        from fleet.api.app import ledger_stream_gen

        it = ledger_stream_gen()
        # consume the opening SSE comment so the poll loop starts cleanly
        await it.__anext__()
        # trigger a run so the tail advances during the 1s poll window
        client.post("/run/incident", json={"verification": "VERIFIED", "severity": "LOW"})

        async def first_event():
            async for chunk in it:
                text = chunk.decode() if isinstance(chunk, bytes) else chunk
                for line in text.splitlines():
                    if line.startswith("data:"):
                        return line
            return None

        return await asyncio.wait_for(first_event(), timeout=8.0)

    got = asyncio.run(drain())
    assert got is not None and got.startswith("data:")
    payload = json.loads(got[len("data: "):])
    assert payload["event"] == "audit.append"
    assert "entry" in payload and "sig" in payload["entry"]


# --- policy / verification / pending --------------------------------------
def test_policy_log_shape(client):
    client.post("/run/incident", json={"verification": "ASSERTED", "severity": "MEDIUM"})
    r = client.get("/policy-log")
    assert r.status_code == 200
    for d in r.json()["decisions"]:
        assert set(d) >= {"seq", "agent_id", "capability", "decision"}
        assert d["decision"] in ("grant", "require_approval", "deny")


def test_verification_shape(client):
    r = client.get("/verification")
    assert r.status_code == 200
    for v in r.json()["artifacts"]:
        assert set(v) >= {"seq", "intel_id", "verification", "confidence"}
        assert v["verification"] in ("VERIFIED", "ASSERTED", "HALLUCINATION", "UNKNOWN")


def test_pending_approvals_after_asserted_run(client):
    # An ASSERTED run escalates to HUMAN -> produces a pending approval.
    res = client.post("/run/incident",
                      json={"verification": "ASSERTED", "severity": "MEDIUM",
                            "workload_id": "app-db", "action": "isolate"})
    assert res.status_code == 200
    assert res.json()["needs_approval"] is True
    action_id = res.json()["action_id"]
    pend = client.get("/approvals/pending").json()
    assert any(p["request_id"] == action_id for p in pend)


# --- write paths: reject invalid / unsigned -------------------------------
def test_decide_unknown_request_404(client):
    r = client.post("/approvals/nonexistent/decide",
                    json={"approve": True, "signer": "human-approver"})
    assert r.status_code == 404


def test_decide_requires_body(client):
    # FastAPI rejects a missing body (422), never silently signing.
    r = client.post("/approvals/some-id/decide")
    assert r.status_code == 422


def test_decide_approve_calls_real_d17_signing(client):
    res = client.post("/run/incident",
                      json={"verification": "ASSERTED", "severity": "HIGH",
                            "workload_id": "web-edge", "action": "block_egress"})
    action_id = res.json()["action_id"]
    r = client.post(f"/approvals/{action_id}/decide",
                    json={"approve": True, "signer": "human-approver"})
    assert r.status_code == 200
    body = r.json()
    # genuine human Ed25519 signature, bound to this action
    assert body["decision"] == "approve"
    assert body["action_id"] == action_id
    assert body["human_sig"] and len(body["human_sig"]) == 128
    assert body["human_id"] == "human-approver"
    # now it should no longer be pending
    pend = client.get("/approvals/pending").json()
    assert all(p["request_id"] != action_id for p in pend)


def test_decide_deny_records_rejection(client):
    res = client.post("/run/incident",
                      json={"verification": "ASSERTED", "severity": "LOW",
                            "workload_id": "web-edge", "action": "quarantine"})
    action_id = res.json()["action_id"]
    r = client.post(f"/approvals/{action_id}/decide",
                    json={"approve": False, "signer": "human-approver"})
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "reject"
    assert body["human_sig"] == ""  # deny does not emit a human signature


# --- adversarial beats ----------------------------------------------------
def test_demo_beats_list(client):
    r = client.get("/demo/beats")
    assert r.status_code == 200
    assert len(r.json()) == 8


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 6, 7, 8])
def test_each_beat_passes(client, n):
    r = client.post(f"/demo/beat/{n}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["beat"] == n
    assert body["passed"] is True, body["detail"]
    # every beat produced real signed ledger entries
    assert len(body["ledger_entries"]) >= 1
    for e in body["ledger_entries"]:
        assert e["sig"] and "seq" in e


def test_beat_out_of_range(client):
    r = client.post("/demo/beat/9")
    assert r.status_code == 400
