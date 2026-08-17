"""Market-probability calibration (Layer-1 evidence).

IMPORTANT DISTINCTION: ``fleet/cognition/calibration.py`` calibrates
*evidence/reasoning quality* (persona weights, uncertainty temperature) via
``AlignmentEvent``. That is a different thing from *market-probability*
calibration. This module is the **sibling** that tracks whether
``P_model = 0.70`` predictions actually resolve TRUE ~70% of the time against
real Kalshi settlements. It is domain-specific and does NOT touch
``fleet/cognition``.

Metrics:
    * Brier score — mean squared error of probabilistic forecasts.
    * Reliability — bin predictions, compare empirical frequency to stated prob.
    * Rolling calibration — windowed Brier so drift is visible over time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from fleet.crypto.foundation import canonical_bytes, sha256


@dataclass(frozen=True)
class CalibrationRecord:
    """One realized outcome vs the predicted probability, at settlement."""

    exchange_id: int
    predicted_prob: float     # P_model(Y=1) issued at forecast time
    outcome: int              # 1 if YES resolved true, 0 otherwise
    model_id: str = "unknown"
    ts: int = 0              # settlement timestamp
    cal_hash: str = ""

    def __post_init__(self):
        if self.outcome not in (0, 1):
            raise ValueError("outcome must be 0 or 1")
        if not (0.0 < self.predicted_prob < 1.0):
            raise ValueError("predicted_prob must be in (0,1)")
        if not self.cal_hash:
            object.__setattr__(self, "cal_hash", self.compute_hash())

    def state(self) -> dict:
        return {
            "exchange_id": self.exchange_id,
            "predicted_prob": self.predicted_prob,
            "outcome": self.outcome,
            "model_id": self.model_id,
            "ts": self.ts,
        }

    def compute_hash(self) -> str:
        return sha256(canonical_bytes(self.state()))


def brier_score(records: List[CalibrationRecord]) -> float:
    """Mean squared error of forecasts. 0 = perfect, 1 = worst.

    Brier = (1/N) * Σ (p_i - o_i)^2
    """
    if not records:
        return 0.0
    return sum((r.predicted_prob - r.outcome) ** 2 for r in records) / len(records)


def rolling_brier(records: List[CalibrationRecord], window: int = 50) -> List[float]:
    """Brier score over the last ``window`` records at each step (online view)."""
    out: List[float] = []
    for i in range(1, len(records) + 1):
        chunk = records[max(0, i - window):i]
        out.append(brier_score(chunk))
    return out


def reliability_bins(
    records: List[CalibrationRecord], n_bins: int = 10
) -> List[Tuple[float, float, int]]:
    """For each probability bin, return (bin_center, empirical_freq, count).

    Bin centers are evenly spaced over (0,1). Empirical frequency is the mean
    outcome in that bin. A perfectly calibrated model has freq ≈ bin_center.
    """
    edges = [i / n_bins for i in range(n_bins + 1)]
    bins: List[List[float]] = [[] for _ in range(n_bins)]
    for r in records:
        idx = min(n_bins - 1, int(r.predicted_prob * n_bins))
        bins[idx].append(float(r.outcome))
    result: List[Tuple[float, float, int]] = []
    for i, grp in enumerate(bins):
        center = (edges[i] + edges[i + 1]) / 2.0
        freq = (sum(grp) / len(grp)) if grp else 0.0
        result.append((center, freq, len(grp)))
    return result


def calibration_error(records: List[CalibrationRecord], n_bins: int = 10) -> float:
    """Total calibration error: Σ count_i * |freq_i - center_i| / N.

    Smaller = better calibrated. Penalizes systematic over/under-confidence.
    """
    if not records:
        return 0.0
    rb = reliability_bins(records, n_bins=n_bins)
    total = len(records)
    return sum(count * abs(freq - center) for center, freq, count in rb) / total


__all__ = [
    "CalibrationRecord",
    "brier_score",
    "rolling_brier",
    "reliability_bins",
    "calibration_error",
]
