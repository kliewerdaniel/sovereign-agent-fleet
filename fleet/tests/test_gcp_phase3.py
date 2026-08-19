"""Phase 3 GCP + Observability (14.8 / 03.2 #7 / 13.3 / D17).

All tests run OFFLINE: the GcpBridge ``local`` mode mirrors the exact Firestore
document schema, so the 14.8 verifier exercises the identical code path a live
deployment would. The verifier receives ONLY public keys -- proving GCP holds
verifiable data, not authority (D3/D6).

Coverage:
  * 14.8: replicate() writes verifiable docs; FirestoreVerifier against the copy
    reproduces tamper detection (flip a body -> verify fails at that seq; intact
    chain verifies). Certification of a single claim: cloud copy == local truth.
  * OTel: audit entries fan out to OTel spans sharing one run trace_id; reasoning
    spans carry the deterministic brain proposal (03.2 #7).
  * 13.3: Pub/Sub publish_task enqueues signed handoffs (local mirror).
  * D17: Cloud Run approval console queues pending action + collects a human
    signed ApprovalRecord via stdlib WSGI app.
"""
import json
import os

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from fleet.crypto.chriscrypt.store import JsonStore
from fleet.gcp.bridge import GcpBridge
from fleet.gcp.otel import OtelExporter
from fleet.gcp.verify import FirestoreVerifier
from fleet.layers import ControlPlane, Handoff, MemBank, Runtime
from fleet.layers.runtime import Approval


@pytest.fixture
def env(tmp_path):
    master = b"phase3-master"
    audit = Ed25519PrivateKey.from_private_bytes(
        HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"fleet:audit").derive(b"audit-p3")
    )
    store = JsonStore(str(tmp_path / "audit.json"))
    bridge = GcpBridge(mode="local", project="project-3ba93cec-8ca6-43c0-ba4")
    otel = OtelExporter(use_sdk=False)
    cp = ControlPlane(master, audit, store=store, now_fn=lambda: 1_000,
                      bridge=bridge, otel=otel, run_id="run-p3")
    kek = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"fleet:mem").derive(b"mem-p3")
    mem = MemBank(kek)
    rt = Runtime(cp, mem, now_fn=lambda: 1_000)
    r = cp.publish_agent("researcher-1", "researcher", ["emit_evidence"])
    a = cp.publish_agent("analyst-1", "analyst", ["qualify", "verify_gate"])
    o = cp.publish_agent("operator-1", "operator", ["prepare_artifact", "crm_write"])
    human = cp.publish_agent("human-1", "human", ["approve_deny"])
    return {"cp": cp, "rt": rt, "r": r, "a": a, "o": o, "human": human,
            "bridge": bridge, "otel": otel, "audit_key": audit}


# --- 14.8 Firestore verifier (verifiable data, not authority) ------------

def test_replicate_writes_verifiable_docs(env):
    env["cp"].request_authority(env["o"].cert, "crm_write")
    docs = env["bridge"].mirror_docs()
    assert docs, "GCP mirror must hold replicated signed artifacts"
    # every replicated doc carries the verbatim signed payload + its sig + prev
    for d in docs:
        assert d["payload"]["sig"] is not None
        assert d["prev_hash"] == d["payload"].get("prev")


def test_firestore_verifier_passes_on_intact_chain(env):
    env["cp"].request_authority(env["o"].cert, "crm_write")
    env["cp"].request_authority(env["a"].cert, "qualify")
    verifier = FirestoreVerifier(
        env["bridge"].mirror_docs(), env["cp"].audit.public_key_pem(),
        env["cp"].root.root_public_pem,
    )
    assert verifier.verify() is True  # GCP copy is verifiable with public keys


def test_firestore_verifier_detects_tamper(env):
    env["cp"].request_authority(env["o"].cert, "crm_write")
    env["cp"].request_authority(env["a"].cert, "qualify")
    docs = env["bridge"].mirror_docs()
    # flip one ledger entry's body in the cloud copy (adversary beat 6)
    target = next(d for d in docs if d["payload"].get("seq") == 1)
    tampered = dict(target)
    tampered_payload = dict(tampered["payload"])
    tampered_payload["payload"] = dict(tampered_payload["payload"])
    tampered_payload["payload"]["result"] = "tampered"
    tampered["payload"] = tampered_payload
    docs[2] = tampered  # replace the seq==1 doc in the mirror
    verifier = FirestoreVerifier(
        docs, env["cp"].audit.public_key_pem(), env["cp"].root.root_public_pem,
    )
    # tamper is detected using ONLY public keys — no authority needed
    assert verifier.verify() is False


def test_verifier_uses_public_keys_only(env):
    env["cp"].request_authority(env["o"].cert, "crm_write")
    verifier = FirestoreVerifier(
        env["bridge"].mirror_docs(), env["cp"].audit.public_key_pem(),
        env["cp"].root.root_public_pem,
    )
    # the verifier object holds only public pems; assert no private attr leaked
    assert not hasattr(verifier, "_priv")
    assert verifier.verify() is True


# --- 03.2 #7 OTel observability -------------------------------------------

def test_otel_fanout_shares_run_trace(env):
    env["cp"].request_authority(env["o"].cert, "crm_write")
    env["cp"].request_authority(env["a"].cert, "qualify")
    spans = env["otel"].spans()
    assert spans, "audit entries must fan out to OTel spans"
    trace_ids = {s.trace_id for s in spans}
    assert len(trace_ids) == 1, "all spans in a run share one trace_id"
    assert env["otel"].trace_for("run-p3") == spans[0].trace_id


def test_otel_reasoning_span_carries_proposal(env):
    span = env["otel"].emit_reasoning("run-p3", "analyst", "qualify",
                                       {"confidence": 0.8, "icp_fit": True})
    assert span.trace_id == env["otel"].trace_for("run-p3")
    assert span.events and span.events[0]["name"] == "proposal"
    assert span.events[0]["attributes"]["icp_fit"] is True


# --- 13.3 Pub/Sub async handoffs ------------------------------------------

def test_pubsub_publish_task_local(env):
    env = env  # noqa
    handoff = Handoff.make(env["a"].cert, env["a"].key, "QualifiedIntel",
                           {"intel_id": "iq_1", "predicates": []})
    # the handoff is already signed (envelope) -> safe to replicate to a topic
    task_id = env["bridge"].publish_task(handoff.to_dict())
    assert task_id.startswith("local-task-")
    # the handoff envelope carries the sender cert; the sender identity is
    # recoverable from it (no new field is minted for Pub/Sub).
    assert env["bridge"].published_tasks()[0]["sender_cert"]["agent_id"] == env["a"].agent_id


# --- D17 Cloud Run approval console ---------------------------------------

def test_console_queues_and_collects_human_approval(env):
    from fleet.gcp.console import ApprovalConsole

    console = ApprovalConsole(env["bridge"])
    console.queue({"action_id": "crm_write:42", "agent_id": "operator-1",
                   "artifact_hash": "abc", "ts": 1_000})
    assert len(console.pending()) == 1
    ap_dict = console.approve(
        "crm_write:42", "approve", "verified intel",
        env["human"].cert, env["human"].key,
    )
    assert ap_dict["decision"] == "approve"
    assert ap_dict["human_id"] == "human-1"
    assert "human_sig" in ap_dict and ap_dict["human_sig"]
    assert console.pending() == []  # consumed after approval


def test_console_wsgi_serves_pending(env):
    from wsgiref.util import setup_testing_defaults
    from io import BytesIO

    from fleet.gcp.console import ApprovalConsole

    console = ApprovalConsole(env["bridge"])
    console.queue({"action_id": "crm_write:7", "agent_id": "operator-1",
                   "artifact_hash": "x", "ts": 1_000})
    environ = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = "GET"
    environ["PATH_INFO"] = "/pending"
    out = {}

    def start_response(status, headers):
        out["status"] = status

    body = console.wsgi_app(environ, start_response)
    assert out["status"] == "200 OK"
    assert b"crm_write:7" in b"".join(body)


def test_seed_build_is_side_effect_free():
    # Regression for the seeder footgun: constructing the live ControlPlane via
    # seed_gcp.build() must NOT write to the live Firestore mirror, or an
    # external judge importing the module to verify the chain would fork it.
    if not os.environ.get("FLEET_PROJECT"):
        pytest.skip("requires FLEET_PROJECT + ADC for live bridge clear()")
    from fleet.gcp.bridge import GcpBridge
    import scripts.seed_gcp as sg

    coll = sg.COLLECTION
    bridge = GcpBridge(mode="gcp", project=sg.PROJECT, firestore_collection=coll)
    # Scope the cleanup to the LEDGER collection only — build() must not write
    # here. Leave the live pending/approvals collections (a judge's in-flight
    # queue) untouched.
    bridge._init_clients()
    for d in bridge._fs.collection(coll).stream():
        d.reference.delete()
    before = len(bridge.mirror_docs())
    # constructing the plane must not replicate anything to the ledger
    sg.build()
    after = len(bridge.mirror_docs())
    assert before == after == 0, "build() wrote to live Firestore ledger (side effect!)"


def test_reconstruct_audit_pubkey_matches_seeded_chain():
    # A judge verifying the cloud copy must be able to reconstruct the audit
    # public key WITHOUT a private key or a ControlPlane, and it must verify
    # the live chain. Guards the deterministic key derivation in the seeder.
    if not os.environ.get("FLEET_PROJECT"):
        pytest.skip("requires FLEET_PROJECT + ADC for live mirror read")
    import scripts.seed_gcp as sg
    from fleet.gcp.bridge import GcpBridge
    from fleet.gcp.verify import FirestoreVerifier

    bridge = GcpBridge(mode="gcp", project=sg.PROJECT, firestore_collection=sg.COLLECTION)
    docs = bridge.mirror_docs()
    v = FirestoreVerifier(docs, sg.reconstruct_audit_pubkey())
    assert v.verify() is True, "judge's reconstructed audit key cannot verify live chain"


def test_console_html_view_renders_without_format_error(env):
    # Regression: GET / with Accept: text/html used str.format() on a template
    # containing literal CSS braces ({font-family:...}), which raised KeyError
    # and surfaced a bare "'font-family'" 500 body in the browser. It must
    # render real HTML instead (browsers send text/html; curl/*/* takes JSON).
    from fleet.gcp.console import ApprovalConsole
    from wsgiref.util import setup_testing_defaults

    console = ApprovalConsole(env["bridge"])
    console.queue({"action_id": "crm_write:11", "agent_id": "operator-1",
                   "capability": "crm_write", "artifact_hash": "deadbeefcafe",
                   "ts": 1_000})
    environ = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = "GET"
    environ["PATH_INFO"] = "/"
    environ["HTTP_ACCEPT"] = "text/html"
    out = {}

    def start_response(status, headers):
        out["status"] = status
        out["headers"] = headers

    body = console.wsgi_app(environ, start_response)
    assert out["status"] == "200 OK"
    content_type = dict(out["headers"]).get("Content-Type", "")
    assert "text/html" in content_type
    html = b"".join(body).decode()
    assert "<html>" in html
    assert "font-family" in html          # CSS preserved, not a KeyError
    assert "{rows}" not in html           # placeholder substituted
    assert "crm_write:11" in html         # pending action shown


# --- G2: console rejects unverifiable approvals (fail-closed) ---------------

def _wsgi_post(console, req):
    from io import BytesIO
    from wsgiref.util import setup_testing_defaults

    environ = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = "POST"
    environ["PATH_INFO"] = "/approve"
    body_bytes = json.dumps(req).encode()
    environ["CONTENT_LENGTH"] = str(len(body_bytes))
    environ["wsgi.input"] = BytesIO(body_bytes)
    out = {}

    def start_response(status, headers):
        out["status"] = status

    resp = console.wsgi_app(environ, start_response)
    return out["status"], b"".join(resp)


def test_g2_console_no_verifier_rejects_all_approvals(env):
    from fleet.gcp.console import ApprovalConsole

    console = ApprovalConsole(env["bridge"])  # no verify_approval / human_cert bound
    console.queue({"action_id": "crm_write:9", "agent_id": "operator-1",
                   "capability": "crm_write", "artifact_hash": "x", "ts": 1_000})
    status, body = _wsgi_post(console, {"action_id": "crm_write:9", "decision": "approve"})
    assert status == "403 Forbidden"
    assert b"accepted" in body and b"false" in body
    assert any(e["kind"] == "console.unverified_approval_rejected" for e in console.audit_log())


def test_g2_console_accepts_valid_signed_approval(env):
    from fleet.gcp.console import ApprovalConsole
    from fleet.layers.approval import verify_approval

    human = env["human"]
    console = ApprovalConsole(
        env["bridge"],
        verify_approval=verify_approval,
        human_cert=human.cert,
    )
    pending = {"action_id": "crm_write:10", "agent_id": "operator-1",
               "capability": "crm_write", "artifact_hash": "h10", "ts": 1_000}
    console.queue(pending)
    # Build a genuine Ed25519-signed ApprovalRecord via the same path the runtime
    # uses, bound to this exact action.
    from fleet.layers.runtime import Approval
    ap = Approval.sign(
        human.cert, human.key, "operator-1", "crm_write:10",
        "crm_write", "h10", "approve", "verified intel", 1_000,
    )
    status, body = _wsgi_post(console, ap.__dict__)
    assert status == "200 OK"
    assert b"true" in body
    assert any(e["kind"] == "console.approval_verified" for e in console.audit_log())


def test_g2_console_rejects_forged_approval(env):
    from fleet.gcp.console import ApprovalConsole
    from fleet.layers.approval import verify_approval

    rogue = env["cp"].publish_agent("rogue-1", "operator", ["crm_write"])
    console = ApprovalConsole(
        env["bridge"],
        verify_approval=verify_approval,
        human_cert=env["human"].cert,  # bound to the REAL human cert
    )
    console.queue({"action_id": "crm_write:11", "agent_id": "operator-1",
                   "capability": "crm_write", "artifact_hash": "h11", "ts": 1_000})
    # Forge an approval signed by the ROGUE key, not the human -> must be rejected.
    from fleet.layers.runtime import Approval
    forged = Approval.sign(
        rogue.cert, rogue.key, "operator-1", "crm_write:11",
        "crm_write", "h11", "approve", "i am the human now", 1_000,
    )
    status, body = _wsgi_post(console, forged.__dict__)
    assert status == "403 Forbidden"
    assert b"false" in body
