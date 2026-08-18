"""Grid / energy demand-response simulation objects (domain-specific, NOT epistemic).

Sixth of six domain packages (after ``exchange.quant``, ``incident.sim``,
``supply.sim``, ``hypothesis.sim``, ``mirror.sim``). ``GridSignal`` (a grid-state
observation) and ``GridPlan`` (a proposed balancing action) carry domain
semantics (load_mw, capacity_mw, price, imbalance_pct) that must never reach the
substrate. The adapter renders them into neutral artifacts. They import nothing
from ``fleet.epistemic``, the other five domains, or ``fleet.layers``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class GridSignal:
    """A grid-state observation the demand-response controller makes.

    load_mw / capacity_mw / price / imbalance_pct live here; the substrate never
    reads them — they become opaque Evidence payload.
    """

    signal_id: str
    node_id: str                 # e.g. "substation-7"
    needs_balancing: bool       # domain verdict
    load_mw: float              # current demand, domain-only, never an authority input
    capacity_mw: float          # available supply, domain-only
    imbalance_pct: float        # (load-capacity)/capacity, domain-only
    price: float = 0.0          # $/MWh, domain-only
    method: str = "scada"       # observation method / source

    def __post_init__(self) -> None:
        if self.capacity_mw <= 0.0:
            raise ValueError("capacity_mw must be positive")


@dataclass(frozen=True)
class GridPlan:
    """A proposed balancing action, analogous to the other domains' plans
    (advisory only)."""

    plan_id: str
    node_id: str
    action: str                 # e.g. "shed", "curtail", "hold"
    balancing_priority: int     # 1 (highest) .. 5 (lowest); domain-only
    verification: str           # "VERIFIED" | "ASSERTED" | "HALLUCINATED"
    rationale: str = ""

    KIND: ClassVar[str] = "grid_plan"

    @property
    def recommendation(self) -> str:
        """Neutral classification (not a permission): RUN / HOLD."""
        return "RUN" if self.balancing_priority <= 3 else "HOLD"
