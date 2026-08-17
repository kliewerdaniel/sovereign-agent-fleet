"""Regime detection over the probability/edge stream (Q3, Layer-1 evidence).

Q3 part 2: a *deterministic* 2-state hidden Markov model (HMM) over the market
mid-probability, plus a running-drift monitor, that classifies the current
market regime as advisory evidence.

Why a 2-state HMM (calm / turbulent) rather than the 3-state "trend/volatile/
mean-reverting" the original D29 plan floated:

    * A binary HMM stays *exactly* deterministic and hashable with no scipy/numpy
      (the forward pass is two numbers; the stationary/transition math is closed
      form). That satisfies I15 reproducibility without pulling in BLAS.
    * The two regimes (CALM, TURBULENT) are the only ones the advisory layer
      needs: "is this market behaving normally, or is something structurally
      moving?" A 3rd regime adds no information the gate could lawfully use (M0).
    * It is a strict superset of the Q2 anomaly detectors: Page-Hinkley/CUSUM
      catch instantaneous *change points*; the HMM estimates the *persistent*
      regime the stream has settled into. Both are evidence; the regime sits
      above the point anomalies as a summary flag.

The HMM emission model: each regime is a Gaussian on the mid-probability (mean,
std). Given a stream of observations we run the exact 2-state forward pass and
read off the filtered state probability; the more-confident state is the regime.
Drift is measured as the signed change in posterior mean over a window.

BOUNDARY (same wall as the rest of exchange/quant): imports ONLY
``fleet.crypto`` + intra-package modules. Never imports ``fleet.fin``,
``exchange.governance``, ``fleet.layers.*``, or ``fleet.cognition``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from fleet.crypto.foundation import canonical_bytes, sha256

# Numeric floor so log-probabilities never blow up to -inf on exact hits.
_LOG_EPS = -1e9  # log(0) sentinel (we add a tiny floor before logging instead)


def _safe_log(x: float) -> float:
    return math.log(max(1e-300, x))


@dataclass(frozen=True)
class RegimeState:
    """The HMM's view of the market at one observation (filtered belief + regime)."""

    exchange_id: int
    obs: float                  # the mid-probability observed
    p_calm: float               # filtered P(state=CALM | obs so far)
    p_turbulent: float          # filtered P(state=TURBULENT | obs so far)
    regime: str                 # "CALM" | "TURBULENT" | "AMBIGUOUS"
    drift: float                # signed change in posterior mean over the window
    confidence: float           # max(p_calm, p_turbulent) — regime certainty
    ts: int = 0
    regime_hash: str = ""

    def __post_init__(self):
        object.__setattr__(self, "p_calm", float(self.p_calm))
        object.__setattr__(self, "p_turbulent", float(self.p_turbulent))
        object.__setattr__(self, "drift", float(self.drift))
        object.__setattr__(self, "confidence", float(self.confidence))
        if not self.regime_hash:
            object.__setattr__(self, "regime_hash", self.compute_hash())

    def state(self) -> dict:
        return {
            "exchange_id": self.exchange_id,
            "obs": self.obs,
            "p_calm": self.p_calm,
            "p_turbulent": self.p_turbulent,
            "regime": self.regime,
            "drift": self.drift,
            "confidence": self.confidence,
            "ts": self.ts,
        }

    def compute_hash(self) -> str:
        return sha256(canonical_bytes(self.state()))


class RegimeDetector:
    """Deterministic 2-state HMM over the mid-probability stream.

    States: CALM (low variance, near the long-run mean) and TURBULENT (high
    variance / displaced mean). The forward pass is exact; everything is
    reproducible from the ordered observation sequence + constructor params.

    Determinism note: ``rng`` is accepted ONLY for optional *synthetic* regime
    simulation (tests). Production uses ``handle`` with real observations and
    never seeds randomness into the state — the detector itself is pure.
    """

    def __init__(
        self,
        exchange_id: int = 1,
        *,
        # emission models (Gaussian on mid-prob)
        calm_mean: float = 0.50,
        calm_std: float = 0.03,
        turbulent_mean: float = 0.50,
        turbulent_std: float = 0.18,
        # transition matrix (row = from-state, col = to-state); stationary-ish
        trans_calm_to_calm: float = 0.95,
        trans_turb_to_turb: float = 0.90,
        # priors over the starting state
        p_start_calm: float = 0.85,
        # drift window for the signed-mean-change monitor
        drift_window: int = 20,
        # confidence floor below which the regime is reported AMBIGUOUS
        ambiguous_below: float = 0.60,
        model_id: str = "hmm-2state",
    ):
        self.exchange_id = exchange_id
        self.calm_mean = calm_mean
        self.calm_std = max(1e-3, calm_std)
        self.turbulent_mean = turbulent_mean
        self.turbulent_std = max(1e-3, turbulent_std)
        self.tc_calm = max(0.0, min(1.0, trans_calm_to_calm))
        self.tt_turb = max(0.0, min(1.0, trans_turb_to_turb))
        self.p_start_calm = max(0.0, min(1.0, p_start_calm))
        self.drift_window = max(1, drift_window)
        self.ambiguous_below = max(0.0, min(1.0, ambiguous_below))
        self.model_id = model_id
        # forward-pass running state
        self._alpha_calm = self.p_start_calm
        self._alpha_turb = 1.0 - self.p_start_calm
        self._recent_means: List[float] = []
        self._recent_raw: List[float] = []
        self._last_regime: Optional[RegimeState] = None

    # -- emission log-prob (Gaussian) ---------------------------------------
    def _log_emission(self, state: str, x: float) -> float:
        mean = self.calm_mean if state == "CALM" else self.turbulent_mean
        std = self.calm_std if state == "CALM" else self.turbulent_std
        z = (x - mean) / std
        # log N(x|mean,std) = -0.5*(ln(2pi)+ln(std^2)+z^2)
        return -0.5 * (math.log(2.0 * math.pi) + 2.0 * math.log(std) + z * z)

    # -- exact 2-state forward step -----------------------------------------
    def handle(self, x: float, ts: int = 0) -> RegimeState:
        """Fold one observation ``x`` (mid-probability) and return the regime state."""
        lc = self._log_emission("CALM", x)
        lt = self._log_emission("TURBULENT", x)
        # predict: propagate the previous filtered state through the transition matrix
        pred_calm = (
            self._alpha_calm * self.tc_calm
            + self._alpha_turb * (1.0 - self.tt_turb)
        )
        pred_turb = (
            self._alpha_turb * self.tt_turb
            + self._alpha_calm * (1.0 - self.tc_calm)
        )
        # update (forward): multiply by emission then normalize in log space
        log_numer_calm = _safe_log(pred_calm) + lc
        log_numer_turb = _safe_log(pred_turb) + lt
        m = max(log_numer_calm, log_numer_turb)
        denom = math.exp(log_numer_calm - m) + math.exp(log_numer_turb - m)
        self._alpha_calm = math.exp(log_numer_calm - m) / denom
        self._alpha_turb = math.exp(log_numer_turb - m) / denom

        p_calm = self._alpha_calm
        p_turb = self._alpha_turb
        confidence = max(p_calm, p_turb)
        regime = (
            "AMBIGUOUS" if confidence < self.ambiguous_below
            else ("CALM" if p_calm >= p_turb else "TURBULENT")
        )
        # drift monitor: signed change in the LOCAL market level (raw mid-prob)
        # over the window. We track the raw observation mean (not the
        # emission-weighted posterior mean, which is pinned at the emission
        # means) so a shift in the actual market price is reported regardless of
        # which regime's variance explains it.
        raw_window_mean = self._recent_raw[0] if self._recent_raw else x
        self._recent_raw.append(x)
        if len(self._recent_raw) > self.drift_window:
            self._recent_raw.pop(0)
        drift = x - raw_window_mean

        st = RegimeState(
            exchange_id=self.exchange_id,
            obs=x,
            p_calm=p_calm,
            p_turbulent=p_turb,
            regime=regime,
            drift=drift,
            confidence=confidence,
            ts=ts,
        )
        self._last_regime = st
        return st

    def replay_into(self, observations: List[float]) -> List[RegimeState]:
        out: List[RegimeState] = []
        for i, x in enumerate(observations):
            out.append(self.handle(x, ts=i))
        return out

    def latest(self) -> Optional[RegimeState]:
        return self._last_regime

    def state(self) -> dict:
        """Deterministic provenance snapshot (hashable Layer-1 evidence)."""
        return {
            "exchange_id": self.exchange_id,
            "calm_mean": self.calm_mean,
            "calm_std": self.calm_std,
            "turbulent_mean": self.turbulent_mean,
            "turbulent_std": self.turbulent_std,
            "tc_calm": self.tc_calm,
            "tt_turb": self.tt_turb,
            "p_start_calm": self.p_start_calm,
            "drift_window": self.drift_window,
            "ambiguous_below": self.ambiguous_below,
            "alpha_calm": self._alpha_calm,
            "alpha_turb": self._alpha_turb,
            "recent_means": list(self._recent_means),
            "recent_raw": list(self._recent_raw),
            "model_id": self.model_id,
        }

    def compute_hash(self) -> str:
        return sha256(canonical_bytes(self.state()))


def detect_regime(
    observations: List[float],
    *,
    exchange_id: int = 1,
    ts: int = 0,
    **kw,
) -> RegimeState:
    """Convenience: run a fresh detector over a full observation list, return the final regime."""
    det = RegimeDetector(exchange_id=exchange_id, **kw)
    states = det.replay_into(observations)
    return states[-1] if states else det.handle(observations[0] if observations else 0.5)


__all__ = [
    "RegimeState",
    "RegimeDetector",
    "detect_regime",
]
