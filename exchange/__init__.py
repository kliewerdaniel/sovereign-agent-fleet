"""exchange — sovereign prediction-market execution stack.

A faithful re-implementation of the River-Markets prime-broker architecture AS our
own sovereign venue/aggregator. The hard infrastructure (matching engine, order
books, streams, settlement) is built first; governance + signed API layer on top.

`exchange` imports `fleet.crypto` and `fleet.layers` strictly as a *library* — it
never forks or re-implements crypto/policy/approval. See exchange/PLANNING.md.

Thesis: Do not trust the model. Trust the execution protocol.
"""
from .core.instrument import ExchangeId, Instrument, InstrumentRegistry
from .core.order import (
    Order,
    OrderSide,
    OrderType,
    TimeInForce,
    make_limit_order,
)
from .core.book import OrderBook, BookLevel, BookSnapshot
from .core.matching import MatchingEngine, Fill, MatchResult
from .core.settlement import ShadowLedger, Position, PnL

__all__ = [
    "ExchangeId",
    "Instrument",
    "InstrumentRegistry",
    "Order",
    "OrderSide",
    "OrderType",
    "TimeInForce",
    "make_limit_order",
    "OrderBook",
    "BookLevel",
    "BookSnapshot",
    "MatchingEngine",
    "Fill",
    "MatchResult",
    "ShadowLedger",
    "Position",
    "PnL",
]
