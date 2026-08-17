"""Belief — an epistemic assertion concerning a Proposition.

A Belief interprets evidence under a model for a specific proposition. It may
carry a probability as *epistemic content*, but that probability is NEVER an
authorization directive: Belief has no capability, no authority, no risk budget,
no trading permission, no execution instruction. The governance surface that
consumes it later treats the probability only as deterministic-math input.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, List, Optional

from .artifact import Artifact
from .proposition import Proposition
from .uncertainty import Uncertainty


@dataclass(frozen=True)
class Belief(Artifact):
    """An epistemic assertion about a Proposition, with uncertainty + lineage."""

    KIND: ClassVar[str] = "belief"

    # Required semantics; defaulted only to satisfy dataclass field ordering,
    # then enforced non-None in __post_init__.
    proposition: Optional[Proposition] = None
    estimate: Optional[Uncertainty] = None
    evidence_refs: List[str] = field(default_factory=list)
    model_id: str = "unknown"        # which intelligence source (NOT a capability)
    method: str = "unspecified"      # mathematical method used

    def __post_init__(self) -> None:
        if self.proposition is None or self.estimate is None:
            raise ValueError("Belief requires a proposition and an estimate")
        super().__post_init__()

    def state(self) -> dict:  # type: ignore[override]
        return {
            **super().state(),
            "proposition": self.proposition.state(),
            "estimate": self.estimate.state(),
            "evidence_refs": self.evidence_refs,
            "model_id": self.model_id,
            "method": self.method,
        }
