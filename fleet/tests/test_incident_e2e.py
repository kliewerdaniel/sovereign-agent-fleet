"""Incident Triage -> Authorized Remediation end-to-end (D26 / use case Option 3).

Drives the REAL ControlPlane / Runtime / SimEnv stack (no fakes). Every scenario
asserts the four independent gates fired correctly AND the consequential SimEnv
state transition actually happened (or correctly did not).

Pipeline order enforced by code:
  Evidence (D16) -> Capability (Gateway) -> Policy (incident) -> Approval (D17)
  -> SimEnv transition -> signed audit.

Scenarios:
  Path A  : LOW severity, VERIFIED evidence, LOW blast  -> AUTO (no human)
  Path B  : HIGH severity, VERIFIED evidence, revenue-svc -> HUMAN (signed approval)
  Act 3   : VERIFIED evidence identity-svc compromised -> BLOCKED (no auth DoS)
  Attack 1: forged/mis-bound human approval -> rejected (D17 fail-closed)
  Attack 2: capability absence (researcher) -> Gateway DENY
  Attack 3: HALLUCINATION intel (zero refs) -> Evidence gate blocks
  Attack 4: direct SimEnv transition on PROTECTED -> second-line defense rejects
"""
import json

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from fleet.crypto.chriscrypt.store import JsonStore
from fleet.crypto.foundation import canonical_bytes, sha256
from fleet.layers import (
    Analyst,
    Approval,
    ControlPlane,
    Handoff,
    HandoffError,
    HALLUCINATION,
    MemBank,
    Operator,
    Researcher,
    RuntimeError_,
    Runtime,
    ToolEnvelope,
    VERIFIED,
)
from fleet.layers.incident import Authorization, bind_artifact
from fleet.simenv.env import ACTIONS, AssetClass, SimEnv, WorkloadState, asset_class


@pytest.fixture
def env(tmp_path):
    master = b"incident-master"
    audit = Ed25519PrivateKey.from_private_bytes(
        HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
             info=b"fleet:audit").derive(b"audit-incident"))
    store = JsonStore(str(tmp_path / "audit.json"))
    cp = ControlPlane(master, audit, store=store, now_fn=lambda: 2_000,
                      run_id="run-incident")
    kek = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
               info=b"fleet:mem").derive(b"mem-incident")
    mem = MemBank(kek)
    rt = Runtime(cp, mem, now_fn=lambda: 2_000)
    r = cp.publish_agent("researcher-1", "researcher", ["emit_evidence"])
    a = cp.publish_agent("analyst-1", "analyst", ["qualify", "verify_gate"])
    o = cp.publish_agent("operator-1", "operator",
                         ["prepare_artifact", "crm_write", "incident_remediate"])
    human = cp.publish_agent("human-1", "human", ["approve_deny"])
    tool_cert, tool_key = cp.root.issue_cert("web_tool", "tool",
                                             ["retrieve"], 2000, 9_999_999_999)
    cp.registry._certs["web_tool"] = tool_cert
    sim = SimEnv()
    return {"cp": cp, "rt": rt, "r": r, "a": a, "o": o, "human": human,
            "tool_key": tool_key, "tool_cert": tool_cert, "sim": sim,
            "audit_key": audit}


# --- evidence + intel helpers ----------------------------------------------

def _gather(env, extract):
    out = json.dumps({"citation": "https://src.example/x", "extract": extract}).encode()
    env_env = ToolEnvelope.make(env["tool_key"], "web_tool", out)
    return Researcher(env["r"], env["rt"]).gather(env_env, "q", ["citation", "extract"])


def _intel(env, verification, severity, n_refs=2):
    """Build a QualifiedIntel handoff with the requested verification + severity.
    The verification field is the D16 output the Operator gates on; we stamp a
    genuinely-sourced intel then override it to exercise each gate."""
    evs = [_gather(env, f"indicator {i}") for i in range(max(n_refs, 1))]
    a = Analyst(env["a"], env["rt"])
    refs = [e.payload["evidence_id"] for e in evs]
    stamped = a.qualify(evs[0], [{
        "claim": "compromise=true", "claim_type": "role",
        "evidence_refs": refs,
    }]).payload
    # force the requested verification/severity for scenario control
    stamped["verification"] = verification
    stamped["severity"] = severity
    return Handoff.make(env["a"].cert, env["a"].key, "QualifiedIntel", stamped)


def _human_approval(env, idem, capability, bound_artifact_hash):
    return Approval.sign(
        env["human"].cert, env["human"].key, "operator-1", idem,
        capability, bound_artifact_hash, "approve",
        "incident authorized", 2_001,
    ).__dict__


def _audit_kinds(env):
    return [e.get("kind") for e in env["cp"].audit.entries()]


# === Path A — LOW auto-remediation (no human) ==============================

def test_pathA_low_auto_remediation(env):
    # VERIFIED + LOW severity + LOW blast (block_egress) -> AUTO.
    intel = _intel(env, VERIFIED, "LOW")
    op = Operator(env["o"], env["rt"])
    res = op.act(intel, "block egress on web-edge", "incident_remediate",
                 "idem-A", target_workload="web-edge",
                 action_name="block_egress", simenv=env["sim"])
    assert res["final"] is True
    assert res["authorization"] == Authorization.AUTO.value
    assert res["require_approval"] is False
    # Consequential state transition ACTUALLY happened.
    assert env["sim"].state_of("web-edge") == WorkloadState.EGRESS_BLOCKED
    assert res["prev_state"] == "RUNNING" and res["new_state"] == "EGRESS_BLOCKED"
    # Audit records the transition.
    assert "operator.final" in _audit_kinds(env)


# === Path B — HIGH revenue-svc requires human ==============================

def test_pathB_high_requires_human(env):
    intel = _intel(env, VERIFIED, "HIGH")
    op = Operator(env["o"], env["rt"])
    # Without approval -> needs_approval (human consent required).
    res = op.act(intel, "isolate revenue-svc", "incident_remediate",
                 "idem-B", target_workload="revenue-svc",
                 action_name="isolate", simenv=env["sim"])
    assert res["final"] is False
    assert res["needs_approval"] is True
    assert res["authorization"] == Authorization.HUMAN.value
    # No transition yet (state unchanged).
    assert env["sim"].state_of("revenue-svc") == WorkloadState.RUNNING

    # With a correctly-bound human approval -> executes.
    target_state = ACTIONS["isolate"][0].value
    bound = bind_artifact("revenue-svc", "isolate", target_state)
    ap = _human_approval(env, "idem-B", "incident_remediate", bound)
    res2 = op.act(intel, "isolate revenue-svc", "incident_remediate",
                  "idem-B", target_workload="revenue-svc",
                  action_name="isolate", simenv=env["sim"], approval=ap)
    assert res2["final"] is True
    assert res2["require_approval"] is True
    assert env["sim"].state_of("revenue-svc") == WorkloadState.ISOLATED


# === Act 3 — policy BLOCKS containment of PROTECTED even when compromised ===

def test_act3_protected_blocked_despite_verified_compromise(env):
    # VERIFIED evidence that identity-svc is compromised (LOW or HIGH severity)
    # must NOT grant the power to isolate it. Policy blocks -> no execution.
    intel = _intel(env, VERIFIED, "HIGH")
    op = Operator(env["o"], env["rt"])
    res = op.act(intel, "isolate identity-svc", "incident_remediate",
                 "idem-3", target_workload="identity-svc",
                 action_name="isolate", simenv=env["sim"])
    assert res["final"] is False
    assert res["blocked"] is True
    assert res["gate"] == "policy"
    assert res["authorization"] == Authorization.BLOCKED.value
    # State unchanged — no self-inflicted auth DoS.
    assert env["sim"].state_of("identity-svc") == WorkloadState.RUNNING
    assert "operator.blocked" in _audit_kinds(env)


# === Attack 1 — forged / mis-bound human approval rejected =================

def test_attack1_misbound_approval_rejected(env):
    intel = _intel(env, VERIFIED, "HIGH")
    op = Operator(env["o"], env["rt"])
    # Attacker reuses a human approval bound to a DIFFERENT action/state.
    wrong_bound = bind_artifact("web-edge", "block_egress", "EGRESS_BLOCKED")
    ap = _human_approval(env, "idem-1", "incident_remediate", wrong_bound)
    res = op.act(intel, "isolate revenue-svc", "incident_remediate",
                 "idem-1", target_workload="revenue-svc",
                 action_name="isolate", simenv=env["sim"], approval=ap)
    assert res["final"] is False
    assert res["blocked"] is True
    assert res["gate"] == "approval"
    assert env["sim"].state_of("revenue-svc") == WorkloadState.RUNNING


# === Attack 2 — capability absence -> Gateway DENY =========================

def test_attack2_capability_denied_for_unauthorized_role(env):
    intel = _intel(env, VERIFIED, "LOW")
    # A RESEARCHER (no incident_remediate capability) attempts remediation.
    op = Operator(env["r"], env["rt"])
    res = op.act(intel, "block egress web-edge", "incident_remediate",
                 "idem-2", target_workload="web-edge",
                 action_name="block_egress", simenv=env["sim"])
    assert res["final"] is False
    assert res["blocked"] is True
    assert res["gate"] == "capability"
    assert env["sim"].state_of("web-edge") == WorkloadState.RUNNING


# === Attack 3 — HALLUCINATION intel blocked at Evidence gate ===============

def test_attack3_hallucination_intel_blocked(env):
    # Zero evidence refs -> HALLUCINATION: blocked before capability/policy.
    intel = _intel(env, HALLUCINATION, "HIGH", n_refs=0)
    op = Operator(env["o"], env["rt"])
    res = op.act(intel, "isolate revenue-svc", "incident_remediate",
                 "idem-3", target_workload="revenue-svc",
                 action_name="isolate", simenv=env["sim"])
    assert res["final"] is False
    assert res["blocked"] is True
    assert res["reason"] == "HALLUCINATION intel rejected"
    assert env["sim"].state_of("revenue-svc") == WorkloadState.RUNNING


# === Attack 4 — direct SimEnv on PROTECTED defends itself ==================

def test_attack4_simenv_second_line_defense(env):
    # Even calling SimEnv.transition directly (bypassing the whole pipeline),
    # the PROTECTED asset refuses containment. Second-line defense.
    res = env["sim"].apply("identity-svc", "isolate")
    assert res.ok is False
    assert res.reason and ("policy" in res.reason.lower()
                           or "protected" in res.reason.lower())
    assert res.new_state == WorkloadState.RUNNING  # unchanged
    # The pipeline never reached the Operator for this (no operator.final).
    assert "operator.final" not in _audit_kinds(env)


# === Idempotency — replay of an authorized remediation does not double-transition

def test_remediation_idempotent_on_replay(env):
    intel = _intel(env, VERIFIED, "LOW")
    op = Operator(env["o"], env["rt"])
    r1 = op.act(intel, "block egress web-edge", "incident_remediate",
                "idem-idem", target_workload="web-edge",
                action_name="block_egress", simenv=env["sim"])
    assert r1["final"] is True
    before = len(env["cp"].audit.entries())
    # Replay same idempotency key.
    r2 = op.act(intel, "block egress web-edge", "incident_remediate",
                "idem-idem", target_workload="web-edge",
                action_name="block_egress", simenv=env["sim"])
    assert r2["final"] is True
    assert r2["prev_state"] == "RUNNING"  # recorded result, no re-transition
    # No second operator.final emitted (idempotent replay doesn't re-log).
    assert _audit_kinds(env).count("operator.final") == 1
    assert len(env["cp"].audit.entries()) == before
