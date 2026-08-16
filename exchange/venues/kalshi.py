"""Kalshi adapter (STUB).

Per the locked scope decision, Kalshi is the first *target* real venue, but the
exchange is built sim-first: this adapter is a STUB that records routed order
intents and (optionally) simulates a deterministic fill. It never touches the
real Kalshi REST API. Wiring to a live Kalshi account (creds + signed requests)
happens in E6+, after the core is proven.

The stub is explicit about liveness so the UI can label it honestly — it always
returns ``RoutingStatus.NOT_LIVE`` for real execution, and the simulated fill
path is clearly fenced behind ``simulate=True``.
"""
from __future__ import annotations

import time
import uuid
from typing import Dict, List, Optional

from .base import (
    NormalizedOrder,
    RouteResult,
    RoutingStatus,
    VenueAdapter,
    VenueFill,
)


class KalshiStub(VenueAdapter):
    name = "kalshi"
    venue = "Kalshi"

    def __init__(self, simulate: bool = True):
        self.simulate = simulate
        self.routed: List[NormalizedOrder] = []
        # venue_order_id -> last status, for cancel()
        self._orders: Dict[str, str] = {}

    def is_live(self) -> bool:
        return False

    def route(self, order: NormalizedOrder) -> RouteResult:
        self.routed.append(order)
        vid = f"kalshi_{uuid.uuid4().hex[:12]}"
        self._orders[vid] = "open"
        fills: List[VenueFill] = []
        detail = "stub: recorded intent only (not live)"
        if self.simulate and order.limit_cents is not None:
            # Deterministic sim fill: full qty at the limit price.
            fills.append(
                VenueFill(
                    venue_order_id=vid,
                    exchange_id=order.exchange_id,
                    price_cents=order.limit_cents,
                    qty=order.qty,
                    side=order.side,
                    ts=time.time(),
                )
            )
            detail = "stub: simulated fill (not live)"
        return RouteResult(
            status=RoutingStatus.NOT_LIVE,
            venue_order_id=vid,
            fills=fills,
            detail=detail,
        )

    def cancel(self, venue_order_id: str) -> RouteResult:
        if venue_order_id in self._orders:
            self._orders[venue_order_id] = "cancelled"
            return RouteResult(status=RoutingStatus.NOT_LIVE, venue_order_id=venue_order_id, detail="stub: cancelled")
        return RouteResult(status=RoutingStatus.REJECTED, detail="unknown venue order id")


__all__ = ["KalshiStub"]
