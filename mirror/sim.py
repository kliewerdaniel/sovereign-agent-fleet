"""Mirror / agent self-observability simulation objects (domain-specific, NOT epistemic).

Fifth of five mirror domain packages (after ``exchange.quant``, ``incident.sim``,
``supply.sim``, ``hypothesis.sim``). ``MirrorSignal`` (a self-health observation)
and ``SelfTunePlan`` (a proposed self-tuning action) carry domain semantics
(cpu_load, error_rate, queue_depth, tune_priority) that must never reach the
substrate. The adapter renders them into neutral artifacts. They import nothing
from ``fleet.epistemic``, the other four domains, or ``fleet.layers``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class MirrorSignal:
    """A self-health observation an agent makes about itself.

    cpu_load / error_rate / queue_depth live here; the substrate never reads
    them — they become opaque Evidence payload.
    """

    signal_id: str
    agent_id: str                # e.g. "brain-gemma", "secops-1"
    needs_tuning: bool          # domain verdict
    cpu_load: float             # 0..1, domain-only, never an authority input
    error_rate: float           # 0..1, domain-only
    queue_depth: int           # domain-only backlog
    method: str = "telemetry"   # observation method / source


@dataclass(frozen=True)
class SelfTunePlan:
    """A proposed self-tuning action, analogous to the other domains' plans
    (advisory only)."""

    plan_id: str
    agent_id: str
    action: str                 # e.g. "self_tune", "throttle", "restart_module"
    tune_priority: int          # 1 (highest) .. 5 (lowest); domain-only
    verification: str           # "VERIFIED" | "ASSERTED" | "HALLUCINATED"
    rationale: str = ""

    KIND: ClassVar[str] = "self_tune_plan"

    @property
    def recommendation(self) -> str:
        """Neutral classification (not a permission): RUN / HOLD."""
        return "RUN" if self.tune_priority <= 3 else "HOLD"
