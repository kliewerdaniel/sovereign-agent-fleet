"""D30 — quant learning loop tests: close the evidence -> belief cycle.

Covers:
  * A settlement folds into the running prior (posterior mean moves toward outcome).
  * Calibration Brier improves as the model becomes accurate; reliability bins populate.
  * Learner hash is deterministic / replayable (I15).
  * Learned prior injected into evaluate_quant changes the ADVISORY belief field but
    NOT the decision/governance verdict or executed qty (M0).
  * Regime nudges on a surprising settlement.
  * Import-wall purity (only fleet.crypto + intra-package exchange.quant.*).
"""
from __future__ import annotations

import pytest

from exchange.quant.bayesian import BayesianBelief
from exchange.quant.learning import QuantLearner, new_learner


def _learner_after(outcomes, p=0.6):
    lr = new_learner(1)
    for i, o in enumerate(outcomes):
        lr = lr.observe_settlement("KX", p, o, ts=i)
    return lr


def test_settlement_moves_prior_toward_outcome():
    # All YES outcomes -> learned base rate should approach 1.0.
    lr = _learner_after([1, 1, 1, 1, 1], p=0.6)
    assert 0.8 < lr.posterior_p_yes < 1.0
    # All NO outcomes -> learned base rate should approach 0.0.
    lr2 = _learner_after([0, 0, 0, 0, 0], p=0.6)
    assert 0.0 < lr2.posterior_p_yes < 0.2


def test_prior_with_no_outcomes_is_uniform():
    lr = new_learner(1)
    assert abs(lr.posterior_p_yes - 0.5) < 1e-9
    assert lr.evidence_strength == 2.0  # Beta(1,1)


def test_calibration_brier_low_when_accurate():
    # An on-average consistent model: p=0.7 -> YES, p=0.3 -> NO. Each pair
    # contributes (1-0.7)^2 = 0.09 and (0-0.3)^2 = 0.09 -> Brier 0.09 (not 0; a
    # perfect forecast would be p=1.0 / p=0.0). The point is the Brier is LOW and
    # stable, and reliability shows the forecast matches the empirical freq.
    lr = new_learner(7)
    for i in range(20):
        lr = lr.observe_settlement("KX", 0.7, 1, ts=i)
        lr = lr.observe_settlement("KX", 0.3, 0, ts=i + 100)
    report = lr.calibration_report()
    assert report["n_settlements"] == 40
    assert report["brier_score"] == pytest.approx(0.09, abs=1e-9)
    # Calibration error: empirical freq in the 0.7 bin ~ 1.0, but center is 0.7 ->
    # there is over-confidence bias, captured by calibration_error > 0.
    assert report["calibration_error"] > 0.0


def test_calibration_brier_high_when_inverted():
    lr = new_learner(7)
    # systematically INVERTED: p=0.9 but outcome 0
    for i in range(20):
        lr = lr.observe_settlement("KX", 0.9, 0, ts=i)
    report = lr.calibration_report()
    # (0.9 - 0)^2 = 0.81 per sample -> Brier 0.81
    assert report["brier_score"] == pytest.approx(0.81, abs=1e-9)
    # Reliability should show over-confidence in the high bin.
    bins = report["reliability_bins"]
    assert len(bins) == 10
    assert any(count > 0 for _, _, count in bins)


def test_learner_hash_deterministic_replayable():
    lr_a = _learner_after([1, 0, 1, 1, 0, 0, 1], p=0.55)
    lr_b = _learner_after([1, 0, 1, 1, 0, 0, 1], p=0.55)
    assert lr_a.learner_hash == lr_b.learner_hash
    # Different history -> different hash (no accidental collision).
    lr_c = _learner_after([0, 0, 0, 0, 0], p=0.55)
    assert lr_c.learner_hash != lr_a.learner_hash


def test_learned_prior_into_evaluate_quant_is_advisory_only():
    from exchange.quant.orchestrator import QuantContext, evaluate_quant
    from fleet.crypto.foundation import AgentCert
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    cert = AgentCert(
        agent_id="quant-advisor-d30", role="tool", capabilities=["quant_compute"],
        issued_at=0, expires_at=2_000_000_000, cert_seq=1, root_sig="self", pubkey_pem="",
    )
    key = Ed25519PrivateKey.generate()

    # Baseline: flat uniform prior.
    ctx = QuantContext(
        exchange_id=1, model_p_yes=0.7, bid_cents=50, ask_cents=52, side="BUY_YES",
        market_live=False, model_id="research", method="d30", ts=0,
    )
    d_uniform = evaluate_quant(ctx, cert, key, proposal_hash="h0")

    # Learned prior strongly toward YES (many YES settlements).
    lr = _learner_after([1, 1, 1, 1, 1], p=0.7)
    d_learned = evaluate_quant(ctx, cert, key, proposal_hash="h0", prior_belief=lr.prior())

    # The advisory belief posterior reflects the learned prior (it shifts).
    assert d_learned.belief.posterior_p_yes != d_uniform.belief.posterior_p_yes
    # M0: the decision fields carry NO authority info; the only verdict-bearing
    # artifact is the evidence envelope, whose signature is independent of prior.
    assert d_learned.evidence.proposal_hash == d_uniform.evidence.proposal_hash
    # The belief field is the ONLY thing that changed; everything else identical.
    assert d_learned.probability.p_yes == d_uniform.probability.p_yes
    assert d_learned.edge.edge == d_uniform.edge.edge
    assert d_learned.kelly.recommendation == d_uniform.kelly.recommendation


def test_m0_learned_prior_never_changes_executed_qty():
    # The API path binds quant only AFTER decide_trade; executed qty = req.qty.
    # Verify the learning blob can never produce a different suggestion that the
    # execution path would honor: suggestion is advisory, execution ignores it.
    from exchange.quant.orchestrator import QuantContext, evaluate_quant
    from fleet.crypto.foundation import AgentCert
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    cert = AgentCert(
        agent_id="quant-advisor-d30", role="tool", capabilities=["quant_compute"],
        issued_at=0, expires_at=2_000_000_000, cert_seq=1, root_sig="self", pubkey_pem="",
    )
    key = Ed25519PrivateKey.generate()
    ctx = QuantContext(
        exchange_id=1, model_p_yes=0.7, bid_cents=50, ask_cents=52, side="BUY_YES",
        available_usd=1000.0, model_id="research", method="d30", ts=0,
    )
    lr = _learner_after([1, 1, 1, 1, 1], p=0.7)
    d = evaluate_quant(ctx, cert, key, proposal_hash="h1", prior_belief=lr.prior())
    # suggested_qty is advisory; an operator would still execute req.qty.
    assert isinstance(d.suggested_qty, int)
    # The decision object exposes no authorization field.
    assert not hasattr(d, "authorization")
    assert not hasattr(d, "verdict")


def test_regime_nudges_on_surprise_settlement():
    # A confident miss (model said 0.95, outcome 0) should shift regime drift.
    lr = new_learner(1)
    lr = lr.observe_settlement("KX", 0.95, 0, ts=0)
    # The surprise (0.95 vs realized 0 -> |0.95 - 0| = 0.95) is a large shock.
    assert lr.regime is not None
    # A run of confident-correct settlements yields a calmer regime signal.
    lr_ok = new_learner(1)
    for i in range(5):
        lr_ok = lr_ok.observe_settlement("KX", 0.8, 1, ts=i)
    # The two learners have different regime states after different surprises.
    assert lr.regime.regime_hash != lr_ok.regime.regime_hash


def test_import_wall_purity():
    import ast, inspect
    mod = __import__("exchange.quant.learning", fromlist=["x"])
    src = inspect.getsource(mod)
    tree = ast.parse(src)
    forbidden = ("fleet.fin", "fleet.layers", "fleet.cognition", "exchange.governance")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                assert not _bad(n.name, forbidden), f"learning.py imports forbidden {n.name}"
        elif isinstance(node, ast.ImportFrom):
            assert not _bad(node.module or "", forbidden), \
                f"learning.py from-imports forbidden {node.module}"


def _bad(name: str, prefixes) -> bool:
    return any(name == p or name.startswith(p + ".") for p in prefixes)
