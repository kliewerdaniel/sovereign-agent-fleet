"""Quant learning loop — close the evidence -> belief cycle (D30).

D29 built the quant layer as a *stateless* per-request estimator: every call starts
from a flat uniform prior and combines the incoming ``model_p_yes`` with market quotes.
That forgets everything between requests. This module makes the layer *learn*: as Kalshi
markets settle, the realized outcomes (0/1) are hard Bernoulli evidence about the true
base rate of ``P_model(Y=1)``. Folding them into a running prior turns a point-estimate
mirror into a *calibrated belief* that carries historical performance.

The loop: forecast -> settlement -> updated belief -> better next forecast.

Design (see docs/planning/D30-quant-learning-loop.md):
  * ADR-D30-1  learner is ADVISORY ONLY (M0) — never changes a verdict or executed qty.
  * ADR-D30-2  reuse D29's exact conjugate Beta-Bernoulli algebra (no new math).
  * ADR-D30-3  settlements use the CalibrationRecord shape (reuse D29 calibration.py).
  * ADR-D30-4  learner state is explicit + opt-in on Exchange.
  * ADR-D30-5  deterministic + hashable (replayable, I15).
  * ADR-D30-6  REST surface can never break the order path.

BOUNDARY (same wall as the rest of exchange/quant): imports ONLY ``fleet.crypto``,
intra-package ``exchange.quant.*`` (bayesian, calibration, regime), and ``dataclasses``.
Never imports ``fleet.fin``, ``exchange.governance``, ``fleet.layers.*``,
``fleet.cognition``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

from fleet.crypto.foundation import canonical_bytes, sha256

from exchange.quant.bayesian import BayesianBelief, prior_belief
from exchange.quant.calibration import CalibrationRecord, brier_score, calibration_error, reliability_bins, rolling_brier
from exchange.quant.regime import RegimeDetector, RegimeState

# Regime drift monitor folded in per settlement (ADR-D30-2 sibling: reuses D29 regime.py).
_REGIME_AMBIGUOUS_BELOW = 0.5


@dataclass(frozen=True)
class QuantLearner:
    """A replayable running learned prior + calibration ledger for one exchange.

    ``alpha``/``beta`` are the accumulated conjugate posterior from every observed
    settlement + soft forecast. ``records`` is the calibration history (one entry per
    observed settlement) so the operator can read Brier / reliability. ``regime`` is the
    latest regime state folded from settlement surprises.
    """

    exchange_id: int
    alpha: float
    beta: float
    prior_alpha: float = 1.0
    prior_beta: float = 1.0
    model_id: str = "unknown"
    ts: int = 0
    records: Tuple[CalibrationRecord, ...] = field(default_factory=tuple)
    regime: "RegimeState" = field(default_factory=lambda: RegimeState(  # type: ignore[call-arg]
        exchange_id=0, obs=0.5, p_calm=0.5, p_turbulent=0.5, regime="AMBIGUOUS",
        drift=0.0, confidence=0.0,
    ))
    learner_hash: str = ""

    def __post_init__(self):
        object.__setattr__(self, "alpha", float(self.alpha))
        object.__setattr__(self, "beta", float(self.beta))
        object.__setattr__(self, "prior_alpha", float(self.prior_alpha))
        object.__setattr__(self, "prior_beta", float(self.prior_beta))
        if not self.learner_hash:
            object.__setattr__(self, "learner_hash", self.compute_hash())

    # -- summaries ------------------------------------------------------------
    @property
    def posterior_p_yes(self) -> float:
        """Learned base-rate belief = alpha / (alpha + beta)."""
        if self.alpha + self.beta <= 0.0:
            return 0.5
        return self.alpha / (self.alpha + self.beta)

    @property
    def evidence_strength(self) -> float:
        """Total pseudo-count mass = how much settlement evidence the belief rests on."""
        return self.alpha + self.beta

    def prior(self) -> BayesianBelief:
        """The running learned belief as a ``BayesianBelief`` for ``evaluate_quant``."""
        return BayesianBelief(
            exchange_id=self.exchange_id,
            alpha=self.alpha,
            beta=self.beta,
            prior_alpha=self.prior_alpha,
            prior_beta=self.prior_beta,
            method="beta_bernoulli_learned",
            model_id=self.model_id,
            ts=self.ts,
        )

    def calibration_report(self) -> dict:
        """Brier + reliability snapshot over the observed settlement history."""
        recs = list(self.records)
        return {
            "exchange_id": self.exchange_id,
            "n_settlements": len(recs),
            "brier_score": brier_score(recs),
            "calibration_error": calibration_error(recs),
            "last_rolling_brier": rolling_brier(recs)[-1] if recs else 0.0,
            "reliability_bins": [
                (round(center, 3), round(freq, 3), count)
                for center, freq, count in reliability_bins(recs)
            ],
            "learned_p_yes": _round(self.posterior_p_yes),
            "evidence_strength": self.evidence_strength,
        }

    # -- mutation (pure, returns a new frozen learner) ------------------------
    def observe_settlement(
        self,
        ticker: str,
        model_p_yes: float,
        outcome: int,
        *,
        ts: int = 0,
    ) -> "QuantLearner":
        """Fold one realized Kalshi settlement into the running belief.

        * The outcome is a hard Bernoulli draw -> exact conjugate update (alpha += o,
          beta += 1 - o) reusing ``BayesianBelief.update_outcome`` (ADR-D30-2).
        * The forecast ``model_p_yes`` (soft) is appended to the calibration ledger as a
          ``CalibrationRecord`` (ADR-D30-3).
        * A *surprise* (|model_p_yes - outcome| large) nudges the regime monitor: a model
          that was confidently wrong implies TURBULENT evidence quality (ADR-D30-6 sibling).
        """
        if outcome not in (0, 1):
            raise ValueError("outcome must be 0 or 1")
        if not (0.0 < model_p_yes < 1.0):
            raise ValueError("model_p_yes must be in (0,1)")

        # Exact conjugate update on the running belief.
        belief = self.prior().update_outcome(outcome, ts=ts)

        # Calibration ledger entry.
        rec = CalibrationRecord(
            exchange_id=self.exchange_id,
            predicted_prob=float(model_p_yes),
            outcome=int(outcome),
            model_id=self.model_id,
            ts=ts,
        )

        # Regime fold-in: feed the model's surprise (forecast error) as a stream point.
        # A confident miss widens the surprise -> the detector leans TURBULENT.
        surprise = abs(model_p_yes - (1.0 if outcome == 1 else 0.0))
        detector = RegimeDetector(exchange_id=self.exchange_id)
        # Seed the detector with the current regime's calibration point then the surprise.
        detector.handle(self.posterior_p_yes, ts=ts)
        new_regime = detector.handle(surprise, ts=ts)

        return QuantLearner(
            exchange_id=self.exchange_id,
            alpha=belief.alpha,
            beta=belief.beta,
            prior_alpha=self.prior_alpha,
            prior_beta=self.prior_beta,
            model_id=self.model_id,
            ts=ts,
            records=self.records + (rec,),
            regime=new_regime,
        )

    # -- provenance -----------------------------------------------------------
    def state(self) -> dict:
        return {
            "exchange_id": self.exchange_id,
            "alpha": self.alpha,
            "beta": self.beta,
            "prior_alpha": self.prior_alpha,
            "prior_beta": self.prior_beta,
            "model_id": self.model_id,
            "ts": self.ts,
            "records": [r.state() for r in self.records],
            "regime_hash": self.regime.regime_hash,
        }

    def compute_hash(self) -> str:
        return sha256(canonical_bytes(self.state()))


def new_learner(
    exchange_id: int,
    *,
    model_id: str = "unknown",
    prior_alpha: float = 1.0,
    prior_beta: float = 1.0,
    ts: int = 0,
) -> QuantLearner:
    """Create an empty learner (uniform prior, no settlements yet)."""
    return QuantLearner(
        exchange_id=exchange_id,
        alpha=prior_alpha,
        beta=prior_beta,
        prior_alpha=prior_alpha,
        prior_beta=prior_beta,
        model_id=model_id,
        ts=ts,
    )


def _round(x: float, n: int = 6) -> float:
    return round(float(x), n)


__all__ = [
    "QuantLearner",
    "new_learner",
]
