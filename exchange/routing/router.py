"""Smart order router + basket splitter.

The router is the execution-decision layer that sits between the sovereign
matching engine (internal book) and the external :class:`VenueAdapter`s. Its job
mirrors River Markets' "smart routing / baskets" primitive: given a desired
execution, pick the venue (or split across venues) that minimizes price impact
and maximizes price improvement, without ever holding customer funds.

Key honesty properties:
* Routing is venue-agnostic — it only sees normalized :class:`VenueAdapter`
  quotes. A non-live (stub) adapter is always ranked *last* and flagged.
* A basket is a set of child orders derived from one parent intent; the router
  guarantees the child quantities sum exactly to the parent (no over/under-fill
  at the routing layer).
* The router never signs or approves anything — that is the governance layer's
  job (E5). It only proposes/executes routing legs.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from exchange.core import InstrumentRegistry  # type: ignore
from exchange.venues.base import (
    NormalizedOrder,
    RouteResult,
    RoutingStatus,
    VenueAdapter,
    VenueFill,
)


@dataclass
class VenueQuote:
    """A venue's executable quote for a normalized order (sim or live)."""

    venue: str
    adapter_name: str
    live: bool
    price_cents: Optional[int]
    qty_available: int


@dataclass
class RouteLeg:
    venue: str
    order: NormalizedOrder
    result: Optional[RouteResult] = None


@dataclass
class RoutePlan:
    """A routing decision for a parent intent."""

    parent_order_id: str
    legs: List[RouteLeg] = field(default_factory=list)
    total_routed: int = 0
    price_improvement_cents: int = 0  # vs parent limit (positive = better)
    used_live: bool = False
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "parent_order_id": self.parent_order_id,
            "legs": [
                {
                    "venue": l.venue,
                    "order": l.order.to_dict(),
                    "result": l.result.to_dict() if l.result else None,
                }
                for l in self.legs
            ],
            "total_routed": self.total_routed,
            "price_improvement_cents": self.price_improvement_cents,
            "used_live": self.used_live,
            "note": self.note,
        }


class Router:
    """Picks venues / splits baskets for best execution. Holds nothing."""

    def __init__(
        self,
        adapters: Dict[str, VenueAdapter],
        registry: Optional[InstrumentRegistry] = None,
    ):
        # adapters keyed by venue name
        self.adapters = adapters
        self.registry = registry

    def _with_ticker(self, venue: str, order: NormalizedOrder) -> NormalizedOrder:
        """Resolve the canonical exchange_id -> venue-native ticker (alias map).

        If a registry is wired and the (venue, exchange_id) maps to a known
        instrument, stamp ``venue_ticker`` so the adapter sends a real symbol
        instead of the raw canonical id. Best-effort: never raises; falls back
        to the id when no mapping exists.
        """
        if order.venue_ticker is not None:
            return order
        if self.registry is None:
            return order
        try:
            inst = self.registry.get(order.exchange_id)
        except KeyError:
            return order
        if inst.venue == venue and inst.venue_ticker:
            return NormalizedOrder(
                exchange_id=order.exchange_id,
                side=order.side,
                qty=order.qty,
                limit_cents=order.limit_cents,
                client_order_id=order.client_order_id,
                venue_hint=order.venue_hint,
                venue_ticker=inst.venue_ticker,
            )
        return order

    def quote(self, venue: str, order: NormalizedOrder) -> VenueQuote:
        """Best-effort quote for an order at a venue (sim = simulated fill)."""
        adapter = self.adapters[venue]
        price = order.limit_cents  # stubs simulate at limit
        return VenueQuote(
            venue=venue,
            adapter_name=adapter.name,
            live=adapter.is_live(),
            price_cents=price,
            qty_available=order.qty,
        )

    def rank_venues(self, order: NormalizedOrder) -> List[VenueQuote]:
        """Rank venues best-first by (live, price improvement, name)."""
        quotes = [self.quote(v, order) for v in self.adapters]
        # live venues first; among equal liveness, better price first
        return sorted(
            quotes,
            key=lambda q: (not q.live, -(q.price_cents or 0), q.venue),
        )

    def _split(self, qty: int, n: int) -> List[int]:
        """Split ``qty`` into ``n`` integer parts that sum exactly to ``qty``."""
        if n <= 1 or qty <= 0:
            return [qty]
        base = qty // n
        rem = qty % n
        parts = [base + (1 if i < rem else 0) for i in range(n)]
        return parts

    def route(self, order: NormalizedOrder, basket: bool = False) -> RoutePlan:
        """Route ``order`` to the best venue, or split across venues if ``basket``.

        Guarantees child quantities sum exactly to the parent qty. Prefers live
        venues; falls back to stubs (flagged NOT_LIVE) so the loop never stalls.
        """
        plan = RoutePlan(parent_order_id=order.client_order_id)
        venues = self.rank_venues(order)
        if not venues:
            plan.note = "no venues available"
            return plan

        if basket and len(venues) > 1:
            parts = self._split(order.qty, len(venues))
            for q, v in zip(parts, venues):
                if q <= 0:
                    continue
                child = self._with_ticker(
                    v.venue,
                    NormalizedOrder(
                        exchange_id=order.exchange_id,
                        side=order.side,
                        qty=q,
                        limit_cents=order.limit_cents,
                        venue_hint=v.venue,
                    ),
                )
                res = self.adapters[v.venue].route(child)
                plan.legs.append(RouteLeg(venue=v.venue, order=child, result=res))
                plan.total_routed += q
                if res.status != RoutingStatus.NOT_LIVE:
                    plan.used_live = True
            plan.note = "basket split across venues"
        else:
            best = venues[0]
            routed_order = self._with_ticker(best.venue, order)
            res = self.adapters[best.venue].route(routed_order)
            plan.legs.append(RouteLeg(venue=best.venue, order=routed_order, result=res))
            plan.total_routed = order.qty
            if res.status != RoutingStatus.NOT_LIVE:
                plan.used_live = True
            plan.note = "single-venue" + ("" if best.live else " (stub)")

        # price improvement vs parent limit (only meaningful with a limit)
        if order.limit_cents is not None and plan.legs:
            best_fill = min(
                (f.price_cents for leg in plan.legs if leg.result for f in leg.result.fills),
                default=order.limit_cents,
            )
            plan.price_improvement_cents = order.limit_cents - best_fill
        return plan


__all__ = ["Router", "RoutePlan", "RouteLeg", "VenueQuote"]
