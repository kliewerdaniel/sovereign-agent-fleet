"""Price discovery: real vs simulated market-data feeds for the sovereign venue.

Per the River-Markets thesis the sovereign venue is the AGGREGATOR and pulls
best-bid/offer from every venue to drive smart routing + honest P&L marks. This
module is the price-discovery seam.

Two implementations:

* :class:`SimPriceFeed` — a deterministic, seedable random-walk quote generator.
  Fully testable in-sandbox (no egress). It IS the live market for the sim-first
  build: quotes are published as ``quote`` events on the existing market bus so
  routing/P&L can mark against real-looking external prices instead of only
  internal fills.
* :class:`KalshiPriceFeed` — a REAL feed that pulls the Kalshi order book REST
  endpoint. It is fail-closed and env-gated: ``is_live()`` is True only with
  loaded creds, and a network pull skips cleanly when the build sandbox cannot
  reach ``*.kalshi.com`` (DNS/egress restriction) — never raises on missing net.

HONESTY: every quote carries a ``live`` flag. The UI/ledger must never present a
sim quote as if it came from a real venue.
"""
from __future__ import annotations

import abc
import math
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from exchange.core.events import EventType, MarketEvent, quote_event
from exchange.venues.kalshi import KalshiLive


@dataclass
class Quote:
    exchange_id: int
    venue: str
    ticker: Optional[str]
    bid_cents: int
    ask_cents: int
    live: bool = False

    @property
    def mid_cents(self) -> int:
        return (self.bid_cents + self.ask_cents) // 2

    def to_dict(self) -> dict:
        return {
            "exchange_id": self.exchange_id,
            "venue": self.venue,
            "ticker": self.ticker,
            "bid_cents": self.bid_cents,
            "ask_cents": self.ask_cents,
            "mid_cents": self.mid_cents,
            "live": self.live,
        }


class PriceFeed(abc.ABC):
    """Abstract market-data source for one venue."""

    venue: str = "abstract"

    @abc.abstractmethod
    def is_live(self) -> bool:
        """True only when quotes originate from a real, credentialed venue."""

    @abc.abstractmethod
    def quote(self, exchange_id: int, ticker: Optional[str] = None) -> Quote:
        """Return the current bid/ask for ``exchange_id`` (ticker if known)."""


class SimPriceFeed(PriceFeed):
    """Deterministic seeded random-walk around an anchor mid.

    Honest about liveness (``live=False``). The walk is seeded by
    ``(exchange_id, step)`` so repeated pulls at the same step are reproducible
    in tests; an optional ``seed`` shifts the whole series.
    """

    venue = "sim"

    def __init__(self, anchor_mid_cents: int = 50, half_spread_cents: int = 2, seed: int = 0):
        if not 1 <= anchor_mid_cents <= 99:
            raise ValueError("anchor mid must be in [1,99] cents")
        self.anchor = anchor_mid_cents
        self.half_spread = max(1, half_spread_cents)
        self.seed = seed
        self._step: Dict[int, int] = {}
        self._last: Dict[int, Quote] = {}

    def is_live(self) -> bool:
        return False

    def _mid(self, exchange_id: int) -> int:
        step = self._step.get(exchange_id, 0)
        # Deterministic pseudo-random walk in [-20, +20] cents around anchor.
        s = (exchange_id * 2654435761 + step * 40503 + self.seed * 2246822519) & 0xFFFFFFFF
        noise = (s % 41) - 20  # -20..+20
        mid = self.anchor + noise
        return max(1, min(99, mid))

    def quote(self, exchange_id: int, ticker: Optional[str] = None) -> Quote:
        mid = self._mid(exchange_id)
        bid = max(1, mid - self.half_spread)
        ask = min(99, mid + self.half_spread)
        q = Quote(
            exchange_id=exchange_id,
            venue=self.venue,
            ticker=ticker,
            bid_cents=bid,
            ask_cents=ask,
            live=False,
        )
        self._last[exchange_id] = q
        return q

    def step(self, exchange_ids: List[int]) -> List[MarketEvent]:
        """Advance the walk one tick and publish ``quote`` events for each id."""
        events: List[MarketEvent] = []
        for eid in exchange_ids:
            self._step[eid] = self._step.get(eid, 0) + 1
            q = self.quote(eid)
            events.append(quote_event(eid, self.venue, q.bid_cents, q.ask_cents, q.ticker, live=False))
        return events

    def advance(self) -> None:
        for eid in list(self._step.keys()):
            self._step[eid] += 1


class KalshiPriceFeed(PriceFeed):
    """Real Kalshi market-data feed (order book REST).

    Fail-closed + env-gated: requires credentials (loaded from the gitignored
    ``exchange/.env``), and any network pull skips/returns a sim-equivalent on
    connectivity failure rather than raising. Never places an order.
    """

    venue = "Kalshi"
    DEFAULT_BASE_URL = "https://demo-api.kalshi.com/v1"

    def __init__(self, base_url: Optional[str] = None, allow_network: bool = True):
        _load_env()
        self.base_url = (base_url or os.environ.get("KALSHI_BASE_URL") or self.DEFAULT_BASE_URL).rstrip("/")
        self.api_key_id = os.environ.get("KALSHI_API_KEY_ID")
        self.private_key_pem = os.environ.get("KALSHI_PRIVATE_KEY")
        self.allow_network = allow_network
        self._key_loaded = bool(self.private_key_pem)

    def is_live(self) -> bool:
        return self._key_loaded

    def quote(self, exchange_id: int, ticker: Optional[str] = None) -> Quote:
        if not (self._key_loaded and self.allow_network):
            # Honest fallback: no live data available.
            return Quote(exchange_id, self.venue, ticker, bid_cents=50, ask_cents=50, live=False)
        sym = ticker or str(exchange_id)
        try:
            status, body = KalshiLive(base_url=self.base_url).get_market(sym)
        except Exception:
            # Connectivity/DNS failure (e.g. sandbox egress) — never raise.
            return Quote(exchange_id, self.venue, ticker, bid_cents=50, ask_cents=50, live=False)
        if status != 200 or not body:
            return Quote(exchange_id, self.venue, ticker, bid_cents=50, ask_cents=50, live=False)
        # Kalshi returns yes_bid/yes_ask in cents.
        yes = body.get("market", {}).get("yes", {}) if isinstance(body, dict) else {}
        bid = int(yes.get("bid", 50))
        ask = int(yes.get("ask", 50))
        return Quote(exchange_id, self.venue, sym, bid_cents=bid, ask_cents=ask, live=True)


def _load_env() -> None:
    """Load exchange/.env once (mirrors KalshiLive's loader)."""
    from exchange.venues.kalshi import _load_env_file

    _load_env_file(os.path.join(os.path.dirname(__file__), "venues", "..", ".env"))
    _load_env_file(".env")


__all__ = ["PriceFeed", "SimPriceFeed", "KalshiPriceFeed", "Quote"]
