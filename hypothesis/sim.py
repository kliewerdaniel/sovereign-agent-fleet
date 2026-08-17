"""Hypothesis / scientific-research simulation objects (domain-specific, NOT epistemic).

Fourth of four mirror domain packages (after ``exchange.quant``, ``incident.sim``,
``supply.sim``). ``HypothesisSignal`` (a derived belief about a hypothesis) and
``ExperimentPlan`` (a proposed experiment to run) carry domain semantics
(p_value, effect_size, confidence) that must never reach the substrate. The
adapter renders them into neutral artifacts. They import nothing from
``fleet.epistemic``, the other three domains, or ``fleet.layers``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class HypothesisSignal:
    """A domain belief about a hypothesis. p_value / effect_size / confidence
    live here; the substrate never reads them — they become opaque Evidence."""

    signal_id: str
    hypothesis_id: str          # e.g. "H3"
    is_supported: bool          # domain verdict
    p_value: float              # 0..1, domain-only, never an authority input
    effect_size: float          # domain-only effect magnitude
    method: str = "analysis"    # analysis method / model id

    def __post_init__(self) -> None:
        if not 0.0 <= self.p_value <= 1.0:
            raise ValueError("p_value must be in [0, 1]")


@dataclass(frozen=True)
class ExperimentPlan:
    """A proposed experiment, analogous to KellyProposal / RemediationPlan /
    ReorderPlan (advisory only)."""

    plan_id: str
    hypothesis_id: str
    action: str                    # e.g. "run_experiment", "publish", "hold"
    experiment_priority: int       # 1 (highest) .. 5 (lowest); domain-only
    verification: str              # "VERIFIED" | "ASSERTED" | "HALLUCINATED"
    rationale: str = ""

    KIND: ClassVar[str] = "experiment_plan"

    @property
    def recommendation(self) -> str:
        """Neutral classification (not a permission): RUN / HOLD."""
        return "RUN" if self.experiment_priority <= 3 else "HOLD"
