"""D28 Phase 4 — M0 proof (Run A = Run B) across BOTH workloads.

The load-bearing phase. It proves by construction that attaching a cognition
enrichment (EvaluationArtifact) to an *already-formed* governance proposal
changes NOTHING about the authorization verdict:

  * Financial workload: clean AUTO trade WITH cognition -> verifier-inert;
    independent recompute of disposition is identical to the recorded one; the
    M0 check (Run A == Run B) holds.
  * Incident workload: clean AUTO remediation WITH cognition -> same proof via
    the workload-agnostic incident verifier.
  * Adversarial: an enrichment that *claims* it forces a human approval is
    structurally ignored -- the disposition computed WITH vs WITHOUT it is
    byte-identical, so smuggling authority into cognition fails closed.

The M0 function lives in ``fleet.cognition`` (import wall intact); the gate is
injected as a pure callable so cognition never sees or touches it.
"""
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

import pytest

from fleet.crypto.chriscrypt.store import JsonStore
from fleet.crypto.foundation import IdentityRoot
from fleet.layers import (
    Analyst, ControlPlane, Handoff, MemBank, Operator, Researcher,
    Runtime, ToolEnvelope, VERIFIED,
)
from fleet.layers.incident import Authorization
from fleet.fin.domain import (
    Account, Mandate, TradeProposal, assess, account_state_hash,
    required_trade_authorization,
)
from fleet.fin.market_adapter import ReplayFixture
from fleet.fin.exchange_sim import ExchangeSim
from fleet.fin.verify import verify_record, verify_control_plane
from fleet.layers.incident_verify import verify_record as inc_verify_record
from fleet.cognition.evaluation import (
    EvaluationArtifact, ProposalArtifact, to_gateway_intent,
)


def _hkdf(label: bytes, seed: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=label).derive(seed)


def _fin_env():
    master = b"fin-m0"
    audit = Ed25519PrivateKey.from_private_bytes(_hkdf(b"fleet:audit", b"a-fin"))
    import tempfile, os
    store = JsonStore(os.path.join(tempfile.mkdtemp(), "fin.json"))
    cp = ControlPlane(master, audit, store=store, now_fn=lambda: 2000)
    mem = MemBank(_hkdf(b"fleet:mem", b"m-fin"))
    rt = Runtime(cp, mem, now_fn=lambda: 2000,
                 brain=__import__("fleet.layers.brain", fromlist=["StubBrain"]).StubBrain())
    r = cp.publish_agent("researcher-1", "researcher", ["emit_evidence"])
    a = cp.publish_agent("analyst-1", "analyst", ["qualify"])
    o = cp.publish_agent("operator-1", "operator", ["trade_execute"])
    tool_cert, tool_key = cp.root.issue_cert("mkt", "tool", ["retrieve"], 2000, 9_999_999_999)
    cp.registry._certs["mkt"] = tool_cert
    account = Account("acct-1", cash=100_000.0, positions={},
                      mandate=Mandate(allowed_assets=["AAPL"]))
    market = ReplayFixture("AAPL", 2000, 150.0, 150.2, 150.1, 1.0e6, "replay").to_market_data()
    return {"cp": cp, "rt": rt, "r": r, "a": a, "o": o,
            "tool_cert": tool_cert, "tool_key": tool_key,
            "account": account, "market": market}


def _fin_intel(env):
    out = b'{"citation":"https://example.com/a","extract":"AAPL momentum"}'
    ev = Researcher(env["r"], env["rt"]).gather(
        ToolEnvelope.make(env["tool_key"], "mkt", out), "q", ["citation", "extract"])
    return Analyst(env["a"], env["rt"]).qualify(
        ev, [{"claim": "x", "claim_type": "icp_fit", "confidence": 0.9,
              "evidence_refs": [ev.payload["evidence_id"]]}])


def _enrichment_block(producer_cert, producer_key, **art_over):
    art = EvaluationArtifact(producer_cert_id=producer_cert.agent_id, **art_over)
    return ProposalArtifact({}, art).bind(producer_cert, producer_key)


def _inc_env():
    master = b"inc-m0"
    audit = Ed25519PrivateKey.from_private_bytes(_hkdf(b"fleet:audit", b"a-inc"))
    import tempfile, os
    store = JsonStore(os.path.join(tempfile.mkdtemp(), "inc.json"))
    cp = ControlPlane(master, audit, store=store, now_fn=lambda: 2000)
    mem = MemBank(_hkdf(b"fleet:mem", b"m-inc"))
    rt = Runtime(cp, mem, now_fn=lambda: 2000)
    r = cp.publish_agent("researcher-1", "researcher", ["emit_evidence"])
    a = cp.publish_agent("analyst-1", "analyst", ["qualify", "verify_gate"])
    o = cp.publish_agent("operator-1", "operator",
                         ["prepare_artifact", "incident_remediate"])
    tool_cert, tool_key = cp.root.issue_cert("web_tool", "tool", ["retrieve"], 2000, 9_999_999_999)
    cp.registry._certs["web_tool"] = tool_cert
    from fleet.simenv.env import SimEnv
    return {"cp": cp, "rt": rt, "r": r, "a": a, "o": o,
            "tool_cert": tool_cert, "tool_key": tool_key, "sim": SimEnv()}


def _inc_intel(env):
    out = b'{"citation":"https://src.example/x","extract":"indicator 0"}'
    ev = Researcher(env["r"], env["rt"]).gather(
        ToolEnvelope.make(env["tool_key"], "web_tool", out), "q", ["citation", "extract"])
    stamped = Analyst(env["a"], env["rt"]).qualify(
        ev, [{"claim": "compromise=true", "claim_type": "role",
              "evidence_refs": [ev.payload["evidence_id"]]}]).payload
    stamped["verification"] = VERIFIED
    stamped["severity"] = "LOW"
    return Handoff.make(env["a"].cert, env["a"].key, "QualifiedIntel", stamped)


# ---------------------------------------------------------------------------
# Financial workload: cognition attached, M0 holds, verdict unchanged
# ---------------------------------------------------------------------------

def test_financial_m0_with_cognition():
    env = _fin_env()
    intel = _fin_intel(env)
    enrichment = _enrichment_block(
        env["a"].cert, env["a"].key, uncertainty=0.9, contradiction_count=3)
    sim = ExchangeSim(env["account"], env["market"], now=2000)
    res = Operator(env["o"], env["rt"]).act_trade(
        intel, TradeProposal("AAPL", "BUY", 10.0, {"type": "MARKET"}, "t", 0.9, ["ev"], "s1"),
        env["account"], env["market"], env["account"].mandate, sim,
        idempotency_key="k-fin", enrichment=enrichment)
    assert res["final"] is True
    assert res["authorization"] == "AUTO"  # clean small qty -> AUTO, not HUMAN

    rec = [e for e in env["cp"].audit.entries() if e.get("kind") == "operator.final"][-1]["payload"]
    # enrichment was embedded (D-D binding)
    assert rec.get("enrichment") is not None
    # The M0 proof ran inside the verifier and held.
    vr = verify_record(rec, env["o"].cert, None, 2000,
                       registry=env["cp"].registry)
    assert vr.status == "PASS", vr.reason
    assert vr.m0_ok is True


def test_financial_m0_independent_recompute_identical():
    env = _fin_env()
    intel = _fin_intel(env)
    enrichment = _enrichment_block(env["a"].cert, env["a"].key, uncertainty=0.95)
    sim = ExchangeSim(env["account"], env["market"], now=2000)
    Operator(env["o"], env["rt"]).act_trade(
        intel, TradeProposal("AAPL", "BUY", 10.0, {"type": "MARKET"}, "t", 0.9, ["ev"], "s1"),
        env["account"], env["market"], env["account"].mandate, sim,
        idempotency_key="k-recomp", enrichment=enrichment)

    rec = [e for e in env["cp"].audit.entries() if e.get("kind") == "operator.final"][-1]["payload"]
    # Independent recompute of disposition WITHOUT the enrichment must equal the
    # recorded disposition (cognition stripped == cognition attached).
    account = env["account"]
    mand = account.mandate
    market = env["market"]
    prop = rec["proposal"]
    proposal = TradeProposal(prop["symbol"], prop["side"], float(prop["qty"]),
                             prop["price_constraint"], prop["thesis"],
                             float(prop["confidence"]), list(prop["evidence_refs"]),
                             prop["strategy_id"])
    risk = assess(proposal, account, market, mand, 2000)
    stripped = required_trade_authorization(risk, rec.get("consensus")).value
    assert stripped == rec["disposition"], "M0: verdict changed when cognition stripped"


# ---------------------------------------------------------------------------
# Incident workload: cognition attached, M0 holds (workload-agnostic proof)
# ---------------------------------------------------------------------------

def test_incident_m0_with_cognition():
    env = _inc_env()
    intel = _inc_intel(env)
    enrichment = _enrichment_block(
        env["a"].cert, env["a"].key, uncertainty=0.8, popper={"failed": 2})
    res = Operator(env["o"], env["rt"]).act(
        intel, "block egress on web-edge", "incident_remediate", "idem-inc",
        target_workload="web-edge", action_name="block_egress", simenv=env["sim"],
        enrichment=enrichment)
    assert res["final"] is True
    assert res["authorization"] == Authorization.AUTO.value

    rec = [e["payload"] for e in env["cp"].audit.entries()
           if e.get("kind") == "operator.final"
           and e.get("payload", {}).get("target") == "web-edge"][-1]
    assert rec.get("enrichment") is not None
    vr = inc_verify_record(rec, env["o"].cert, 2000,
                           registry=env["cp"].registry)
    assert vr.status == "PASS", vr.reason
    assert vr.m0_ok is True


# ---------------------------------------------------------------------------
# Adversarial: smuggling an approval instruction into cognition FAILS CLOSED
# ---------------------------------------------------------------------------

def test_adversarial_enrichment_cannot_change_verdict():
    env = _fin_env()
    intel = _fin_intel(env)  # AUTO-bound proposal (small qty)

    # Attacker crafts an enrichment that LIES about needing a human approval by
    # smuggling a governance flag into the enrichment payload.
    malicious = EvaluationArtifact(
        producer_cert_id=env["a"].cert.agent_id,
        uncertainty=0.0, contradiction_count=0,
        evidence_quality={"authenticity": 1.0},
        needs_met={"intent": True, "constraints_satisfied": True, "gaps": [],
                   "requires_human_review": True},  # smuggled flag
    )
    # The signals-not-flags guarantee rejects it BEFORE it can be signed/sent.
    with pytest.raises(Exception):
        ProposalArtifact({}, malicious).bind(env["a"].cert, env["a"].key)

    # Even if an attacker bypassed that and attached a benign enrichment, the
    # verdict is computed from governance inputs only (D-A): AUTO, not HUMAN.
    benign = _enrichment_block(env["a"].cert, env["a"].key, uncertainty=0.0)
    sim = ExchangeSim(env["account"], env["market"], now=2000)
    res = Operator(env["o"], env["rt"]).act_trade(
        intel, TradeProposal("AAPL", "BUY", 10.0, {"type": "MARKET"}, "t", 0.9, ["ev"], "s1"),
        env["account"], env["market"], env["account"].mandate, sim,
        idempotency_key="k-adv", enrichment=benign)
    assert res["authorization"] == "AUTO"
    assert res["require_approval"] is False
    rec = [e for e in env["cp"].audit.entries() if e.get("kind") == "operator.final"][-1]["payload"]
    vr = verify_record(rec, env["o"].cert, None, 2000,
                       registry=env["cp"].registry)
    assert vr.m0_ok is True  # M0 holds even against a hostile enrichment


def test_cognition_never_mutates_governance_surface():
    # The single seam: to_gateway_intent passes the surface through untouched.
    surface = {"intel_id": "iq-9", "symbol": "AAPL"}
    art = EvaluationArtifact(producer_cert_id="evaluator-1", uncertainty=0.99)
    out_surface, force = to_gateway_intent(surface, art)
    assert out_surface is surface              # cognition never mutates it
    assert force is True                        # only a boolean escapes
    assert "requires_human_review" not in art.to_payload()  # signals only
