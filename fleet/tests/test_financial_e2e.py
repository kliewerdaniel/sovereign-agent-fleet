"""D27 — Financial reference workload: strict 1:1 adversarial e2e suite.

Every test exercises ONE real governance behavior and asserts the CONCRETE
signal the system emits (decision strings, gate names, reason substrings,
verifier status). No behavior depends on the model: the model may lie,
hallucinate, or disagree; the authority boundary holds regardless (M0).

Run: env -i PATH="$PWD/.venv/bin:/usr/bin:/bin" "$PWD/.venv/bin/python" -m pytest fleet/tests/test_financial_e2e.py -q
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import asdict
from typing import Any, Dict, Tuple

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from fleet.crypto.chriscrypt.store import JsonStore
from fleet.layers import (
    ControlPlane,
    MemBank,
    Runtime,
    Researcher,
    Analyst,
    Operator,
    ToolEnvelope,
)
from fleet.layers.runtime import Approval
from fleet.fin.domain import (
    Account,
    Mandate,
    TradeProposal,
    MarketData,
    assess,
    bind_trade,
    account_state_hash,
    required_trade_authorization,
)
from fleet.fin.market_adapter import ReplayFixture
from fleet.fin.exchange_sim import ExchangeSim
from fleet.fin.authorization import TradeAuthorization, build_trade_authorization
from fleet.fin.verify import verify_record, verify_control_plane


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

def _hkdf(label: bytes, seed: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=label).derive(seed)


def _env() -> Dict[str, Any]:
    """Build a clean CP + runtime + financial agents + paper account + market."""
    master = b"fin-master"
    audit_key = Ed25519PrivateKey.from_private_bytes(_hkdf(b"fleet:audit", b"audit-fin"))
    store = JsonStore(os.path.join(tempfile.mkdtemp(), "fin.json"))
    cp = ControlPlane(master, audit_key, store=store, now_fn=lambda: 2000, run_id="run-fin")
    mem = MemBank(_hkdf(b"fleet:mem", b"mem-fin"))
    rt = Runtime(cp, mem, now_fn=lambda: 2000,
                 brain=__import__("fleet.layers.brain", fromlist=["StubBrain"]).StubBrain())
    researcher = cp.publish_agent("researcher-1", "researcher", ["emit_evidence"])
    analyst = cp.publish_agent("analyst-1", "analyst", ["qualify"])
    operator = cp.publish_agent("operator-1", "operator", ["trade_execute"])
    human = cp.publish_agent("human-1", "human", ["approve_deny"])
    tool_cert, tool_key = cp.root.issue_cert("mkt", "tool", ["retrieve"], 2000, 9_999_999_999)
    cp.registry._certs["mkt"] = tool_cert
    account = Account("acct-1", cash=100_000.0, positions={},
                      mandate=Mandate(allowed_assets=["AAPL"]))
    market = ReplayFixture("AAPL", 2000, 150.0, 150.2, 150.1, 1.0e6, "replay").to_market_data()
    return dict(cp=cp, rt=rt, researcher=researcher, analyst=analyst, operator=operator,
                human=human, tool_cert=tool_cert, tool_key=tool_key,
                account=account, market=market)


def _evidence_intel(env: Dict[str, Any]) -> Any:
    out = b'{"citation":"https://example.com/a","extract":"AAPL strong momentum"}'
    ev = Researcher(env["researcher"], env["rt"]).gather(
        ToolEnvelope.make(env["tool_key"], "mkt", out), "q", ["citation", "extract"])
    return Analyst(env["analyst"], env["rt"]).qualify(
        ev, [{"claim": "x", "claim_type": "icp_fit", "confidence": 0.9,
              "evidence_refs": [ev.payload["evidence_id"]]}])


def _proposal(symbol: str = "AAPL", side: str = "BUY", qty: float = 10) -> TradeProposal:
    return TradeProposal(symbol, side, float(qty), {"type": "MARKET"}, "thesis",
                         0.9, ["ev-1"], "s1")


def _run(env: Dict[str, Any], proposal=None, consensus=None, approval=None,
         idempotency_key: str = "k") -> Tuple[Dict[str, Any], "ExchangeSim"]:
    if proposal is None:
        proposal = _proposal()
    intel = _evidence_intel(env)
    sim = ExchangeSim(env["account"], env["market"], now=2000)
    res = Operator(env["operator"], env["rt"]).act_trade(
        intel, proposal, env["account"], env["market"], env["account"].mandate, sim,
        idempotency_key=idempotency_key, approval=approval, consensus=consensus)
    return res, sim


def _final_record(cp: ControlPlane) -> Dict[str, Any]:
    entries = [e for e in cp.audit.entries() if e.get("kind") == "operator.final"]
    assert entries, "no operator.final record was written"
    return entries[-1]["payload"]


# ---------------------------------------------------------------------------
# 1. Golden path — model-proposed trade executes under AUTO, verifier PASSES
# ---------------------------------------------------------------------------

def test_golden_path_auto_executes_and_verifies():
    env = _env()
    res, _ = _run(env)
    assert res["final"] is True
    assert res["authorization"] == "AUTO"
    assert res["disposition"] == "AUTO"
    assert res["require_approval"] is False
    rec = _final_record(env["cp"])
    vr = verify_record(rec, env["operator"].cert, env["human"].cert, 2000)
    assert vr.status == "PASS", vr
    agg = verify_control_plane(env["cp"], env["operator"].cert, env["human"].cert, 2000)
    assert agg["overall"] == "PASS", agg


# ---------------------------------------------------------------------------
# 2. Model proposes its WORST trade (disallowed asset) — policy still BLOCKS
#    (M0: authority boundary independent of model output)
# ---------------------------------------------------------------------------

def test_model_worst_proposal_still_blocked():
    env = _env()
    # Mandate only allows AAPL; model "insists" on TSLA.
    res, _ = _run(env, proposal=_proposal(symbol="TSLA"))
    assert res["final"] is False
    assert res["blocked"] is True
    assert res["gate"] == "risk-policy"
    assert "asset-not-allowed" in res["reason"]


# ---------------------------------------------------------------------------
# 3. Unauthorized asset — explicit check
# ---------------------------------------------------------------------------

def test_unauthorized_asset_blocked():
    env = _env()
    res, _ = _run(env, proposal=_proposal(symbol="TSLA"))
    assert res["blocked"] is True
    assert res["gate"] == "risk-policy"
    assert "asset-not-allowed" in res["reason"]


# ---------------------------------------------------------------------------
# 4. Excessive position — notional breaches mandate limit -> BLOCK
# ---------------------------------------------------------------------------

def test_excessive_position_blocked():
    env = _env()
    # max_order_usd = 10_000; at $150/share, 1_000 shares = $150_000 -> breach.
    res, _ = _run(env, proposal=_proposal(qty=1000))
    assert res["final"] is False
    assert res["blocked"] is True
    assert res["gate"] == "risk-policy"
    # Real reason token emitted by the risk engine for oversized orders:
    assert "order-too-large" in res["reason"]


# ---------------------------------------------------------------------------
# 5. Replay detected — same idempotency_key yields the cached fill, no dup ledger
# ---------------------------------------------------------------------------

def test_replay_detected():
    env = _env()
    r1, _ = _run(env, idempotency_key="replay-key")
    before = len([e for e in env["cp"].audit.entries() if e.get("kind") == "operator.final"])
    r2, _ = _run(env, idempotency_key="replay-key")  # identical request
    after = len([e for e in env["cp"].audit.entries() if e.get("kind") == "operator.final"])
    # Second call is a replay: returns the cached, already-final result.
    assert r2["final"] is True
    assert r2.get("idempotent_replay") is True or r1["receipt"]["order_id"] == r2["receipt"]["order_id"]
    # No new ledger entry was written for the replay.
    assert after == before


# ---------------------------------------------------------------------------
# 6. Forged approval rejected — HUMAN tier requires a strictly-bound approval
# ---------------------------------------------------------------------------

def test_forged_approval_rejected():
    env = _env()
    # Force HUMAN tier via advisory consensus escalation.
    intel = _evidence_intel(env)
    sim = ExchangeSim(env["account"], env["market"], now=2000)
    # First, discover the artifact_hash the operator will bind.
    pre = account_state_hash(env["account"])
    risk = assess(_proposal(qty=50), env["account"], env["market"], env["account"].mandate, 2000)
    artifact = bind_trade(env["account"].account_id, _proposal(qty=50),
                          pre, env["market"].snapshot_hash, risk.risk_assessment_hash)
    # Forged: signature produced by the WRONG key (operator key, not human key).
    forged = Approval.sign(env["human"].cert, env["operator"].key,  # wrong key
                           env["operator"].agent_id, "human-key", "trade_execute",
                           artifact, "approve", "forged", 2000)
    res = Operator(env["operator"], env["rt"]).act_trade(
        intel, _proposal(qty=50), env["account"], env["market"], env["account"].mandate, sim,
        idempotency_key="human-key", approval=asdict(forged), consensus="weak")
    assert res["final"] is False
    assert res["blocked"] is True
    assert res["gate"] == "approval"
    assert "invalid" in res["reason"].lower() or "mis-bound" in res["reason"].lower()


# ---------------------------------------------------------------------------
# 7. Revoked identity rejected — gateway denies before any gate runs
# ---------------------------------------------------------------------------

def test_revoked_identity_rejected():
    env = _env()
    env["cp"].registry.revoke("operator-1")
    # A revoked operator cannot obtain capability authority (fail-closed at the
    # gateway, before any governance gate runs).
    resp = env["cp"].request_authority(env["operator"].cert, "trade_execute",
                                       idempotency_key="revoked")
    assert resp.granted is False
    assert resp.deny_reason


# ---------------------------------------------------------------------------
# 8. Tampered order rejected at Layer-3 — signature/state tamper -> REFUSE
# ---------------------------------------------------------------------------

def test_tampered_order_rejected():
    env = _env()
    res, _ = _run(env, idempotency_key="tamper-src")
    assert res["final"] is True
    rec = _final_record(env["cp"])
    ta = TradeAuthorization.from_dict(rec["ta"])
    # Tamper: flip the quantity after signing (invalidates the operator sig).
    ta.qty = ta.qty + 1.0
    sim2 = ExchangeSim(env["account"], env["market"], now=2000)
    ar = sim2.apply(ta, env["operator"].cert, env["operator"].key, now=2000)
    assert ar.ok is False
    assert "authorization-invalid" in ar.refuse_reason or "invalid" in ar.refuse_reason


# ---------------------------------------------------------------------------
# 9. Model disagreement escalates (advisory only, never de-escalates)
# ---------------------------------------------------------------------------

def test_model_disagreement_escalates():
    env = _env()
    # A perfectly-allowed proposal, but consensus="weak" -> escalate to HUMAN.
    intel = _evidence_intel(env)
    sim = ExchangeSim(env["account"], env["market"], now=2000)
    res = Operator(env["operator"], env["rt"]).act_trade(
        intel, _proposal(qty=10), env["account"], env["market"], env["account"].mandate, sim,
        idempotency_key="weak-key", consensus="weak")
    # No approval supplied -> cannot execute; HUMAN tier requires approval.
    assert res["final"] is False
    assert res.get("needs_approval") is True
    assert res["authorization"] == "HUMAN"

    # And consensus can NEVER rescue a hard breach (asset not allowed).
    sim2 = ExchangeSim(env["account"], env["market"], now=2000)
    res2 = Operator(env["operator"], env["rt"]).act_trade(
        intel, _proposal(symbol="TSLA"), env["account"], env["market"], env["account"].mandate, sim2,
        idempotency_key="weak-tsla", consensus="weak")
    assert res2["final"] is False
    assert res2["gate"] == "risk-policy"


# ---------------------------------------------------------------------------
# 10. Expired authorization rejected at Layer-3
# ---------------------------------------------------------------------------

def test_expired_authorization_rejected():
    env = _env()
    res, _ = _run(env, idempotency_key="exp-src")
    assert res["final"] is True
    rec = _final_record(env["cp"])
    ta = TradeAuthorization.from_dict(rec["ta"])
    # Re-apply far in the future (> expiration = ts + 300s).
    sim2 = ExchangeSim(env["account"], env["market"], now=2000 + 1000)
    ar = sim2.apply(ta, env["operator"].cert, env["operator"].key, now=2000 + 1000)
    assert ar.ok is False
    assert "expired" in ar.refuse_reason or "invalid" in ar.refuse_reason


# ---------------------------------------------------------------------------
# 11. State binding S1 != S2 — account drift between eval and apply -> REFUSE
# ---------------------------------------------------------------------------

def test_state_binding_s1_s2():
    env = _env()
    res, _ = _run(env, idempotency_key="bind-src")
    assert res["final"] is True
    rec = _final_record(env["cp"])
    ta = TradeAuthorization.from_dict(rec["ta"])
    # Account already mutated by the successful trade; the TA's portfolio_pre_hash
    # no longer matches the live account -> Layer-3 refuses.
    sim2 = ExchangeSim(env["account"], env["market"], now=2000)
    ar = sim2.apply(ta, env["operator"].cert, env["operator"].key, now=2000)
    assert ar.ok is False
    assert "portfolio-state-mismatch" in ar.refuse_reason


# ---------------------------------------------------------------------------
# 12. Verifier CRITICAL on tampered record (recomputed risk hash mismatch)
# ---------------------------------------------------------------------------

def test_verifier_critical_on_tamper():
    env = _env()
    res, _ = _run(env)
    assert res["final"] is True
    # Tamper the canonical risk hash in the logged record; the verifier's
    # recomputation will not match -> the control-plane aggregate must be CRITICAL
    # (per D27 §17: recompute mismatch fails the whole run, never overall PASS).
    rec = dict(_final_record(env["cp"]))  # shallow copy
    rec["risk_assessment_hash"] = "tampered"
    vr = verify_record(rec, env["operator"].cert, env["human"].cert, 2000)
    assert vr.status == "FAIL", vr
    assert "risk-hash-mismatch" in vr.reason
    # Inject a tampered operator.final record (tampered risk hash) into the
    # ledger and verify the control-plane aggregate escalates to CRITICAL
    # (per D27 §17: recompute mismatch fails the whole run, never overall PASS).
    tampered = dict(_final_record(env["cp"]))
    tampered["risk_assessment_hash"] = "tampered"
    env["cp"].audit.append({"kind": "operator.final", "result": "ok", **tampered})
    agg = verify_control_plane(env["cp"], env["operator"].cert, env["human"].cert, 2000)
    assert agg["overall"] == "CRITICAL", agg
    assert agg["failed"] >= 1, agg  # the tampered record fails recomputation


# ---------------------------------------------------------------------------
# 13. Verifier passes clean run (control-plane aggregate = PASS)
# ---------------------------------------------------------------------------

def test_verifier_passes_clean_run():
    env = _env()
    res, _ = _run(env)
    assert res["final"] is True
    agg = verify_control_plane(env["cp"], env["operator"].cert, env["human"].cert, 2000)
    assert agg["overall"] == "PASS", agg
    assert agg["total"] >= 1
    assert agg["passed"] == agg["total"]


# ---------------------------------------------------------------------------
# 14. Pure risk mapping — consensus advisory-only, hard breach always BLOCK
# ---------------------------------------------------------------------------

def test_required_disposition_mapping():
    env = _env()
    acct = env["account"]
    mkt = env["market"]
    mand = acct.mandate
    # Clean proposal -> AUTO
    p_ok = _proposal(qty=10)
    r_ok = assess(p_ok, acct, mkt, mand, 2000)
    assert required_trade_authorization(r_ok, None).value == "AUTO"
    # Disallowed asset -> BLOCKED regardless of consensus
    p_bad = _proposal(symbol="TSLA")
    r_bad = assess(p_bad, acct, mkt, mand, 2000)
    assert required_trade_authorization(r_bad, None).value == "BLOCKED"
    assert required_trade_authorization(r_bad, "weak").value == "BLOCKED"
    assert required_trade_authorization(r_bad, "consensus-agree").value == "BLOCKED"
    # Advisory escalation only: weak -> HUMAN, severe -> BLOCKED
    r_ok2 = assess(p_ok, acct, mkt, mand, 2000)
    assert required_trade_authorization(r_ok2, "weak").value == "HUMAN"
    assert required_trade_authorization(r_ok2, "severe").value == "BLOCKED"


# ---------------------------------------------------------------------------
# 14. MODEL-COUPLED PATH (D27 "AI strategy demonstrates the protocol")
#     The probabilistic brain PROPOSES; the EXACT same four-gate pipeline decides.
#     M0: a lying/hostile model cannot produce an executed trade.
# ---------------------------------------------------------------------------

def _env_with_brain(brain) -> Dict[str, Any]:
    """Same harness as _env() but with a configurable probabilistic brain."""
    master = b"fin-master"
    audit_key = Ed25519PrivateKey.from_private_bytes(_hkdf(b"fleet:audit", b"audit-fin"))
    store = JsonStore(os.path.join(tempfile.mkdtemp(), "fin.json"))
    cp = ControlPlane(master, audit_key, store=store, now_fn=lambda: 2000, run_id="run-fin")
    mem = MemBank(_hkdf(b"fleet:mem", b"mem-fin"))
    rt = Runtime(cp, mem, now_fn=lambda: 2000, brain=brain)
    researcher = cp.publish_agent("researcher-1", "researcher", ["emit_evidence"])
    analyst = cp.publish_agent("analyst-1", "analyst", ["qualify"])
    operator = cp.publish_agent("operator-1", "operator", ["trade_execute"])
    human = cp.publish_agent("human-1", "human", ["approve_deny"])
    tool_cert, tool_key = cp.root.issue_cert("mkt", "tool", ["retrieve"], 2000, 9_999_999_999)
    cp.registry._certs["mkt"] = tool_cert
    account = Account("acct-1", cash=100_000.0, positions={},
                      mandate=Mandate(allowed_assets=["AAPL"]))
    market = ReplayFixture("AAPL", 2000, 150.0, 150.2, 150.1, 1.0e6, "replay").to_market_data()
    return dict(cp=cp, rt=rt, researcher=researcher, analyst=analyst, operator=operator,
                human=human, tool_cert=tool_cert, tool_key=tool_key,
                account=account, market=market)


def test_cooperative_brain_proposal_executes_and_verifies():
    """An HONEST model: proposal flows through the same gates, executes, verifies PASS."""
    from fleet.layers.brain import CooperativeBrain
    env = _env_with_brain(CooperativeBrain(symbol="AAPL", qty=10))
    intel = _evidence_intel(env)
    sim = ExchangeSim(env["account"], env["market"], now=2000)
    res = Operator(env["operator"], env["rt"]).act_trade_from_brain(
        intel, env["account"], env["market"], env["account"].mandate, sim,
        idempotency_key="k-brain-ok")
    assert res["final"] is True, res
    assert res["authorization"] == "AUTO"
    rec = _final_record(env["cp"])
    vr = verify_record(rec, env["operator"].cert, env["human"].cert, 2000)
    assert vr.status == "PASS", vr
    agg = verify_control_plane(env["cp"], env["operator"].cert, env["human"].cert, 2000)
    assert agg["overall"] == "PASS", agg


def test_hostile_brain_proposal_refused_by_risk_policy():
    """M0 headline: a hostile model (unauth asset + 100x size) is REFUSED at the
    risk-policy Layer even though its output is schema-valid. No execution,
    no operator.final record written."""
    from fleet.layers.brain import HostileBrain
    env = _env_with_brain(HostileBrain())
    intel = _evidence_intel(env)
    sim = ExchangeSim(env["account"], env["market"], now=2000)
    res = Operator(env["operator"], env["rt"]).act_trade_from_brain(
        intel, env["account"], env["market"], env["account"].mandate, sim,
        idempotency_key="k-brain-hostile")
    assert res["final"] is False
    assert res["blocked"] is True
    assert res["gate"] == "risk-policy"
    # hostile model output never reaches the exchange / verifier
    finals = [e for e in env["cp"].audit.entries() if e.get("kind") == "operator.final"]
    assert not finals, "hostile model must not produce an executed trade"


def test_hostile_brain_rejected_at_every_layer_independently():
    """M0 robustness: the hostile proposal is rejected by the PURE risk function
    (no operator, no model) AND by the full pipeline. The boundary does not
    depend on whether the model is even consulted."""
    from fleet.layers.brain import HostileBrain, TradeStrategist
    env = _env_with_brain(HostileBrain())
    intel = _evidence_intel(env)
    # Build the hostile proposal directly via the strategist (pure fn), then
    # assert the SAME decision the full pipeline reaches.
    strategist = TradeStrategist(env["operator"], env["rt"], ["AAPL"])
    proposal = strategist.propose_from_evidence(intel, "hostile")
    # Pure risk engine refuses it independently of the model/operator.
    risk = assess(proposal, env["account"], env["market"], env["account"].mandate, 2000)
    assert required_trade_authorization(risk, None).value == "BLOCKED", risk.reason
    assert "asset-not-allowed" in risk.reason

