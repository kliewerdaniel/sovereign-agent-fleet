"""Deterministic, no-brain trade strategy (D27 baseline / protocol proof).

The point of this module: a trade proposal can be produced WITHOUT any
probabilistic model, and it still flows through the SAME governance
(D16 -> Capability -> Risk -> Approval -> TradeAuthorization -> ExchangeSim ->
Verifier). "The deterministic strategy proves the protocol. The AI strategy
demonstrates the protocol." Neither is authoritative; both are just proposal
sources behind the same boundary.

This strategy is intentionally simple and fully reproducible: given the same
MarketData + Mandate it always returns the same TradeProposal (no randomness,
no model). It is the canonical reference workload for "intelligence source
replaced without changing the authority boundary."
"""
from __future__ import annotations

from typing import Any, Dict

from fleet.fin.domain import Account, Mandate, MarketData, TradeProposal


class DeterministicStrategy:
    """A rule-based strategist that needs no probabilistic brain.

    Rule (illustrative, not investment advice): within the mandate's allowed
    universe, if the last price is at or below ``buy_below`` AND the notional
    would respect ``max_order_usd``, propose a LONG (BUY) sized to the lesser
    of (max_order_usd / price) and (max_position_pct * equity / price).
    Otherwise propose nothing.
    """

    def __init__(self, strategy_id: str = "deterministic-baseline",
                 buy_below: float = float("inf"), confidence: float = 1.0):
        self.strategy_id = strategy_id
        self.buy_below = buy_below
        self.confidence = confidence

    def propose(self, market: MarketData, mandate: Mandate,
                account: Account, evidence_refs: Any = "deterministic") -> Any:
        if market.symbol not in mandate.allowed_assets:
            return None
        if "BUY" not in mandate.allowed_sides:
            return None
        if market.last > self.buy_below:
            return None
        price = market.last
        if price <= 0:
            return None
        equity = account.cash + account.market_value(market)
        max_by_cash = mandate.max_order_usd / price
        max_by_pct = (mandate.max_position_pct * equity) / price
        qty = int(min(max_by_cash, max_by_pct))
        if qty <= 0:
            return None
        return TradeProposal(
            symbol=market.symbol,
            side="BUY",
            qty=float(qty),
            price_constraint={"type": "MARKET"},
            thesis=f"deterministic baseline: last={price} <= buy_below={self.buy_below}",
            confidence=self.confidence,
            evidence_refs=[str(evidence_refs)],
            strategy_id=self.strategy_id,
        )
