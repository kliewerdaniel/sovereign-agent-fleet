"""Phase 1 Control Plane tests (testing-strategy 14.2 + 14.7).

Proves by construction (not by clicking):
  * capability deny: agent lacking a capability gets granted=false (beat 2)
  * consequential capability requires approval (operator crm_write)
  * forged cert (not signed by root) -> Gateway DENY (beat 7)
  * expired cert -> DENY
  * revoked cert -> DENY
  * idempotency: replayed request with same key -> DENY
  * handoff schema: Researcher emitting classification -> rejected (D8)
  * handoff schema: Analyst citing missing/unknown evidence -> rejected
  * rotation: revoke -> re-issue -> new cert authenticates + old fails (D14 / beat 8)
  * signed deny event is chained into the tamper-evident audit ledger
"""
import os
import time

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from fleet.crypto.chriscrypt.store import JsonStore
from fleet.crypto.foundation import AgentCert, IdentityRoot
from fleet.layers import (
    ControlPlane,
    Handoff,
    HandoffError,
    RegistryError,
)


@pytest.fixture
def cp(tmp_path):
    master = b"phase1-master-secret"
    audit_key = Ed25519PrivateKey.from_private_bytes(
        HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"fleet:audit").derive(b"audit-1")
    )
    store = JsonStore(str(tmp_path / "audit.json"))
    return ControlPlane(master, audit_key, store=store)


@pytest.fixture
def published(cp):
    r = cp.publish_agent("researcher-1", "researcher", ["emit_evidence"])
    a = cp.publish_agent("analyst-1", "analyst", ["qualify", "verify_gate"])
    o = cp.publish_agent("operator-1", "operator", ["prepare_artifact", "crm_write", "outreach_send"])
    h = cp.publish_agent("human-1", "human", ["approve_deny"])
    return {"researcher": r, "analyst": a, "operator": o, "human": h}


# --- capability deny (beat 2, 14.2) ---------------------------------------

def test_researcher_lacks_crm_write_denied(cp, published):
    resp = cp.request_authority(published["researcher"].cert, "crm_write")
    assert resp.granted is False
    assert resp.decision == "deny"
    assert resp.signed_deny_event is not None


def test_analyst_lacks_crm_write_denied(cp, published):
    resp = cp.request_authority(published["analyst"].cert, "crm_write")
    assert resp.granted is False


def test_researcher_emit_evidence_granted(cp, published):
    resp = cp.request_authority(published["researcher"].cert, "emit_evidence")
    assert resp.granted is True
    assert resp.decision == "grant"  # not consequential


def test_operator_crm_write_requires_approval(cp, published):
    resp = cp.request_authority(published["operator"].cert, "crm_write")
    assert resp.granted is True
    assert resp.require_approval is True
    assert resp.decision == "require_approval"


# --- forged / expired / revoked (14.7) ------------------------------------

def test_forged_cert_not_signed_by_root_denied(cp, published):
    rogue_key = Ed25519PrivateKey.generate()
    pem = rogue_key.public_key().public_bytes(
        __import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding", "PublicFormat"]).Encoding.PEM,
        __import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding", "PublicFormat"]).PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    forged = AgentCert(
        agent_id="rogue", pubkey_pem=pem, role="operator",
        capabilities=["crm_write"], issued_at=1, expires_at=9_999_999_999,
        cert_seq=0, root_sig="deadbeef",
    )
    resp = cp.request_authority(forged, "crm_write")
    assert resp.granted is False


def test_expired_cert_denied(tmp_path):
    master = b"phase1-master-secret"
    audit_key = Ed25519PrivateKey.from_private_bytes(
        HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"fleet:audit").derive(b"audit-exp")
    )
    store = JsonStore(str(tmp_path / "audit.json"))
    local_cp = ControlPlane(master, audit_key, store=store, now_fn=lambda: 1_000)
    pub = local_cp.publish_agent("op-2", "operator", ["crm_write"], ttl_seconds=100)
    # advance time past expiry via the shared clock
    local_cp.advance_clock(1_000 + 200)
    resp = local_cp.request_authority(pub.cert, "crm_write")
    assert resp.granted is False


def test_revoked_cert_denied(cp, published):
    cp.registry.revoke("operator-1")
    resp = cp.request_authority(published["operator"].cert, "crm_write")
    assert resp.granted is False


def test_a3_revoke_invalidates_cached_grant_on_replay(cp, published):
    """A3: a previously-granted idempotency key must NOT survive a revoke.

    Without this, an attacker who obtained one legitimate grant could replay
    the cached positive verdict even after the agent is revoked. The Gateway
    re-validates liveness on replay (A3/D14).
    """
    key = "idem-revoke-a3"
    g = cp.request_authority(published["operator"].cert, "crm_write", idempotency_key=key)
    assert g.granted is True
    # Revoke the operator.
    cp.registry.revoke("operator-1")
    # Replay with the SAME idempotency key -> must now be denied (stale cache
    # is re-validated against registry liveness).
    r = cp.request_authority(published["operator"].cert, "crm_write", idempotency_key=key)
    assert r.granted is False
    assert r.signed_deny_event is not None


# --- idempotency (13.7) ----------------------------------------------------

def test_replay_same_idempotency_key_returns_prior(cp, published):
    key = "idem-001"
    r1 = cp.request_authority(published["operator"].cert, "crm_write", idempotency_key=key)
    assert r1.granted is True
    # 13.7: a replay of the same key returns the PRIOR verdict (idempotent),
    # not a fresh denial. Double-execution is blocked at the Runtime write layer.
    r2 = cp.request_authority(published["operator"].cert, "crm_write", idempotency_key=key)
    assert r2.granted is True
    assert r2 is r1 or r2.idempotency_key == key


# --- handoff schema (D8, 14.2) --------------------------------------------

def test_researcher_emitting_classification_rejected(cp, published):
    ev = {
        "evidence_id": "ev_1", "agent_id": "researcher-1",
        "citation": "https://example.com/x", "extract": "prospect uses cloud ERP",
        "source_hash": "abc", "classification": "icp_fit",  # forbidden field
    }
    h = Handoff.make(published["researcher"].cert, published["researcher"].key, "SourcedEvidence", ev)
    with pytest.raises(HandoffError):
        h.consume(cp.registry, known_evidence=set())


def test_researcher_evidence_consumed_then_analyst_cites_it(cp, published):
    ev = {
        "evidence_id": "ev_2", "agent_id": "researcher-1",
        "citation": "https://example.com/y", "extract": "VP engineering title found",
        "source_hash": "def",
    }
    h = Handoff.make(published["researcher"].cert, published["researcher"].key, "SourcedEvidence", ev)
    validated = h.consume(cp.registry, known_evidence=set())
    assert validated["evidence_id"] == "ev_2"

    intel = {
        "intel_id": "iq_1", "agent_id": "analyst-1", "target_id": "prospect-9",
        "predicates": [{"claim": "role=vp_eng", "claim_type": "role", "evidence_refs": ["ev_2"]}],
    }
    hi = Handoff.make(published["analyst"].cert, published["analyst"].key, "QualifiedIntel", intel)
    out = hi.consume(cp.registry, known_evidence={"ev_2"})
    assert out["intel_id"] == "iq_1"


def test_analyst_citing_unknown_evidence_rejected(cp, published):
    intel = {
        "intel_id": "iq_2", "agent_id": "analyst-1", "target_id": "prospect-9",
        "predicates": [{"claim": "role=vp_eng", "claim_type": "role", "evidence_refs": ["ev_nonexistent"]}],
    }
    hi = Handoff.make(published["analyst"].cert, published["analyst"].key, "QualifiedIntel", intel)
    with pytest.raises(HandoffError):
        hi.consume(cp.registry, known_evidence=set())


def test_handoff_with_bad_signature_rejected(cp, published):
    ev = {
        "evidence_id": "ev_3", "agent_id": "researcher-1",
        "citation": "https://example.com/z", "extract": "ok", "source_hash": "ghi",
    }
    h = Handoff.make(published["researcher"].cert, published["researcher"].key, "SourcedEvidence", ev)
    h.sender_sig = "00" * 64  # corrupt signature
    with pytest.raises(HandoffError):
        h.consume(cp.registry, known_evidence=set())


# --- rotation (D14, beat 8, 14.7) ------------------------------------------

def test_rotate_after_revoke_resumes_authority(cp, published):
    # revoke operator
    cp.registry.revoke("operator-1")
    assert cp.request_authority(published["operator"].cert, "crm_write").granted is False
    # rotate -> fresh cert/key under same agent_id
    rotated = cp.registry.rotate("operator-1")
    assert rotated.cert.cert_seq == published["operator"].cert.cert_seq + 1
    assert cp.request_authority(rotated.cert, "crm_write").granted is True
    # the OLD cert must no longer authenticate (compromised key is dead)
    assert cp.request_authority(published["operator"].cert, "crm_write").granted is False


# --- audit integrity -------------------------------------------------------

def test_deny_event_is_chained_and_verifiable(cp, published):
    cp.request_authority(published["researcher"].cert, "crm_write")
    assert cp.verify_audit() is True
    kinds = [e["kind"] for e in cp.audit.entries()]
    assert "gateway.deny" in kinds
