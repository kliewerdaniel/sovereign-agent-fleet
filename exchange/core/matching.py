"""Deterministic price-time matching engine.

Crosses an incoming aggressing order against the resting book. Priority: best price
first, then time (arrival sequence). Produces `Fill`s at the resting (passive) price
(price improvement goes to the aggressor, matching real venue convention). Honors
TimeInForce: GTC rests remainders, IOC cancels remainder, FOK requires full fill.

Guarantees (property-tested in test_matching.py):
  - no order is filled beyond its remaining qty (no negative inventory at the book),
  - a fill price is always <= limit for a BUY and >= limit for a SELL,
  - self-trade prevention: an order never fills against an order of the same
    subaccount (configurable; default on, like real venues).
  - MARKET orders sweep the book at resting prices until exhausted or empty.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from .book import OrderBook
from .events import EventType, ExchangeBus, MarketEvent, trade_event
from .order import Order, OrderSide, OrderType, TimeInForce


@dataclass
class Fill:
    fill_id: str
    exchange_id: int
    price_cents: int
    qty: int
    aggressor_side: OrderSide
    taker_order_id: str
    maker_order_id: str
    taker_subaccount: str
    maker_subaccount: str

    def notional_cents(self) -> int:
        return self.price_cents * self.qty

    def to_dict(self) -> dict:
        return {
            "fill_id": self.fill_id,
            "exchange_id": self.exchange_id,
            "price_cents": self.price_cents,
            "qty": self.qty,
            "aggressor_side": self.aggressor_side.value,
            "taker_order_id": self.taker_order_id,
            "maker_order_id": self.maker_order_id,
            "taker_subaccount": self.taker_subaccount,
            "maker_subaccount": self.maker_subaccount,
        }


@dataclass
class MatchResult:
    fills: List[Fill] = field(default_factory=list)
    rested: bool = False  # True if any quantity was parked on the book
    fully_filled: bool = False

    @property
    def filled_qty(self) -> int:
        return sum(f.qty for f in self.fills)


def _cross_price(aggressor: Order, resting_price: int) -> Optional[int]:
    """Return the execution price if `aggressor` can cross `resting_price`, else None.

    BUY aggressor crosses a resting ASK at/under its limit; SELL aggressor crosses a
    resting BID at/over its limit. Execution is at the passive (resting) price. When
    `resting_price` is None the callers never reach here (level iteration is over
    concrete prices), so we assert non-None.
    """
    assert resting_price is not None
    if aggressor.order_type == OrderType.MARKET:
        return resting_price
    lim = aggressor.price_cents
    if lim is None:
        return None
    if aggressor.side == OrderSide.BUY:
        return resting_price if resting_price <= lim else None
    else:
        return resting_price if resting_price >= lim else None


class MatchingEngine:
    def __init__(self, book: OrderBook, prevent_self_trade: bool = True, bus: Optional[ExchangeBus] = None):
        self.book = book
        self.prevent_self_trade = prevent_self_trade
        self.bus = bus
        self._consumed: dict[str, Order] = {}  # oid -> maker fully consumed in last match()

    def _resting_levels(self, side: OrderSide):
        """Yield (price, level) in priority order for the side the aggressor hits.

        A BUY aggressor hits resting ASKs (ascending price); a SELL aggressor hits
        resting BIDs (descending price).
        """
        if side == OrderSide.SELL:  # aggressor hits the ask book
            return sorted(self.book._asks.items(), key=lambda kv: kv[0])
        return sorted(self.book._bids.items(), key=lambda kv: -kv[0])  # hits the bid book

    def match(self, aggressor: Order) -> MatchResult:
        """Match `aggressor` against the book, mutating both and returning fills.

        The aggressor is the taker; resting orders are makers. Remainders rest on the
        book for GTC; for IOC they are cancelled; FOK requires a full fill or none.
        """
        aggressor.validate()
        result = MatchResult()
        if aggressor.remaining <= 0:
            return result

        # publish accept/reject semantics up front so subscribers see the intent
        if self.bus is not None:
            if aggressor.remaining <= 0:
                self.bus.publish(MarketEvent(
                    type=EventType.ORDER_REJECTED,
                    exchange_id=self.book.exchange_id,
                    payload={"order_id": aggressor.order_id, "reason": "zero_remaining"},
                ))
                return result

        # Snapshot maker filled-counts so a failed FOK can be cleanly rolled back.
        maker_snapshot: dict[str, int] = {}
        counter_side = OrderSide.SELL if aggressor.side == OrderSide.BUY else OrderSide.BUY

        remaining = aggressor.remaining
        for _price, level in self._resting_levels(counter_side):
            if remaining <= 0:
                break
            level.sort(key=lambda o: getattr(o, "_seq", 0))
            still_resting: List[Order] = []
            for resting in list(level):  # copy: remove_filled mutates the book level in place
                if remaining <= 0:
                    still_resting.append(resting)
                    continue
                if self.prevent_self_trade and resting.subaccount_id == aggressor.subaccount_id:
                    still_resting.append(resting)
                    continue
                px = _cross_price(aggressor, resting.price_cents)
                if px is None:
                    still_resting.append(resting)
                    continue
                take = min(remaining, resting.remaining)
                if take <= 0:
                    still_resting.append(resting)
                    continue
                maker_snapshot.setdefault(resting.order_id, resting.filled)
                fill = Fill(
                    fill_id=f"f_{uuid.uuid4().hex[:12]}",
                    exchange_id=self.book.exchange_id,
                    price_cents=px,
                    qty=take,
                    aggressor_side=aggressor.side,
                    taker_order_id=aggressor.order_id,
                    maker_order_id=resting.order_id,
                    taker_subaccount=aggressor.subaccount_id,
                    maker_subaccount=resting.subaccount_id,
                )
                aggressor.filled += take
                resting.filled += take
                remaining = aggressor.remaining
                result.fills.append(fill)
                if self.bus is not None:
                    self.bus.publish(trade_event(
                        exchange_id=self.book.exchange_id,
                        price_cents=px,
                        qty=take,
                        taker_side=aggressor.side,
                        taker_sub=aggressor.subaccount_id,
                        maker_sub=resting.subaccount_id,
                        taker_order_id=aggressor.order_id,
                        maker_order_id=resting.order_id,
                    ))
                if not resting.done:
                    still_resting.append(resting)
                else:
                    self._consumed[resting.order_id] = resting
                    self.book.remove_filled(resting)
            self.book._set_level(counter_side, _price, still_resting)
            if remaining <= 0:
                break

        result.fully_filled = aggressor.done
        tif = aggressor.time_in_force
        if not aggressor.done:
            if tif == TimeInForce.FOK:
                # All-or-nothing: restore maker filled counts AND re-insert any maker
                # that was fully consumed (and thus removed from the book) so the book
                # is exactly as it was before match().
                for oid, filled_before in maker_snapshot.items():
                    maker = self._find_resting(oid)
                    if maker is None:
                        # was removed by remove_filled(); locate the original via the
                        # snapshot by re-deriving from book is impossible, so we keep a
                        # reference list of consumed makers.
                        maker = self._consumed.pop(oid, None)
                    if maker is not None:
                        maker.filled = filled_before
                        if maker.remaining > 0:
                            self.book.add(maker)
                aggressor.filled = 0
                if self.bus is not None:
                    self.bus.publish(MarketEvent(
                        type=EventType.ORDER_REJECTED,
                        exchange_id=self.book.exchange_id,
                        payload={"order_id": aggressor.order_id, "reason": "fok_rolled_back"},
                    ))
                return MatchResult()
            if tif == TimeInForce.IOC:
                if self.bus is not None:
                    self.bus.publish(MarketEvent(
                        type=EventType.ORDER_REJECTED,
                        exchange_id=self.book.exchange_id,
                        payload={"order_id": aggressor.order_id, "reason": "ioc_remainder_cancelled"},
                    ))
                return result
            if aggressor.order_type != OrderType.MARKET:
                self.book.add(aggressor)
                result.rested = True
                if self.bus is not None:
                    self.bus.publish(MarketEvent(
                        type=EventType.ORDER_RESTED,
                        exchange_id=self.book.exchange_id,
                        payload={"order_id": aggressor.order_id, "side": aggressor.side.value},
                    ))
        elif self.bus is not None:
            self.bus.publish(MarketEvent(
                type=EventType.ORDER_ACCEPTED,
                exchange_id=self.book.exchange_id,
                payload={"order_id": aggressor.order_id, "filled": aggressor.filled},
            ))
        if self.bus is not None:
            self.bus.publish(MarketEvent(
                type=EventType.BOOK,
                exchange_id=self.book.exchange_id,
                payload=self.book.snapshot().to_dict(),
            ))
        return result

    def _find_resting(self, order_id: str) -> Optional[Order]:
        for levels in (self.book._bids.values(), self.book._asks.values()):
            for o in levels:
                if o.order_id == order_id:
                    return o
        return None
