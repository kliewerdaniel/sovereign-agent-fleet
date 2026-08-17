"""Supply-chain simulation objects (domain-specific, NOT epistemic).

Mirrors ``exchange.quant`` and ``incident.sim`` in role: domain objects the
substrate has never heard of. ``InventorySignal`` (a derived stockout forecast)
and ``ReorderPlan`` (a proposed replenishment) carry domain semantics
(stockout probability, lead time, reorder point) that must never reach the
substrate. The adapter renders them into neutral artifacts. They import nothing
from ``fleet.epistemic``, ``exchange``, ``incident``, or ``fleet.layers``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class InventorySignal:
    """A domain stockout forecast. stockout_prob and lead_time live here; the
    substrate never reads them — they become opaque Evidence payload."""

    signal_id: str
    sku: str                        # e.g. "SKU-4481"
    is_stockout_risk: bool          # domain verdict
    stockout_prob: float            # 0..1, domain-only, never an authority input
    lead_time_days: int             # domain-only logistics metric
    method: str = "forecast"        # forecasting method / model id

    def __post_init__(self) -> None:
        if not 0.0 <= self.stockout_prob <= 1.0:
            raise ValueError("stockout_prob must be in [0, 1]")


@dataclass(frozen=True)
class ReorderPlan:
    """A proposed replenishment, analogous to KellyProposal / RemediationPlan
    (advisory only)."""

    plan_id: str
    sku: str
    action: str                    # e.g. "reorder", "expedite", "hold"
    reorder_priority: int          # 1 (highest) .. 5 (lowest); domain-only
    verification: str               # "VERIFIED" | "ASSERTED" | "HALLUCINATED"
    rationale: str = ""

    KIND: ClassVar[str] = "reorder_plan"

    @property
    def recommendation(self) -> str:
        """Neutral classification (not a permission): REORDER / HOLD."""
        return "REORDER" if self.reorder_priority <= 3 else "HOLD"
