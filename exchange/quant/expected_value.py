"""Expected value for a Kalshi binary contract (Layer-1 evidence).

Kalshi reality (confirmed by research + exchange/feeds.py): binary contracts
settle to $0 / $1 per contract. A MARKET order fills with certainty at the
resting price (you take the ask to buy YES, the bid to sell); a LIMIT order
gives price certainty but carries fill risk. The public API gives you the
crowd's price with no built-in sizing or edge detection — filling that gap is
exactly what this system is for.

    EV = P(win) * payoff - P(loss) * loss - fees - expected_slippage

where for a YES contract bought at price ``c`` (cents, in [1,99]):
    P(win)        = P_model(Y=1)
    payoff         = (100 - c) cents   (you paid c, receive 100 if YES)
    P(loss)        = 1 - P(win)
    loss           = c cents            (you paid c, receive 0 if NO)
    fee            = fee_per_contract   (Kalshi charges a small fee per contract)
    expected_slip  = half_spread * (1 - execution_prob) * sign
                     (limit orders may not fill at the touch; expected adverse
                      fill vs the mid if they do fill)
    exec_prob      = 1.0 for MARKET orders, < 1.0 for LIMIT (fill risk)

The decision engine may REJECT a trade even when the model is right, if EV is
insufficient after costs (the whole point of an edge layer).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fleet.crypto.foundation import canonical_bytes, sha256

from exchange.quant.probability import EdgeEstimate


@dataclass(frozen=True)
class ExpectedValue:
    """Expected value (in cents per contract) of taking the position.

    ``ev_cents`` is the headline. ``edge_cents`` is the raw edge
    (P_model - P_market) expressed in cents; ``net_ev_cents`` is
    ``ev_cents`` after fees + expected slippage. ``positive`` is a convenience
    boolean (net_ev_cents > 0).
    """

    exchange_id: int
    side: str                    # "BUY_YES" | "SELL_YES" (we model YES contracts)
    p_win: float
    fill_price_cents: int
    fee_per_contract_cents: float
    expected_slippage_cents: float
    execution_prob: float
    ev_cents: float
    edge_cents: float
    net_ev_cents: float
    positive: bool
    model_id: str = "unknown"
    ts: int = 0
    ev_hash: str = ""

    def __post_init__(self):
        net = round(self.ev_cents - self.fee_per_contract_cents - self.expected_slippage_cents, 6)
        object.__setattr__(self, "net_ev_cents", net)
        object.__setattr__(self, "positive", net > 0)
        if not self.ev_hash:
            object.__setattr__(self, "ev_hash", self.compute_hash())

    def state(self) -> dict:
        return {
            "exchange_id": self.exchange_id,
            "side": self.side,
            "p_win": self.p_win,
            "fill_price_cents": self.fill_price_cents,
            "fee_per_contract_cents": self.fee_per_contract_cents,
            "expected_slippage_cents": self.expected_slippage_cents,
            "execution_prob": self.execution_prob,
            "ev_cents": self.ev_cents,
            "edge_cents": self.edge_cents,
            "net_ev_cents": self.net_ev_cents,
            "positive": self.positive,
            "model_id": self.model_id,
            "ts": self.ts,
        }

    def compute_hash(self) -> str:
        return sha256(canonical_bytes(self.state()))


def expected_value(
    edge: EdgeEstimate,
    *,
    side: str = "BUY_YES",
    fill_price_cents: int,
    fee_per_contract_cents: float = 0.07,   # Kalshi ~$0.07/contract (capped at 10% of YES price)
    half_spread_cents: float = 1.0,          # resting half-spread on the book
    execution_prob: float = 1.0,             # 1.0 market order, <1 limit order
    model_id: str = "unknown",
    ts: int = 0,
) -> ExpectedValue:
    """Compute EV for a binary YES contract position.

    Args:
        edge: the EdgeEstimate (p_model vs p_market) this EV is built on.
        side: "BUY_YES" (long the YES) or "SELL_YES" (short the YES, i.e. long NO).
        fill_price_cents: the price at which we transact (ask to buy YES,
            bid to sell YES). Must be in [1,99].
        fee_per_contract_cents: Kalshi per-contract fee (default ~0.07¢).
        half_spread_cents: resting half-spread; used for expected slippage on
            limit orders.
        execution_prob: probability the order fills (1.0 for market, <1 limit).
        model_id, ts: provenance.
    """
    if not (1 <= fill_price_cents <= 99):
        raise ValueError(f"fill price must be in [1,99] cents, got {fill_price_cents}")
    if not (0.0 <= execution_prob <= 1.0):
        raise ValueError(f"execution_prob must be in [0,1], got {execution_prob}")

    p_win = edge.p_model if side == "BUY_YES" else (1.0 - edge.p_model)
    c = float(fill_price_cents)

    if side == "BUY_YES":
        payoff = 100.0 - c          # receive 100 if YES
        loss = c                     # lose c if NO
        # expected slippage: if a limit order, adverse fill vs mid when it fills
        exp_slip = half_spread_cents * (1.0 - execution_prob)
    else:  # SELL_YES (long NO): pay c to sell YES, receive 100-c if NO
        payoff = 100.0 - c
        loss = c
        exp_slip = half_spread_cents * (1.0 - execution_prob)

    # Expected value before costs, weighted by execution probability.
    gross_ev = execution_prob * (p_win * payoff - (1.0 - p_win) * loss)
    # Edge in cents: how much the model's probability beats the market mid.
    edge_cents = edge.edge * 100.0

    return ExpectedValue(
        exchange_id=edge.exchange_id,
        side=side,
        p_win=p_win,
        fill_price_cents=fill_price_cents,
        fee_per_contract_cents=fee_per_contract_cents,
        expected_slippage_cents=round(exp_slip, 6),
        execution_prob=execution_prob,
        ev_cents=round(gross_ev, 6),
        edge_cents=round(edge_cents, 6),
        net_ev_cents=round(gross_ev - fee_per_contract_cents - exp_slip, 6),
        positive=(gross_ev - fee_per_contract_cents - exp_slip) > 0,
        model_id=model_id,
        ts=ts,
    )


__all__ = ["ExpectedValue", "expected_value"]
