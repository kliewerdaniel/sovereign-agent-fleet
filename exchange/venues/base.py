"""Venue adapter abstraction.

A :class:`VenueAdapter` is the sovereign exchange's pluggable bridge to an
external execution venue (Kalshi, Polymarket, Crypto.com, ...). The exchange
CORE never talks to a venue directly — routing passes normalized orders to an
adapter, which translates them to the venue's wire format and returns
normalized fills.

Per the River-Markets thesis, the sovereign venue holds NOTHING: we are the
aggregator and our internal ledger is the source of truth for P&L/positions.
The adapter is a pass-through execution leg to the venue's account, which
retains custody of funds. Every adapter call is normalized so the matching
engine, shadow ledger, and governance layer stay venue-agnostic.

This module is honest about liveness: adapters declare ``live`` via
``is_live()``; a stub adapter returns ``False`` and records intents instead of
executing.
"""
from __future__ import annotations

import abc
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class RoutingStatus(str, Enum):
    ROUTED = "routed"          # accepted by the venue (real or simulated)
    REJECTED = "rejected"
    PENDING = "pending"
    NOT_LIVE = "not_live"      # adapter is a stub and records only


@dataclass
class VenueFill:
    venue_order_id: str
    exchange_id: int
    price_cents: int
    qty: int
    side: str
    ts: float = field(default_factory=lambda: __import__("time").time())


@dataclass
class RouteResult:
    status: RoutingStatus
    venue_order_id: Optional[str] = None
    fills: List[VenueFill] = field(default_factory=list)
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "venue_order_id": self.venue_order_id,
            "fills": [vars(f) for f in self.fills],
            "detail": self.detail,
        }


@dataclass
class NormalizedOrder:
    """Venue-neutral order shape handed to an adapter."""

    exchange_id: int
    side: str  # "BUY"/"SELL"
    qty: int
    limit_cents: Optional[int]
    client_order_id: str = field(default_factory=lambda: f"c_{uuid.uuid4().hex[:12]}")
    venue_hint: Optional[str] = None
    # Resolved venue-native symbol (alias) for THIS venue, set by the router from
    # the InstrumentRegistry. Lets adapters like KalshiLive send a real ticker
    # instead of the canonical exchange_id. None => adapter falls back to id.
    venue_ticker: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "exchange_id": self.exchange_id,
            "side": self.side,
            "qty": self.qty,
            "limit_cents": self.limit_cents,
            "client_order_id": self.client_order_id,
            "venue_hint": self.venue_hint,
            "venue_ticker": self.venue_ticker,
        }


class VenueAdapter(abc.ABC):
    """Pluggable execution leg to one external venue."""

    name: str = "abstract"
    venue: str = "abstract"

    @abc.abstractmethod
    def is_live(self) -> bool:
        """True only when this adapter talks to a real, credentialed venue."""

    @abc.abstractmethod
    def route(self, order: NormalizedOrder) -> RouteResult:
        """Translate and send ``order`` to the venue. Returns normalized result."""

    @abc.abstractmethod
    def cancel(self, venue_order_id: str) -> RouteResult:
        """Cancel a previously routed order."""


__all__ = [
    "VenueAdapter",
    "VenueFill",
    "RouteResult",
    "NormalizedOrder",
    "RoutingStatus",
]
