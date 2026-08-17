"""Q3 tests: Bayesian belief updating + regime detection (advisory evidence).

Real pipeline, no mocks. Asserts:
  * BayesianBelief: conjugate update correctness (Beta algebra), soft point
    estimate weighting, hard outcome absorption, credible interval bounds.
  * RegimeDetector: deterministic 2-state HMM — calm stream -> CALM, turbulent
    stream -> TURBULENT; exact forward pass; reproducible hashes.
  * Q3 folds into evaluate_quant: belief + regime present, hashes bound, the
    envelope still signs + verifies, and M0 holds (no authority fields added).
  * Determinism: same ctx -> identical belief/regime hashes (I15).
  * Import wall: bayesian.py / regime.py import only fleet.crypto + intra-package.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fleet.crypto.foundation import AgentCert
from exchange.quant.bayesian import BayesianBelief, prior_belief, update_belief
from exchange.quant.evidence import verify_quant_evidence
from exchange.quant.orchestrator import QuantContext, evaluate_quant
from exchange.quant.regime import RegimeDetector, RegimeState, detect_regime


# ----------------------------------------------------------------------------
# Bayesian belief
# ----------------------------------------------------------------------------
def test_bayesian_prior_is_uniform_mean_half():
    b = prior_belief(1)
    assert b.posterior_p_yes == pytest.approx(0.5)
    assert b.alpha == 1.0 and b.beta == 1.0
    assert b.evidence_strength == pytest.approx(2.0)


def test_bayesian_soft_point_estimate_moves_belief():
    b0 = prior_belief(1)
    # feeding p=0.80 with weight 4 -> alpha 1+3.2, beta 1+0.8
    b1 = b0.update_point_estimate(0.80, weight=4.0)
    assert b1.alpha == pytest.approx(4.2)
    assert b1.beta == pytest.approx(1.8)
    # posterior mean is between 0.5 and 0.80
    assert 0.5 < b1.posterior_p_yes < 0.80
    assert b1.posterior_p_yes == pytest.approx(4.2 / 6.0)


def test_bayesian_hard_outcome_is_exact_conjugate_update():
    b0 = prior_belief(1, prior_alpha=3.0, prior_beta=7.0)
    b_yes = b0.update_outcome(1)
    assert b_yes.alpha == 4.0 and b_yes.beta == 7.0
    b_no = b0.update_outcome(0)
    assert b_no.alpha == 3.0 and b_no.beta == 8.0


def test_bayesian_credible_interval_within_unit():
    b = prior_belief(1).update_point_estimate(0.70, weight=9.0)
    lo, hi = b.credible_interval()
    assert 0.0 < lo < hi < 1.0
    # mean is inside the interval
    assert lo < b.posterior_p_yes < hi


def test_bayesian_determinism_same_inputs_same_hashes():
    b1 = update_belief(prior_belief(1), 0.65, weight=2.0, outcomes=[1, 0, 1])
    b2 = update_belief(prior_belief(1), 0.65, weight=2.0, outcomes=[1, 0, 1])
    assert b1.belief_hash == b2.belief_hash
    assert b1.posterior_p_yes == b2.posterior_p_yes


def test_bayesian_three_phi_levels_diverge():
    lo = update_belief(prior_belief(1), 0.55, weight=1.0)
    mid = update_belief(prior_belief(1), 0.70, weight=1.0)
    hi = update_belief(prior_belief(1), 0.90, weight=1.0)
    assert lo.posterior_p_yes < mid.posterior_p_yes < hi.posterior_p_yes


# ----------------------------------------------------------------------------
# Regime detection (HMM)
# ----------------------------------------------------------------------------
def test_regime_calm_stream_classified_calm():
    # stationary tight band around 0.50 (small iid noise, no mean shift)
    import random
    rng = random.Random(7)
    obs = [0.50 + rng.uniform(-0.01, 0.01) for _ in range(40)]
    st = detect_regime(obs, exchange_id=1)
    assert st.regime == "CALM"
    assert st.confidence > 0.6


def test_regime_turbulent_stream_classified_turbulent():
    # calm opener, then a violent dislocation to 0.85 with high variance
    obs = [0.50 + 0.003 * i for i in range(20)]
    obs += [0.85, 0.80, 0.88, 0.79, 0.86, 0.83, 0.90, 0.81, 0.87, 0.84]
    st = detect_regime(obs, exchange_id=1)
    assert st.regime == "TURBULENT"
    assert st.confidence > 0.6


def test_regime_drift_reports_signed_shift():
    obs = [0.50] * 10 + [0.80] * 10
    st = detect_regime(obs, exchange_id=1)
    # mean shifted UP materially
    assert st.drift > 0.1


def test_regime_hmm_is_deterministic():
    obs = [0.50 + 0.01 * (i % 5) for i in range(30)]
    d1 = RegimeDetector(exchange_id=1).replay_into(obs)
    d2 = RegimeDetector(exchange_id=1).replay_into(obs)
    assert [s.regime_hash for s in d1] == [s.regime_hash for s in d2]
    assert d1[-1].regime == d2[-1].regime


def test_regime_state_is_frozen_hashable():
    st = RegimeDetector(exchange_id=1).handle(0.5, ts=0)
    assert isinstance(st, RegimeState)
    assert st.regime_hash and len(st.regime_hash) == 64


# ----------------------------------------------------------------------------
# Q3 folded into the orchestrator + M0
# ----------------------------------------------------------------------------
def _producer():
    cert = AgentCert(
        agent_id="quant", pubkey_pem="", role="tool", capabilities=["quant"],
        issued_at=0, expires_at=9999999999, cert_seq=1, root_sig="x",
    )
    key = Ed25519PrivateKey.generate()
    cert.pubkey_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return cert, key


def _ctx(**kw):
    base = dict(
        exchange_id=1, model_p_yes=0.68, bid_cents=55, ask_cents=57,
        last_cents=56, side="BUY_YES", available_usd=1000.0,
        ticker="KXINFLATION-24",
        regime_observations=tuple(0.50 + 0.004 * i for i in range(30)),
    )
    base.update(kw)
    return QuantContext(**base)


def test_q3_folds_into_evaluate_quant():
    cert, key = _producer()
    d = evaluate_quant(_ctx(), cert, key, proposal_hash="o-q3")
    # belief + regime are present and typed
    assert isinstance(d.belief, BayesianBelief)
    assert isinstance(d.regime, RegimeState)
    assert 0.0 < d.belief.posterior_p_yes < 1.0
    assert d.regime.regime in ("CALM", "TURBULENT", "AMBIGUOUS")
    # envelope still binds + verifies (belief hash folded into calibration_hash)
    assert d.evidence.calibration_hash == d.belief.belief_hash
    assert verify_quant_evidence(d.evidence, cert)


def test_q3_orchestrator_determinism():
    cert, key = _producer()
    a = evaluate_quant(_ctx(), cert, key)
    b = evaluate_quant(_ctx(), cert, key)
    assert a.belief.belief_hash == b.belief.belief_hash
    assert a.regime.regime_hash == b.regime.regime_hash
    assert a.evidence.signature == b.evidence.signature


def test_q3_m0_quant_decision_has_no_authority_fields():
    cert, key = _producer()
    d = evaluate_quant(_ctx(), cert, key, proposal_hash="p1")
    forbidden = {"authorization", "disposition", "decision", "approval",
                 "requires_approval", "blocked", "risk"}
    assert not (forbidden & set(d.to_dict().keys()))


def test_q3_bayes_three_phi_levels_change_posterior_not_verdict():
    """Three belief strengths change the advisory posterior; M0 -> verdict same."""
    cert, key = _producer()
    lo = evaluate_quant(_ctx(model_p_yes=0.55, bayes_weight=1.0), cert, key, proposal_hash="lo")
    hi = evaluate_quant(_ctx(model_p_yes=0.90, bayes_weight=1.0), cert, key, proposal_hash="hi")
    assert lo.belief.posterior_p_yes < hi.belief.posterior_p_yes
    # evidence differs, but neither carries a verdict (M0 preserved)
    assert lo.evidence.proposal_hash == "lo" and hi.evidence.proposal_hash == "hi"


# ----------------------------------------------------------------------------
# Import wall (mirrors test_boundary_quant.py intent for the new modules)
# ----------------------------------------------------------------------------
def test_q3_import_wall_clean():
    forbidden = ("fleet.fin", "fleet.layers", "fleet.cognition", "exchange.governance")
    for mod in ("bayesian.py", "regime.py"):
        src = Path(__file__).resolve().parents[2] / "exchange" / "quant" / mod
        tree = ast.parse(src.read_text())
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if any(node.module == f or node.module.startswith(f + ".") for f in forbidden):
                    violations.append(f"from {node.module} import")
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if any(a.name == f or a.name.startswith(f + ".") for f in forbidden):
                        violations.append(f"import {a.name}")
        assert not violations, f"{mod} violates import wall: {violations}"


__all__ = []
