"""Shadow ledger: positions, cash, and P&L attribution per subaccount.

Hybrid settlement model (per plan §1.6): we track everything sovereignly and hold
NOTHING. This ledger is a *shadow* / attribution layer over pass-through execution to
real venue accounts. No real funds move here — it is an internal double-entry mirror
that lets a desk attribute P&L per subaccount, the way River attributes P&L without
custody.

Binary YES/NO market accounting: a BUY fills at price p (cents) for q contracts =>
cost = p*q cents, long q YES. A SELL at p for q => proceeds = p*q, short q YES.
Realized P&L on a flattening trade = (exit - entry) signed by direction. Unrealized
is marked at the current mid (best bid/ask) when provided.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class PositionSide(str, Enum):
    LONG = "LONG"  # net long YES
    SHORT = "SHORT"  # net short YES
    FLAT = "FLAT"


@dataclass
class Position:
    subaccount_id: str
    exchange_id: int
    net_qty: int = 0  # + long, - short
    avg_price_cents: float = 0.0  # volume-weighted entry (cents)
    realized_cents: int = 0

    @property
    def side(self) -> PositionSide:
        if self.net_qty > 0:
            return PositionSide.LONG
        if self.net_qty < 0:
            return PositionSide.SHORT
        return PositionSide.FLAT

    def apply_fill(self, side, price_cents: int, qty: int) -> None:
        """Update the position for one fill. `side` is the aggressor/exec side."""
        signed = qty if side.value == "BUY" else -qty
        if self.net_qty == 0 or (signed > 0) == (self.net_qty > 0):
            # Increasing or opening: extend the weighted average.
            total = abs(self.net_qty) + qty
            if total == 0:
                self.avg_price_cents = 0.0
            else:
                self.avg_price_cents = (
                    self.avg_price_cents * abs(self.net_qty) + price_cents * qty
                ) / total
            self.net_qty += signed
        else:
            # Reducing/closing/flipping: realize P&L on the closed portion.
            closing = min(qty, abs(self.net_qty))
            if self.net_qty > 0:  # long being reduced by a SELL
                self.realized_cents += int((price_cents - self.avg_price_cents) * closing)
            else:  # short being reduced by a BUY
                self.realized_cents += int((self.avg_price_cents - price_cents) * closing)
            self.net_qty += signed
            if self.net_qty == 0:
                self.avg_price_cents = 0.0
            elif (signed > 0) != (self.net_qty - signed > 0):
                # Flipped through zero: open the new side at this price.
                self.avg_price_cents = price_cents

    def unrealized_cents(self, mark_price_cents: Optional[int]) -> int:
        if mark_price_cents is None or self.net_qty == 0:
            return 0
        if self.net_qty > 0:
            return int((mark_price_cents - self.avg_price_cents) * self.net_qty)
        return int((self.avg_price_cents - mark_price_cents) * (-self.net_qty))


@dataclass
class PnL:
    subaccount_id: str
    realized_cents: int
    unrealized_cents: int
    total_cents: int

    def to_dict(self) -> dict:
        return {
            "subaccount_id": self.subaccount_id,
            "realized_cents": self.realized_cents,
            "unrealized_cents": self.unrealized_cents,
            "total_cents": self.total_cents,
        }


class ShadowLedger:
    """Per-subaccount position + P&L attribution. No custody."""

    def __init__(self) -> None:
        # (subaccount, exchange_id) -> Position
        self._positions: Dict[tuple, Position] = {}
        self._subs: Dict[str, dict] = {}

    def _pos(self, sub: str, exchange_id: int) -> Position:
        key = (sub, exchange_id)
        if key not in self._positions:
            self._positions[key] = Position(subaccount_id=sub, exchange_id=exchange_id)
        return self._positions[key]

    def record_fill(self, sub: str, exchange_id: int, side, price_cents: int, qty: int) -> Position:
        pos = self._pos(sub, exchange_id)
        pos.apply_fill(side, price_cents, qty)
        self._subs.setdefault(sub, {})
        return pos

    def position(self, sub: str, exchange_id: int) -> Position:
        return self._pos(sub, exchange_id)

    def pnl(self, sub: str, marks: Optional[Dict[int, int]] = None) -> PnL:
        marks = marks or {}
        realized = 0
        unrealized = 0
        for (s, ex), pos in self._positions.items():
            if s != sub:
                continue
            realized += pos.realized_cents
            unrealized += pos.unrealized_cents(marks.get(ex))
        return PnL(sub, realized, unrealized, realized + unrealized)

    def subaccounts(self) -> List[str]:
        return sorted(self._subs.keys())
