"""Price-time priority order book for a single instrument.

Binary YES/NO market. BUY orders rest at bid prices; SELL orders rest at ask prices.
Priority is price-then-time (earlier order_id wins ties). Prices are integer cents.
The book is the resting side; the matching engine consumes it. Deterministic.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Dict, List, Optional

from .order import Order, OrderSide


@dataclass(frozen=True)
class BookLevel:
    price_cents: int
    size: int

    def to_dict(self) -> dict:
        return {"price_cents": self.price_cents, "size": self.size}


@dataclass
class BookSnapshot:
    exchange_id: int
    bids: List[BookLevel]  # descending price
    asks: List[BookLevel]  # ascending price

    def to_dict(self) -> dict:
        return {
            "exchange_id": self.exchange_id,
            "bids": [b.to_dict() for b in self.bids],
            "asks": [a.to_dict() for a in self.asks],
        }


class OrderBook:
    """Resting limit orders for one instrument, price-time priority."""

    def __init__(self, exchange_id: int):
        self.exchange_id = exchange_id
        # price_cents -> list of resting orders (FIFO by arrival)
        self._bids: Dict[int, List[Order]] = {}
        self._asks: Dict[int, List[Order]] = {}
        self._seq = 0  # arrival sequence for time priority

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def add(self, order: Order) -> None:
        order.validate()
        # Resting orders are LIMIT-class; price_cents is guaranteed non-None by
        # validate() for every order type the book holds (MARKET never rests).
        price = order.price_cents
        assert price is not None, "resting order must have a price"
        book = self._bids if order.side == OrderSide.BUY else self._asks
        book.setdefault(price, []).append(order)
        # tag for time priority (stable fallback if order_id differs)
        order._seq = self._next_seq()  # type: ignore[attr-defined]

    def best_bid(self) -> Optional[int]:
        return max(self._bids) if self._bids else None

    def best_ask(self) -> Optional[int]:
        return min(self._asks) if self._asks else None

    def remove_filled(self, order: Order) -> None:
        """Drop a fully filled resting order from its book level."""
        if not order.done:
            return
        price = order.price_cents
        assert price is not None, "filled resting order must have a price"
        book = self._bids if order.side == OrderSide.BUY else self._asks
        level = book.get(price)
        if level and order in level:
            level.remove(order)
            if not level:
                del book[price]

    def _set_level(self, side: OrderSide, price: int, orders: List[Order]) -> None:
        """Replace a price level's resting orders (used by the matching engine)."""
        book = self._bids if side == OrderSide.BUY else self._asks
        if orders:
            book[price] = orders
        else:
            book.pop(price, None)

    def snapshot(self) -> BookSnapshot:
        bids = sorted(
            (BookLevel(p, sum(o.remaining for o in os_)) for p, os_ in self._bids.items()),
            key=lambda lvl: -lvl.price_cents,
        )
        asks = sorted(
            (BookLevel(p, sum(o.remaining for o in os_)) for p, os_ in self._asks.items()),
            key=lambda lvl: lvl.price_cents,
        )
        return BookSnapshot(exchange_id=self.exchange_id, bids=bids, asks=asks)

    def depth(self) -> int:
        return sum(len(os_) for os_ in self._bids.values()) + sum(
            len(os_) for os_ in self._asks.values()
        )
