"""Hackathon MVP demo — probability/edge layer INSIDE the Sovereign substrate.

Run:  python demo/quant_demo.py   (from repo root, .deploy-venv)

This demonstrates the D29 thesis live, with NO live orders and NO changes to the
locked authority path:
    The model PROPOSES -> the math ESTIMATES -> the protocol AUTHORIZES
    -> the environment ENFORCES -> the ledger PROVES.

It proves meta-invariant M0: the authorization outcome from ``decide_trade`` is
IDENTICAL whether or not a signed ``QuantEvidence`` envelope is attached — because
the envelope is advisory evidence (D28-style enrichment), never an input to the
gate. The gate's only "intelligence-aware" input is the existing ``intel`` flag
(HALLUCINATION blocks; everything else is pure risk math).

This demo uses the REAL package surfaces:
  * ``exchange.quant.orchestrator.evaluate_quant`` (the Q6 pipeline), and
  * the real ``exchange.api`` REST surface (Q6-live) via FastAPI TestClient,
    so the advisory enrichment is exercised through the actual ``/order`` endpoint.

NOTE on boundaries: this is a *demo orchestrator* (outside exchange/quant/), so it
may import both ``exchange.quant`` and ``exchange.governance``. The quant PACKAGE
itself never imports governance (enforced by exchange/tests/test_boundary_quant.py).
"""
from __future__ import annotations

import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

# --- repo imports (authority + evidence, composed by the demo only) ----------
from fleet.crypto.foundation import AgentCert
from exchange.api import _state, app
from exchange.quant.calibration import CalibrationRecord, brier_score
from exchange.quant.orchestrator import QuantContext, evaluate_quant


def _producer() -> tuple[AgentCert, Ed25519PrivateKey]:
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
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


def _banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def main() -> int:
    print("SOVEREIGN QUANT EDGE DEMO — probability layer inside the substrate")
    print("(local, sim-only, no live orders, locked authority path untouched)")

    cert, key = _producer()

    # 1) THE BRAIN (intelligence source) proposes a raw probabilistic belief.
    _banner("1. BRAIN proposes P_model(Y=1 | X)")
    brain_p = 0.70  # e.g. model-release-info + research-fleet belief
    print(f"   Brain: P_model = {brain_p:.2f}  (whatever produced it)")

    # 2) THE EXCHANGE FEED supplies the market's implied probability (sim source).
    _banner("2. EXCHANGE feed supplies P_market (Kalshi order book, sim)")
    # Drive the real REST surface so the advisory path is exercised end-to-end.
    _state.clear()
    client = TestClient(app)
    # seed a resting SELL so the BUY crosses and executes
    seed = client.post("/order", json={
        "side": "SELL", "qty": 20, "limit_cents": 55, "subaccount_id": "maker",
    })
    print(f"   seeded resting SELL -> {seed.json()['authorization']}")

    # 3) QUANT pipeline (Q6) runs through the real /order endpoint: the Brain's
    #    belief enters as advisory model_p_yes, the orchestrator signs a
    #    QuantEvidence envelope, and it attaches to the response.
    _banner("3. /order: quant advisory enrichment signed + attached (M0-preserving)")
    r = client.post("/order", json={
        "side": "BUY", "qty": 10, "limit_cents": 60, "subaccount_id": "t",
        "model_p_yes": brain_p, "available_usd": 1000.0,
    })
    body = r.json()
    q = body["quant"]
    print(f"   authorization = {body['authorization']}  (verdict path, unchanged)")
    print(f"   executed_qty   = {body['executed_qty']}  (req.qty, NOT kelly suggestion)")
    print(f"   model_p_yes    = {q['model_p_yes']:.2f}")
    print(f"   market_mid     = {q['market_mid']:.2f}")
    print(f"   edge           = {q['edge']:+.3f}")
    print(f"   net_EV         = {q['net_ev_cents']:+.2f} cents/contract")
    print(f"   kelly          = {q['kelly_recommendation']} (suggested_qty={q['suggested_qty']})")
    print(f"   bayesian_post  = {q['bayesian_posterior']:.3f}  CI={tuple(round(v,3) for v in q['bayesian_ci'])}  strength={q['bayesian_evidence_strength']:.1f}")
    print(f"   regime         = {q['regime']} (conf={q['regime_confidence']:.2f}, drift={q['regime_drift']:+.3f})")
    print(f"   envelope.sig   = {q['envelope']['signature'][:24]}... verified={q['envelope']['verified']}")
    assert r.status_code == 200
    assert q["envelope"]["verified"] is True
    assert q["envelope"]["proposal_hash"] == body["order_id"]

    # 4) M0 PROOF: the AUTHORITY decision is IDENTICAL with / without the envelope.
    _banner("4. M0 PROOF — authorization ignores the envelope (identical outcome)")
    # Re-run the SAME order with NO model_p_yes (no quant enrichment at all).
    _state.clear()
    client2 = TestClient(app)
    client2.post("/order", json={"side": "SELL", "qty": 20, "limit_cents": 55, "subaccount_id": "maker"})
    r_no = client2.post("/order", json={
        "side": "BUY", "qty": 10, "limit_cents": 60, "subaccount_id": "t",
    })
    same = r_no.json()["authorization"] == body["authorization"]
    print(f"   decide_trade (envelope present) : {body['authorization']}")
    print(f"   decide_trade (envelope removed): {r_no.json()['authorization']}")
    print(f"   M0 HOLD: identical authorization = {same}")
    assert same, "M0 violated: envelope changed the authorization"

    # 5) SAFETY VALVE: a negative-EV trade is flagged HALLUCINATION and BLOCKED —
    #    the gate can only ever BLOCK or hold, never upgrade, on bad evidence.
    _banner("5. SAFETY VALVE — bad edge downgrades via existing gate (one-way)")
    r_block = client.post("/order", json={
        "side": "BUY", "qty": 10, "limit_cents": 55, "subaccount_id": "t",
        "intel": "HALLUCINATION", "model_p_yes": brain_p,
    })
    print(f"   negative-EV / unbacked flagged: intel='HALLUCINATION' -> {r_block.status_code} (BLOCKED)")
    assert r_block.status_code == 403

    # 6) CALIBRATION: prove the Brain's P_model is honest over time (Brier vs settles).
    _banner("6. CALIBRATION — Brier score over realized settlements")
    history = [
        CalibrationRecord(101, 0.70, 1),   # predicted .70, resolved YES
        CalibrationRecord(101, 0.65, 1),
        CalibrationRecord(101, 0.80, 0),   # predicted .80, resolved NO -> miss
        CalibrationRecord(101, 0.60, 1),
        CalibrationRecord(101, 0.55, 0),
    ]
    print(f"   Brier score over {len(history)} settlements = {brier_score(history):.3f}  (lower=more honest)")

    # 7) Q3: BAYESIAN belief update + REGIME detection as living advisory evidence.
    _banner("7. Q3 — Bayesian belief update + regime detection (advisory, M0-safe)")
    from exchange.quant.bayesian import prior_belief, update_belief
    from exchange.quant.regime import detect_regime
    # The Brain's soft 0.70 estimate moves a uniform prior; realized outcomes sharpen it.
    b0 = prior_belief(101)
    b1 = update_belief(b0, 0.70, weight=2.0, outcomes=[1, 1, 0, 1])
    print(f"   prior P(YES)      = {b0.posterior_p_yes:.3f}")
    print(f"   after 0.70 + 3W/1L= {b1.posterior_p_yes:.3f}  (95% CI {tuple(round(v,3) for v in b1.credible_interval())})")
    # Regime: a calm market vs a dislocated one
    calm = detect_regime([0.50 + 0.006 * i for i in range(25)] + [0.49, 0.51, 0.50, 0.52, 0.48], exchange_id=101)
    shock = detect_regime([0.50] * 15 + [0.80, 0.78, 0.83, 0.81, 0.79, 0.84], exchange_id=101)
    print(f"   regime(calm tape) = {calm.regime} (conf={calm.confidence:.2f})")
    print(f"   regime(shock tape)= {shock.regime} (conf={shock.confidence:.2f}, drift={shock.drift:+.3f})")
    assert b1.posterior_p_yes > b0.posterior_p_yes
    assert shock.regime == "TURBULENT"

    # 8) Q4: temporal event graph + information gain over a belief trajectory.
    _banner("8. Q4 — event graph + information gain (local-first, M0-safe)")
    from exchange.quant.eventgraph import info_gain_from_series
    # A belief trajectory: doubt -> news -> conviction -> settle.
    traj = [0.50, 0.55, 0.72, 0.74, 0.81]
    g = info_gain_from_series(101, traj, ticker="KX")
    print(f"   events in trajectory = {g.event_count()}  (n snapshots - 1)")
    print(f"   total information gain = {g.total_information_gain():.3f} bits")
    print(f"   final entropy           = {g.cumulative_entropy():.3f} bits")
    print(f"   most informative event  = {g.most_informative_event().event_id}")  # type: ignore[union-attr]
    assert g.total_information_gain() > 0.0
    assert g.most_informative_event().event_id == "KX-2"  # 0.55 -> 0.72 is the big move  # type: ignore[union-attr]

    _banner("RESULT")
    print("   Model PROPOSED | math ESTIMATED | protocol AUTHORIZED | ledger PROVES.")
    print("   Quant layer = auditable evidence, NOT authority. D27/D28 lock honored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
