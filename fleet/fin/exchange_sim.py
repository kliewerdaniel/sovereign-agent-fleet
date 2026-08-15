"""ExchangeSim — the Layer-3 consequential environment (paper, simulated).

The environment does NOT trust the model. It trusts only the signed
TradeAuthorization and the current account state. ``apply`` performs the four
independent checks described in D27 §13 BEFORE mutating the account; the most
subtle one is the S1/S2 state-binding re-verification: the TA was risk-evaluated
against ``portfolio_pre_hash``; ``apply`` recomputes the live account hash and
refuses if it no longer matches. This defeats a silent transition from the
evaluated state S1 to a different state S2.

Deterministic, pure mutations inside an idempotent commit (the Operator owns the
commit; ExchangeSim owns the validity check + the mutation).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fleet.crypto.foundation import canonical_bytes, sha256
from fleet.fin.authorization import verify_trade_authorization
from fleet.fin.domain import Account, Mandate, MarketData, Side, account_state_hash


@dataclass
class ExecutionReceipt:
    order_id: str
    agent_id: str
    account_id: str
    symbol: str
    side: str
    qty: float
    fill_price: float
    ts: int
    prev_state_hash: str
    new_state_hash: str
    ledger_seq: int
    operator_sig: str
    ok: bool
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id, "agent_id": self.agent_id,
            "account_id": self.account_id, "symbol": self.symbol,
            "side": self.side, "qty": self.qty, "fill_price": self.fill_price,
            "ts": self.ts, "prev_state_hash": self.prev_state_hash,
            "new_state_hash": self.new_state_hash, "ledger_seq": self.ledger_seq,
            "operator_sig": self.operator_sig, "ok": self.ok, "reason": self.reason,
        }


@dataclass
class ApplyResult:
    ok: bool
    refuse_reason: str
    prev_state_hash: str
    new_state_hash: Optional[str]
    receipt: Optional[ExecutionReceipt]


class ExchangeSim:
    """Single paper account, equities/ETFs, LONG-only, MARKET+LIMIT (v1)."""

    def __init__(self, account: Account, market: MarketData, now: int = 0,
                 ledger_seq: int = 0):
        self.account = account
        self.market = market
        self._now = now
        self._seq = ledger_seq

    def _refuse(self, ta, reason: str) -> ApplyResult:
        prev = account_state_hash(self.account)
        return ApplyResult(ok=False, refuse_reason=reason,
                           prev_state_hash=prev, new_state_hash=None, receipt=None)

    def apply(self, ta, operator_cert, operator_key, now: Optional[int] = None) -> ApplyResult:
        """Validate the signed authorization against CURRENT reality, then mutate.

        Returns REFUSE (no mutation) on any failure. This is the Layer-3 trust
        boundary; Operator preflight is usability only.
        """
        now = now if now is not None else self._now

        # (a) verify the TA signature + identity epoch + expiry + nonce
        if not verify_trade_authorization(ta, operator_cert, now):
            return self._refuse(ta, "authorization-invalid-or-expired")

        # (b) state binding (CRITICAL, D27 I7): the TA was risk-evaluated against
        #     portfolio_pre_hash; the live account must still hash to it.
        live_hash = account_state_hash(self.account)
        if live_hash != ta.portfolio_pre_hash:
            return self._refuse(ta, "portfolio-state-mismatch (S1 != S2)")

        # (c) order constraints: asset/size/price re-checked at the boundary
        mkt = self.market
        if ta.symbol != mkt.symbol:
            return self._refuse(ta, "market-symbol-mismatch")
        if ta.side not in ("BUY", "SELL"):
            return self._refuse(ta, "side-not-allowed")
        notional = ta.qty * mkt.last
        if ta.price_constraint.get("type") == "LIMIT":
            ref = float(ta.price_constraint.get("limit", mkt.last))
            band = float(ta.price_constraint.get("band", 0.0))
            if band > 0 and abs(ref - mkt.last) > band * mkt.last:
                return self._refuse(ta, "price-out-of-band")
            if band == 0 and ref != mkt.last:
                return self._refuse(ta, "price-out-of-band")
        side = Side(ta.side)

        # (d) mutate the account (the consequential effect, paper only)
        prev = live_hash
        acc = self.account
        if side == Side.BUY:
            if acc.cash < notional:
                return self._refuse(ta, "insufficient-cash")
            acc.cash -= notional
            pos = acc.positions.get(ta.symbol)
            if pos is None:
                acc.positions[ta.symbol] = _make_position(ta.symbol, ta.qty, mkt.last)
            else:
                total_qty = pos.qty + ta.qty
                pos.avg_price = ((pos.avg_price * pos.qty) + (mkt.last * ta.qty)) / total_qty
                pos.qty = total_qty
        else:  # SELL (only if mandate allows SELL)
            held = acc.positions.get(ta.symbol)
            if held is None or held.qty < ta.qty:
                return self._refuse(ta, "insufficient-holdings")
            realized = (mkt.last - held.avg_price) * ta.qty
            acc.daily_realized_pnl += realized
            acc.cash += notional
            held.qty -= ta.qty
            if held.qty <= 0:
                del acc.positions[ta.symbol]
        acc.orders_today += 1

        self._seq += 1
        new_hash = account_state_hash(acc)
        body = canonical_bytes({
            "order_id": ta.order_hash, "agent_id": ta.agent_id,
            "account_id": ta.account_id, "symbol": ta.symbol, "side": ta.side,
            "qty": ta.qty, "fill_price": mkt.last, "ts": now,
            "prev_state_hash": prev, "new_state_hash": new_hash, "seq": self._seq,
        })
        operator_sig = operator_key.sign(body).hex()
        receipt = ExecutionReceipt(
            order_id=ta.order_hash, agent_id=ta.agent_id, account_id=ta.account_id,
            symbol=ta.symbol, side=ta.side, qty=ta.qty, fill_price=mkt.last,
            ts=now, prev_state_hash=prev, new_state_hash=new_hash,
            ledger_seq=self._seq, operator_sig=operator_sig, ok=True,
        )
        return ApplyResult(ok=True, refuse_reason="", prev_state_hash=prev,
                           new_state_hash=new_hash, receipt=receipt)

    def state_hash(self) -> str:
        return account_state_hash(self.account)


def _make_position(symbol: str, qty: float, price: float):
    from fleet.fin.domain import Position
    return Position(symbol=symbol, qty=qty, avg_price=price, side="BUY")
