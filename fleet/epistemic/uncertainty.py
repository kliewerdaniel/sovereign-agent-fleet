"""Minimum-sufficient uncertainty representation (Phase 1).

This object *represents* uncertainty; it performs NO quantitative inference.
There is no Bayesian updating, no distribution framework, no risk mathematics,
no calibration math here. Phase 1 supports exactly three shapes, ratified by the
design:

    * Point(p)            — single probability in (0, 1)
    * Interval(lo, hi)    — credible / confidence interval
    * Entropy(h)          — multi-outcome / information uncertainty

Every shape records optional ``epistemic`` vs ``aleatoric`` components because
only epistemic uncertainty justifies "collect more evidence" (2C-4). The
discriminant is ``kind``. Domain-specific mathematical models (Kelly, VaR,
posterior sampling, ...) are NOT pulled into ``fleet/epistemic/`` — this is the
clean extension point, not an inference engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Uncertainty:
    """A value object representing a claim's uncertainty. No inference."""

    kind: str = "point"              # "point" | "interval" | "entropy"
    p: Optional[float] = None        # Point value
    lo: Optional[float] = None       # Interval low
    hi: Optional[float] = None       # Interval high
    h: Optional[float] = None        # Entropy value
    epistemic: Optional[float] = None     # reducible (model-doesn't-know)
    aleatoric: Optional[float] = None     # inherent (cannot be reduced)

    @classmethod
    def point(cls, p: float, *, epistemic: Optional[float] = None,
              aleatoric: Optional[float] = None) -> "Uncertainty":
        return cls(kind="point", p=float(p), epistemic=epistemic, aleatoric=aleatoric)

    @classmethod
    def interval(cls, lo: float, hi: float, *, epistemic: Optional[float] = None,
                 aleatoric: Optional[float] = None) -> "Uncertainty":
        return cls(kind="interval", lo=float(lo), hi=float(hi),
                   epistemic=epistemic, aleatoric=aleatoric)

    @classmethod
    def entropy(cls, h: float, *, epistemic: Optional[float] = None,
                aleatoric: Optional[float] = None) -> "Uncertainty":
        return cls(kind="entropy", h=float(h), epistemic=epistemic, aleatoric=aleatoric)

    def state(self) -> dict:
        return {
            "kind": self.kind,
            "p": self.p,
            "lo": self.lo,
            "hi": self.hi,
            "h": self.h,
            "epistemic": self.epistemic,
            "aleatoric": self.aleatoric,
        }

    def compute_hash(self) -> str:
        from fleet.crypto.foundation import canonical_bytes, sha256
        return sha256(canonical_bytes(self.state()))
