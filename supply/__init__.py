"""Supply-chain / inventory workload (THIRD external domain, M0 stress test).

The third independent consumer of the neutral ``fleet.epistemic`` contract. It is
NEITHER finance (``exchange/``) NOR incident-response (``incident/``) — a different
shape of domain entirely (logistics/operations). Its only job here is to prove
the substrate keeps serving unrelated domains through the identical ``decide()``
without ever learning what "reorder" or "stockout" means.

It shares NO imports with ``exchange/``, ``incident/``, or ``fleet.epistemic``.
The package knows only its own vocabulary and renders it through the adapter.
Three unrelated domains, one untouched substrate: that is the strongest form of
the M0 domain-generality claim.
"""
from __future__ import annotations

from .sim import InventorySignal, ReorderPlan

__all__ = ["InventorySignal", "ReorderPlan"]
