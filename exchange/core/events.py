"""Market event bus for the sovereign exchange.

Every observable exchange action (order accepted / rested / filled / rejected,
book level change, heartbeat) is published as a :class:`MarketEvent` onto a
process-local :class:`ExchangeBus`. Streaming transports (SSE, and later WS)
subscribe to the bus and serialize events to clients.

The bus is intentionally in-process and synchronous. For a sovereign venue that
holds nothing and replicates only via signed artifacts, a local publisher is the
honest default; fan-out to remote subscribers happens through the governance/
replication layer, not here.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

from .order import OrderSide


class EventType(str, Enum):
    ORDER_ACCEPTED = "order.accepted"
    ORDER_RESTED = "order.rested"
    ORDER_REJECTED = "order.rejected"
    TRADE = "trade"
    BOOK = "book"  # full book snapshot after a match
    QUOTE = "quote"  # price-discovery quote (sim or live)
    HEARTBEAT = "heartbeat"


@dataclass
class MarketEvent:
    """A single serialized exchange event."""

    type: EventType
    exchange_id: int
    ts: float = field(default_factory=time.time)
    seq: int = 0
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value  # Enum -> str for wire
        return d


# a subscriber receives every published event
Subscriber = Callable[[MarketEvent], None]


class ExchangeBus:
    """Minimal synchronous pub/sub hub over market events."""

    def __init__(self) -> None:
        self._subs: List[Subscriber] = []
        self._seq = 0
        self._history: List[MarketEvent] = []  # bounded replay buffer

    def subscribe(self, sub: Subscriber) -> Callable[[], None]:
        self._subs.append(sub)
        idx = len(self._subs) - 1

        def unsubscribe() -> None:
            if 0 <= idx < len(self._subs):
                self._subs[idx] = lambda _e: None  # tombstone (keeps indices stable)

        return unsubscribe

    def publish(self, event: MarketEvent) -> None:
        self._seq += 1
        event.seq = self._seq
        self._history.append(event)
        if len(self._history) > 4096:
            self._history = self._history[-4096:]
        for sub in self._subs:
            try:
                sub(event)
            except Exception:
                # a misbehaving subscriber must never break the book
                continue

    def last_seq(self) -> int:
        return self._seq

    def replay(self, since_seq: int = 0) -> List[MarketEvent]:
        return [e for e in self._history if e.seq > since_seq]


def _side_str(side: OrderSide) -> str:
    return "BUY" if side == OrderSide.BUY else "SELL"


def trade_event(
    exchange_id: int,
    price_cents: int,
    qty: int,
    taker_side: OrderSide,
    taker_sub: str,
    maker_sub: str,
    taker_order_id: str,
    maker_order_id: str,
) -> MarketEvent:
    return MarketEvent(
        type=EventType.TRADE,
        exchange_id=exchange_id,
        payload={
            "price_cents": price_cents,
            "qty": qty,
            "taker_side": _side_str(taker_side),
            "taker_subaccount": taker_sub,
            "maker_subaccount": maker_sub,
            "taker_order_id": taker_order_id,
            "maker_order_id": maker_order_id,
        },
    )


def make_heartbeat(exchange_id: int) -> MarketEvent:
    return MarketEvent(type=EventType.HEARTBEAT, exchange_id=exchange_id, payload={})


def quote_event(
    exchange_id: int,
    venue: str,
    bid_cents: int,
    ask_cents: int,
    ticker: Optional[str] = None,
    live: bool = False,
) -> MarketEvent:
    """A price-discovery quote (sim or live). Honest about liveness."""
    return MarketEvent(
        type=EventType.QUOTE,
        exchange_id=exchange_id,
        payload={
            "venue": venue,
            "bid_cents": bid_cents,
            "ask_cents": ask_cents,
            "mid_cents": (bid_cents + ask_cents) // 2,
            "ticker": ticker,
            "live": live,
        },
    )


__all__ = [
    "EventType",
    "MarketEvent",
    "ExchangeBus",
    "Subscriber",
    "trade_event",
    "make_heartbeat",
    "quote_event",
]
