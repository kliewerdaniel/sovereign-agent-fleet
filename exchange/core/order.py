"""Order primitives for the exchange matching core.

Sides: BUY (long YES) / SELL (short YES). Types: LIMIT, MARKET, plus the
server-managed complex orders (ICEBERG, PEG, TP, SL) defined here but matched
natively as LIMIT/ MARKET by the engine in E1 (algo expansion is E4). Prices are
integer cents (1..99). Quantities are integer contracts.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    # Server-managed complex orders (E4): engine treats the visible peak as a
    # LIMIT/MARKET; the algo layer expands the remainder (see routing/algos.py).
    ICEBERG = "ICEBERG"
    PEG = "PEG"
    TP = "TP"  # take-profit (sell at >= price)
    SL = "SL"  # stop-loss (sell at <= price)


class TimeInForce(str, Enum):
    GTC = "GTC"  # good till cancelled
    GTD = "GTD"  # good till date
    IOC = "IOC"  # immediate or cancel
    FOK = "FOK"  # fill or kill


@dataclass
class Order:
    order_id: str
    exchange_id: int
    side: OrderSide
    order_type: OrderType
    qty: int  # total contracts (peak for iceberg)
    price_cents: Optional[int] = None  # required for LIMIT/ICEBERG/PEG/TP/SL
    time_in_force: TimeInForce = TimeInForce.GTC
    subaccount_id: str = "default"
    # Fill tracking (mutable, engine-managed)
    filled: int = 0
    # Algo fields (E4); ignored by engine for plain LIMIT/MARKET
    peak_qty: Optional[int] = None  # iceberg visible clip
    trigger_cents: Optional[int] = None  # TP/SL trigger
    venue_hint: Optional[str] = None

    @property
    def remaining(self) -> int:
        return max(0, self.qty - self.filled)

    @property
    def done(self) -> bool:
        return self.remaining == 0

    def validate(self) -> None:
        if self.qty <= 0:
            raise ValueError("qty must be positive")
        if self.remaining < 0:
            raise ValueError("overfilled order")
        if self.order_type in (
            OrderType.LIMIT,
            OrderType.ICEBERG,
            OrderType.PEG,
            OrderType.TP,
            OrderType.SL,
        ):
            if self.price_cents is None or not (1 <= self.price_cents <= 99):
                raise ValueError(f"invalid price_cents for {self.order_type}")


def make_limit_order(
    exchange_id: int,
    side: OrderSide,
    qty: int,
    price: float,
    subaccount_id: str = "default",
    time_in_force: TimeInForce = TimeInForce.GTC,
    order_id: Optional[str] = None,
) -> Order:
    """Convenience factory: dollar `price` (0.01..0.99) -> integer cents."""
    from .instrument import cents

    return Order(
        order_id=order_id or f"o_{uuid.uuid4().hex[:12]}",
        exchange_id=exchange_id,
        side=side,
        order_type=OrderType.LIMIT,
        qty=qty,
        price_cents=cents(price),
        time_in_force=time_in_force,
        subaccount_id=subaccount_id,
    )
