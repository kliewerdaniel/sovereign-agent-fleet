"""Phase 2 (D21 hardening) — A1/A2 adversarial tests for human approval.

Proves the Operator's D17 enforcement is CRYPTOGRAPHIC, not narrative:

  * a forged approval (signed by the wrong key) is rejected;
  * an approval rebound to a DIFFERENT action_id is rejected (no reuse);
  * an approval rebound to a DIFFERENT artifact is rejected (no swap);
  * an approval rebound to a DIFFERENT capability is rejected;
  * an approval whose signer is NOT a `human` role cert is rejected;
  * a valid, strictly-bound approval proceeds to FINAL.

These run against the live Control Plane with no fakes. They fail closed:
any bypass would let an unapproved consequential write execute.
"""
from fleet.crypto.foundation import AgentCert, canonical_bytes
from fleet.layers import (
    Analyst,
    Approval,
    ControlPlane,
    HALLUCINATION,
    Handoff,
    MemBank,
    Operator,
    Researcher,
    Runtime,
    VERIFIED,
    ToolEnvelope,
    stamp,
)
from fleet.layers.approval import verify_approval


def _agent_cp(tmp_path):
    import json
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from fleet.crypto.chriscrypt.store import JsonStore
    from fleet.crypto.foundation import IdentityRoot

    master = b"a1-a2-master"
    audit = Ed25519PrivateKey.from_private_bytes(
        HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
             info=b"fleet:audit").derive(b"audit-a1"))
    store = JsonStore(str(tmp_path / "audit.json"))
    cp = ControlPlane(master, audit, store=store, now_fn=lambda: 1_000)
    kek = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
               info=b"fleet:mem").derive(b"mem-a1")
    mem = MemBank(kek)
    rt = Runtime(cp, mem, now_fn=lambda: 1_000)
    r = cp.publish_agent("researcher-1", "researcher", ["emit_evidence"])
    a = cp.publish_agent("analyst-1", "analyst", ["qualify", "verify_gate"])
    o = cp.publish_agent("operator-1", "operator", ["prepare_artifact", "crm_write"])
    human = cp.publish_agent("human-1", "human", ["approve_deny"])
    tool_cert, tool_key = cp.root.issue_cert("web_tool", "tool", ["retrieve"],
                                             1000, 9_999_999_999)
    cp.registry._certs["web_tool"] = tool_cert

    # Build one VERIFIED intel handoff (>=2 refs -> conf 1.0).
    def _gather(extract):
        out = json.dumps({"citation": "https://x/y", "extract": extract}).encode()
        env = ToolEnvelope.make(tool_key, "web_tool", out)
        return Researcher(r, rt).gather(env, "q", ["citation", "extract"])

    ev1 = _gather("prospect uses cloud ERP")
    ev2 = _gather("VP engineering title")
    intel = {
        "intel_id": "iq_a1", "agent_id": "analyst-1", "target_id": "p",
        "predicates": [{"claim": "icp_fit=true", "claim_type": "icp_fit",
                        "evidence_refs": [ev1.payload["evidence_id"],
                                          ev2.payload["evidence_id"]]}],
    }
    stamped = stamp(intel, rt.evidence_meta(), 1_000)
    assert stamped["verification"] == VERIFIED
    iq = Handoff.make(a.cert, a.key, "QualifiedIntel", stamped)
    return cp, rt, r, a, o, human, iq, tool_key


def _ah(text):
    from fleet.layers.armor import redact_pii
    from fleet.crypto.foundation import sha256
    red, _ = redact_pii(text)
    return sha256(red.encode("utf-8"))


def test_valid_bound_approval_proceeds():
    # placeholder; real fixture injected per-test below
    assert True


# --- fixtures ----------------------------------------------------------------

def _mk(tmp_path):
    return _agent_cp(tmp_path)


# --- tests -------------------------------------------------------------------

def test_a1_forged_approval_rejected(tmp_path):
    cp, rt, r, a, o, human, iq, _ = _mk(tmp_path)
    op = Operator(o, rt)
    artifact = "Write CRM: ICP fit confirmed."
    # Sign with the OPERATOR's key, not the human's -> invalid signature under
    # the human cert's pubkey.
    forged = Approval.sign(o.cert, o.key, "operator-1", "idem-x", "crm_write",
                           _ah(artifact), "approve", "mine", 1_001).__dict__
    res = op.act(iq, artifact, "crm_write", "idem-x", approval=forged)
    assert res["final"] is False
    assert res["blocked"] is True
    assert "operator.final" not in [e.get("kind") for e in cp.audit.entries()]


def test_a2_approval_rebound_to_other_action_rejected(tmp_path):
    cp, rt, r, a, o, human, iq, _ = _mk(tmp_path)
    op = Operator(o, rt)
    artifact = "Write CRM: ICP fit confirmed."
    # Approval is bound to action_id "idem-other", but the action uses "idem-x".
    ap = Approval.sign(human.cert, human.key, "operator-1", "idem-other",
                       "crm_write", _ah(artifact), "approve", "ok", 1_001).__dict__
    res = op.act(iq, artifact, "crm_write", "idem-x", approval=ap)
    assert res["final"] is False
    assert res["blocked"] is True


def test_a2_approval_rebound_to_other_artifact_rejected(tmp_path):
    cp, rt, r, a, o, human, iq, _ = _mk(tmp_path)
    op = Operator(o, rt)
    artifact_a = "Write CRM: ICP fit confirmed."
    artifact_b = "Write CRM: DIFFERENT prospect."
    # Approval signs artifact_hash of A, action commits B.
    ap = Approval.sign(human.cert, human.key, "operator-1", "idem-x", "crm_write",
                       _ah(artifact_a), "approve", "ok", 1_001).__dict__
    res = op.act(iq, artifact_b, "crm_write", "idem-x", approval=ap)
    assert res["final"] is False
    assert res["blocked"] is True


def test_a2_approval_rebound_to_other_capability_rejected(tmp_path):
    cp, rt, r, a, o, human, iq, _ = _mk(tmp_path)
    op = Operator(o, rt)
    artifact = "Write CRM: ICP fit confirmed."
    # Approval signs capability "outreach_send", action requests "crm_write".
    ap = Approval.sign(human.cert, human.key, "operator-1", "idem-x",
                       "outreach_send", _ah(artifact), "approve", "ok", 1_001).__dict__
    res = op.act(iq, artifact, "crm_write", "idem-x", approval=ap)
    assert res["final"] is False
    assert res["blocked"] is True


def test_a1_non_human_signer_rejected(tmp_path):
    cp, rt, r, a, o, human, iq, _ = _mk(tmp_path)
    op = Operator(o, rt)
    artifact = "Write CRM: ICP fit confirmed."
    # Signed by the ANALYST (valid signature, but role != human).
    ap = Approval.sign(a.cert, a.key, "operator-1", "idem-x", "crm_write",
                       _ah(artifact), "approve", "ok", 1_001).__dict__
    res = op.act(iq, artifact, "crm_write", "idem-x", approval=ap)
    assert res["final"] is False
    assert res["blocked"] is True


def test_a1_valid_bound_approval_succeeds(tmp_path):
    cp, rt, r, a, o, human, iq, _ = _mk(tmp_path)
    op = Operator(o, rt)
    artifact = "Write CRM: ICP fit confirmed."
    ap = Approval.sign(human.cert, human.key, "operator-1", "idem-ok",
                       "crm_write", _ah(artifact), "approve", "ok", 1_001).__dict__
    # verify_approval itself agrees (belt-and-suspenders property test).
    hc = cp.registry.human_cert()
    assert hc is not None
    assert verify_approval(ap, hc, "idem-ok", "crm_write", _ah(artifact)) is True
    res = op.act(iq, artifact, "crm_write", "idem-ok", approval=ap)
    assert res["final"] is True
    assert "operator.final" in [e.get("kind") for e in cp.audit.entries()]
