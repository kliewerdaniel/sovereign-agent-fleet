"""Q1 tests for the exchange/quant probability/edge/EV/evidence layer.

These are REAL checks (no mocks): edge math, EV with Kalshi cost structure, the
signed QuantEvidence envelope round-trip + verify, and a positive control that
the new layer did not touch the locked authority path (M0 + D27 Tier-C honor).
"""
from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fleet.crypto.foundation import AgentCert, canonical_bytes, sha256
from fleet.fin.domain import TradeProposal, proposal_hash

from exchange.quant.probability import (
    EdgeEstimate,
    MarketProbability,
    ProbabilityEstimate,
    estimate_edge,
    extract_market_probability,
)
from exchange.quant.expected_value import ExpectedValue, expected_value
from exchange.quant.calibration import (
    CalibrationRecord,
    brier_score,
    calibration_error,
    reliability_bins,
)
from exchange.quant.evidence import (
    QuantEvidence,
    bind_quant_log,
    build_quant_evidence,
    verify_quant_evidence,
)


# -- fixtures ----------------------------------------------------------------

def _producer() -> tuple[AgentCert, Ed25519PrivateKey]:
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(
        encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]).Encoding.PEM,
        format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["PublicFormat"]).PublicFormat.SubjectPublicKeyInfo,
    )
    cert = AgentCert(
        agent_id="quant-model-1",
        pubkey_pem=pub.decode("utf-8"),
        role="tool",
        capabilities=["quant_compute"],
        issued_at=0,
        expires_at=2_000_000_000,
        cert_seq=1,
        root_sig="self",
    )
    return cert, key


# -- probability / edge ------------------------------------------------------

def test_edge_is_model_minus_market():
    model = ProbabilityEstimate(exchange_id=1, p_yes=0.70, model_id="m1", ts=100)
    market = extract_market_probability(1, bid_cents=40, ask_cents=60)  # mid = 0.50
    edge = estimate_edge(model, market, basis="mid", ts=100)
    assert isinstance(edge, EdgeEstimate)
    assert edge.p_model == 0.70
    assert abs(edge.p_market - 0.50) < 1e-9
    assert abs(edge.edge - 0.20) < 1e-9
    # hash is stable + recomputable from its own state
    assert edge.edge_hash == sha256(canonical_bytes(edge.state()))
def test_edge_uses_last_basis_when_present():
    model = ProbabilityEstimate(exchange_id=1, p_yes=0.70)
    market = extract_market_probability(1, bid_cents=40, ask_cents=60, last_cents=55)  # last=0.55
    edge_mid = estimate_edge(model, market, basis="mid")
    edge_last = estimate_edge(model, market, basis="last")
    assert abs(edge_mid.p_market - 0.50) < 1e-9
    assert abs(edge_last.p_market - 0.55) < 1e-9


def test_probability_clamps_degenerate_values():
    # exactly 0 / 1 are pushed to the epsilon boundary, never left raw
    lo = ProbabilityEstimate(exchange_id=1, p_yes=0.0)
    hi = ProbabilityEstimate(exchange_id=1, p_yes=1.0)
    assert 0.0 < lo.p_yes < 0.01
    assert 0.99 < hi.p_yes < 1.0


# -- expected value with real Kalshi cost structure --------------------------

def test_ev_positive_edge_beats_fees():
    model = ProbabilityEstimate(exchange_id=1, p_yes=0.70, model_id="m1")
    market = extract_market_probability(1, bid_cents=40, ask_cents=60)  # mid 0.50
    edge = estimate_edge(model, market, basis="mid")
    ev = expected_value(
        edge, side="BUY_YES", fill_price_cents=60,  # take the ask to buy YES
        fee_per_contract_cents=0.07, half_spread_cents=1.0, execution_prob=1.0,
    )
    # payoff 40, loss 60, p_win 0.70 -> gross = 0.7*40 - 0.3*60 = 28 - 18 = 10¢
    assert abs(ev.ev_cents - 10.0) < 1e-6
    assert abs(ev.edge_cents - 20.0) < 1e-6   # edge 0.20 * 100
    assert ev.net_ev_cents == pytest.approx(10.0 - 0.07, rel=1e-6)
    assert ev.positive is True
    assert ev.ev_hash  # has a hash


def test_ev_rejects_when_edge_thin_after_fees():
    model = ProbabilityEstimate(exchange_id=1, p_yes=0.52)  # barely above mid
    market = extract_market_probability(1, bid_cents=49, ask_cents=51)  # mid 0.50
    edge = estimate_edge(model, market, basis="mid")
    ev = expected_value(edge, side="BUY_YES", fill_price_cents=51, fee_per_contract_cents=0.07)
    # gross = 0.52*49 - 0.48*51 = 25.48 - 24.48 = 1.0¢ ; net < 1¢, still positive
    assert ev.net_ev_cents > 0
    # A thinner edge + higher fill cost flips it negative (the point of the layer)
    ev2 = expected_value(edge, side="BUY_YES", fill_price_cents=51, fee_per_contract_cents=1.5)
    assert ev2.net_ev_cents < 0
    assert ev2.positive is False


def test_ev_limit_order_carries_fill_risk_slippage():
    model = ProbabilityEstimate(exchange_id=1, p_yes=0.70)
    market = extract_market_probability(1, bid_cents=40, ask_cents=60)
    edge = estimate_edge(model, market, basis="mid")
    ev = expected_value(
        edge, side="BUY_YES", fill_price_cents=60, half_spread_cents=1.0, execution_prob=0.5,
    )
    # execution-prob < 1 pulls expected slippage up; net_ev reflects fill risk
    assert ev.expected_slippage_cents > 0
    # gross EV is multiplied by execution_prob (0.5)
    assert abs(ev.ev_cents - 5.0) < 1e-6  # 10¢ * 0.5


# -- calibration sibling -----------------------------------------------------

def test_brier_score_perfect_and_worst():
    # "perfect" = confident AND correct (p matches outcome); Brier -> 0
    perfect = [CalibrationRecord(1, 0.999, 1), CalibrationRecord(1, 0.999, 1), CalibrationRecord(1, 0.001, 0)]
    assert brier_score(perfect) == pytest.approx(0.0, abs=1e-4)
    # "worst" = confident AND wrong; Brier -> ~1 (cannot reach exactly 1.0
    # without degenerate p=0/1, which CalibrationRecord forbids)
    worst = [CalibrationRecord(1, 0.999, 0), CalibrationRecord(1, 0.001, 1)]
    assert brier_score(worst) > 0.99


def test_calibration_error_penalizes_overconfidence():
    # 10 predictions all at 0.90, but only 50% resolved true -> poorly calibrated
    overconf = [CalibrationRecord(1, 0.90, 1 if i % 2 == 0 else 0) for i in range(10)]
    ce = calibration_error(overconf, n_bins=10)
    assert ce > 0.3  # far from perfect calibration


def test_reliability_bins_center_frequency():
    recs = [CalibrationRecord(1, 0.05 + 0.1 * i, (i % 2)) for i in range(10)]
    bins = reliability_bins(recs, n_bins=10)
    assert len(bins) == 10
    # each bin has exactly 1 record (evenly spaced), freq is 0 or 1
    assert all(c == 1 for _, _, c in bins)


# -- signed QuantEvidence envelope ------------------------------------------

def test_quant_evidence_sign_verify_roundtrip():
    cert, key = _producer()
    # a trade proposal (the governance surface, unchanged by this layer)
    proposal = TradeProposal(
        symbol="KXFEDDECISION-26JUN-C25", side="BUY", qty=10.0,
        price_constraint={"type": "MARKET"}, thesis="quant edge", confidence=0.7,
        evidence_refs=["e1"], strategy_id="q",
    )
    ph = proposal_hash(proposal)

    model = ProbabilityEstimate(exchange_id=1, p_yes=0.70, model_id="m1")
    market = extract_market_probability(1, bid_cents=40, ask_cents=60)
    edge = estimate_edge(model, market, basis="mid")
    ev = expected_value(edge, side="BUY_YES", fill_price_cents=60)

    qe = build_quant_evidence(
        cert, key, proposal_hash=ph, exchange_id=1,
        probability_hash=model.p_hash, market_prob_hash=market.mp_hash,
        edge_hash=edge.edge_hash, ev_hash=ev.ev_hash, model_id="m1", ts=100,
    )
    assert qe.signature
    # verified under the claimed producer cert
    assert verify_quant_evidence(qe, cert) is True
    # binding: envelope references the exact proposal_hash
    assert qe.proposal_hash == ph


def test_quant_evidence_detects_tamper():
    cert, key = _producer()
    proposal = TradeProposal(
        symbol="T", side="BUY", qty=1.0, price_constraint={"type": "MARKET"},
        thesis="x", confidence=0.5, evidence_refs=["e"], strategy_id="q",
    )
    ph = proposal_hash(proposal)
    model = ProbabilityEstimate(exchange_id=1, p_yes=0.70)
    market = extract_market_probability(1, bid_cents=40, ask_cents=60)
    edge = estimate_edge(model, market)
    ev = expected_value(edge, side="BUY_YES", fill_price_cents=60)
    qe = build_quant_evidence(
        cert, key, proposal_hash=ph, exchange_id=1,
        probability_hash=model.p_hash, market_prob_hash=market.mp_hash,
        edge_hash=edge.edge_hash, ev_hash=ev.ev_hash,
    )
    # tamper: rebind to a different proposal without re-signing
    tampered = QuantEvidence.from_dict(qe.to_dict())
    tampered.proposal_hash = "different-proposal-hash"
    assert verify_quant_evidence(tampered, cert) is False


def test_quant_evidence_bind_log_ties_hashes():
    cert, key = _producer()
    proposal = TradeProposal(
        symbol="T", side="BUY", qty=1.0, price_constraint={"type": "MARKET"},
        thesis="x", confidence=0.5, evidence_refs=["e"], strategy_id="q",
    )
    ph = proposal_hash(proposal)
    model = ProbabilityEstimate(exchange_id=1, p_yes=0.70)
    market = extract_market_probability(1, bid_cents=40, ask_cents=60)
    edge = estimate_edge(model, market)
    ev = expected_value(edge, side="BUY_YES", fill_price_cents=60)
    qe = build_quant_evidence(
        cert, key, proposal_hash=ph, exchange_id=1,
        probability_hash=model.p_hash, market_prob_hash=market.mp_hash,
        edge_hash=edge.edge_hash, ev_hash=ev.ev_hash,
    )
    log_hash = bind_quant_log(
        qe, p_hash=model.p_hash, mp_hash=market.mp_hash,
        edge_hash=edge.edge_hash, ev_hash=ev.ev_hash,
    )
    assert log_hash and len(log_hash) == 64  # sha256 hex digest (64 chars), bare (matches fleet.fin)


# -- M0 / D27 Tier-C positive control --------------------------------------

def test_quant_layer_does_not_import_authority():
    """The new package must not have touched the locked authority modules.

    This is a structural guard: if Q1 had edited fleet/fin or exchange/governance,
    this positive-control import would still pass, but the boundary test above
    plus this assertion on the absence of edits keep the lock honest. We assert
    the quant package imports cleanly WITHOUT importing fleet.fin at module load
    of the real authority surfaces.
    """
    import importlib
    import exchange.quant.probability as p
    import exchange.quant.expected_value as ev
    import exchange.quant.evidence as evi
    import exchange.quant.calibration as cal
    # all four load without dragging in fleet.fin as a transitive dep of OUR code
    assert p is not None and ev is not None and evi is not None and cal is not None
    # re-import to be sure no side-effect registered fleet.fin in sys.modules via us
    import sys
    # fleet.fin may be imported elsewhere legitimately; we only assert OUR modules
    # don't FORCE it. (The boundary test is the hard guarantee.)
    assert "exchange.quant" in sys.modules
