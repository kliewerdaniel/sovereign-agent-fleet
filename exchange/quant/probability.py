"""Core probability / edge / expected-value records (Layer-1 evidence).

Every record follows the repo's provenance convention: a ``state()`` dict
(signed-exclusion of ``signature``), a ``compute_hash()`` pairing
``sha256(canonical_bytes(state()))`` (the same primitive ``fleet/fin/domain.py::
MarketData`` uses), and a frozen, hashable shape.

Central object for Kalshi binary YES/NO contracts:

    Edge = P_model(Y=1 | X) - P_market

where ``P_market`` is the Kalshi implied probability extracted from the order
book (yes_bid/yes_ask midpoint, or last trade). ``fleet/fin/domain.py`` does
NOT compute any of this today — its ``RiskLayer`` reasons about position /
exposure / cash limits on an *already-decided* trade, not about whether the
trade has positive expected edge in the first place. That gap is what this
module fills.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from fleet.crypto.foundation import canonical_bytes, sha256

# Probability bounds for a binary contract probability (0..1, never exactly
# 0 or 1 — an excluded outcome would break EV/entropy math and is a model bug).
_PROB_EPS = 1e-9


def _clamp_prob(p: float) -> float:
    """Clamp a probability into (0, 1) open interval; refuse degenerate values."""
    if not (0.0 < p < 1.0):
        # Allow exact 0/1 only if already at the epsilon boundary (numeric noise).
        if p <= 0.0:
            return _PROB_EPS
        if p >= 1.0:
            return 1.0 - _PROB_EPS
    return float(p)


@dataclass(frozen=True)
class ProbabilityEstimate:
    """P_model(Y=1 | X) — the model's calibrated probability the event occurs.

    This is the *model's* probability. It is produced by whatever intelligence
    source (research fleet, model release info, news, Reddit) — this module
    only records it, types it, and hashes it. It is evidence, never authority.
    """

    exchange_id: int
    p_yes: float                 # P_model(Y=1) in (0,1)
    uncertainty: float = 0.0     # model-reported epistemic uncertainty, >= 0
    model_id: str = "unknown"
    method: str = "unspecified"  # mathematical method used to derive p_yes
    ts: int = 0
    p_hash: str = ""

    def __post_init__(self):
        # frozen dataclass -> use object.__setattr__ for computed fields
        p = _clamp_prob(self.p_yes)
        object.__setattr__(self, "p_yes", p)
        object.__setattr__(self, "uncertainty", max(0.0, float(self.uncertainty)))
        if not self.p_hash:
            object.__setattr__(self, "p_hash", self.compute_hash())

    def state(self) -> dict:
        return {
            "exchange_id": self.exchange_id,
            "p_yes": self.p_yes,
            "uncertainty": self.uncertainty,
            "model_id": self.model_id,
            "method": self.method,
            "ts": self.ts,
        }

    def compute_hash(self) -> str:
        return sha256(canonical_bytes(self.state()))


@dataclass(frozen=True)
class MarketProbability:
    """P_market — the crowd's implied probability from the Kalshi order book.

    Derived from a ``Quote`` (yes_bid/yes_ask in cents). ``mid_prob`` is the
    fair mid; ``last_prob`` uses the last trade when available. All in (0,1).
    """

    exchange_id: int
    mid_prob: float              # (yes_bid + yes_ask) / 2  in (0,1)
    bid_prob: float
    ask_prob: float
    last_prob: Optional[float] = None
    venue: str = "kalshi"
    live: bool = False
    ticker: Optional[str] = None
    ts: int = 0
    mp_hash: str = ""

    def __post_init__(self):
        object.__setattr__(self, "mid_prob", _clamp_prob(self.mid_prob))
        object.__setattr__(self, "bid_prob", _clamp_prob(self.bid_prob))
        object.__setattr__(self, "ask_prob", _clamp_prob(self.ask_prob))
        if self.last_prob is not None:
            object.__setattr__(self, "last_prob", _clamp_prob(self.last_prob))
        if not self.mp_hash:
            object.__setattr__(self, "mp_hash", self.compute_hash())

    def state(self) -> dict:
        return {
            "exchange_id": self.exchange_id,
            "mid_prob": self.mid_prob,
            "bid_prob": self.bid_prob,
            "ask_prob": self.ask_prob,
            "last_prob": self.last_prob,
            "venue": self.venue,
            "live": self.live,
            "ticker": self.ticker,
            "ts": self.ts,
        }

    def compute_hash(self) -> str:
        return sha256(canonical_bytes(self.state()))


@dataclass(frozen=True)
class EdgeEstimate:
    """Edge = P_model - P_market (the central opportunity object).

    Sign matters: positive edge means the model prices the event MORE likely
    than the crowd. Magnitude matters: a thin edge after fees/slippage may not
    survive (see ExpectedValue).
    """

    exchange_id: int
    p_model: float
    p_market: float
    edge: float
    basis: str = "mid"          # which market prob the edge uses (mid/last)
    model_id: str = "unknown"
    ts: int = 0
    edge_hash: str = ""

    def __post_init__(self):
        edge = round(self.p_model - self.p_market, 9)
        object.__setattr__(self, "edge", edge)
        if not self.edge_hash:
            object.__setattr__(self, "edge_hash", self.compute_hash())

    def state(self) -> dict:
        return {
            "exchange_id": self.exchange_id,
            "p_model": self.p_model,
            "p_market": self.p_market,
            "edge": self.edge,
            "basis": self.basis,
            "model_id": self.model_id,
            "ts": self.ts,
        }

    def compute_hash(self) -> str:
        return sha256(canonical_bytes(self.state()))


def extract_market_probability(
    exchange_id: int,
    bid_cents: int,
    ask_cents: int,
    *,
    last_cents: Optional[int] = None,
    venue: str = "kalshi",
    live: bool = False,
    ticker: Optional[str] = None,
    ts: int = 0,
) -> MarketProbability:
    """Build a ``MarketProbability`` from Kalshi order-book cents.

    Mirrors ``exchange/feeds.Quote`` conventions (cents in [1,99], mid = mean).
    ``bid_prob``/``ask_prob`` are the YES probabilities from the resting book;
    ``last_prob`` uses the last trade when provided.
    """
    if not (1 <= bid_cents <= 99 and 1 <= ask_cents <= 99):
        raise ValueError(f"Kalshi prices must be in [1,99] cents, got {bid_cents}/{ask_cents}")
    bid_prob = bid_cents / 100.0
    ask_prob = ask_cents / 100.0
    mid_prob = (bid_prob + ask_prob) / 2.0
    last_prob = (last_cents / 100.0) if last_cents is not None else None
    return MarketProbability(
        exchange_id=exchange_id,
        mid_prob=mid_prob,
        bid_prob=bid_prob,
        ask_prob=ask_prob,
        last_prob=last_prob,
        venue=venue,
        live=live,
        ticker=ticker,
        ts=ts,
    )


def estimate_edge(
    model: ProbabilityEstimate,
    market: MarketProbability,
    *,
    basis: str = "mid",
    ts: int = 0,
) -> EdgeEstimate:
    """Edge = P_model - P_market, using the chosen market-prob basis."""
    return EdgeEstimate(
        exchange_id=model.exchange_id,
        p_model=model.p_yes,
        p_market=p_market_for(market, basis),
        edge=model.p_yes - p_market_for(market, basis),
        basis=basis,
        model_id=model.model_id,
        ts=ts,
    )


def p_market_for(market: MarketProbability, basis: str) -> float:
    """Resolve the chosen market-probability basis (mid, or last when present)."""
    return market.last_prob if (basis == "last" and market.last_prob is not None) else market.mid_prob


__all__ = [
    "ProbabilityEstimate",
    "MarketProbability",
    "EdgeEstimate",
    "extract_market_probability",
    "estimate_edge",
]
