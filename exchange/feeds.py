"""Price discovery: real vs simulated market-data feeds for the sovereign venue.

Per the River-Markets thesis the sovereign venue is the AGGREGATOR and pulls
best-bid/offer from every venue to drive smart routing + honest P&L marks. This
module is the price-discovery seam.

Two implementations:

* :class:`SimPriceFeed` -- a deterministic, seedable random-walk quote generator.
  Fully testable in-sandbox (no egress). It IS the live market for the sim-first
  build: quotes are published as ``quote`` events on the existing market bus so
  routing/P&L can mark against real-looking external prices instead of only
  internal fills.
* :class:`KalshiPriceFeed` -- REAL Kalshi market data, v2 contract. Pulls
  ``GET /markets/{ticker}`` (yes/no bid+ask in dollar strings) and parses them to
  integer cents. Fail-closed + gated: ``is_live()`` is True only when credentials
  are loaded AND ``allow_network=True`` AND the network probe succeeds. Any
  pull that fails (auth, DNS, parse) returns ``live=False`` and never raises.

HONESTY: every quote carries a ``live`` flag. The UI/ledger must never present a
sim quote as if it came from a real venue. The v2 Kalshi `yes_bid_dollars` we
receive is itself a real quote; we surface it with ``live=True`` and keep the
raw venue string on the quote for audit.

NOTE ON THE "/live_data/milestone" ENDPOINT: that Kalshi route returns live
*sports scoring* data (game progress, player stats) -- it has no prices and is
NOT part of price discovery. Real prices come from ``/markets/{ticker}``,
``/markets/{ticker}/orderbook``, and the WSS Market Ticker stream.
"""
from __future__ import annotations

import abc
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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
    # Raw venue response, kept for audit/debug (e.g. the dollar-string prices).
    raw: Optional[Dict[str, Any]] = None

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


def _dollars_to_cents(value: Any) -> Optional[int]:
    """Kalshi v2 returns prices as dollar strings (e.g. \"0.53\").

    Subpenny (deci_cent) pricing means 0.53 == 53 cents. Parse to integer cents;
    return None if missing/zero/non-numeric so the caller can stay honest.
    """
    if value is None:
        return None
    try:
        cents = round(float(value) * 100)
    except (ValueError, TypeError):
        return None
    return max(0, min(100, cents))


class KalshiPriceFeed(PriceFeed):
    """Real Kalshi market-data feed, v2 contract (``/markets/{ticker}``).

    Fail-closed + env-gated. ``is_live()`` is True only when:
      * credentials were loaded (private key present), AND
      * ``allow_network=True`` (opt-in; never on by default in a real venue), AND
      * a network probe (``GET /exchange/status``) actually reached Kalshi.

    A live quote uses the real ``yes_bid_dollars`` / ``yes_ask_dollars`` parsed to
    integer cents. Any failure (auth 401, DNS, parse, missing price) returns a
    ``live=False`` neutral quote -- never raises, never fabricates liveness.
    """

    venue = "Kalshi"
    # v2 demo (risk-free). Production would be external-api.kalshi.com/trade-api/v2.
    DEFAULT_BASE_URL = "https://external-api.demo.kalshi.co/trade-api/v2"

    def __init__(self, base_url: Optional[str] = None, allow_network: bool = False):
        _load_env()
        self.base_url = (base_url or os.environ.get("KALSHI_BASE_URL") or self.DEFAULT_BASE_URL).rstrip("/")
        self.api_key_id = os.environ.get("KALSHI_API_KEY_ID")
        self.allow_network = allow_network
        self._client = (
            KalshiLive(base_url=self.base_url, allow_live_orders=False)
            if (self.api_key_id and os.environ.get("KALSHI_PRIVATE_KEY"))
            else None
        )
        # Probe liveness once (read-only). Cached so repeated quotes don't re-hit.
        self._probed_live: Optional[bool] = None

    # -- liveness -----------------------------------------------------------
    def _probe(self) -> bool:
        if self._probed_live is not None:
            return self._probed_live
        live = False
        if self._client is not None and self.allow_network:
            try:
                st, _ = self._client.get_exchange_status()
                live = st == 200
            except Exception:
                live = False
        self._probed_live = live
        return live

    def is_live(self) -> bool:
        return self._probe()

    # -- quote --------------------------------------------------------------
    def quote(self, exchange_id: int, ticker: Optional[str] = None) -> Quote:
        sym = ticker or str(exchange_id)
        if not self.is_live() or self._client is None:
            # Honest fallback: no live data available.
            return Quote(exchange_id, self.venue, sym, bid_cents=50, ask_cents=50, live=False)

        try:
            status, body = self._client.get_market(sym)
        except Exception:
            # Connectivity/DNS failure -- never raise.
            return Quote(exchange_id, self.venue, sym, bid_cents=50, ask_cents=50, live=False)
        if status != 200 or not isinstance(body, dict):
            return Quote(exchange_id, self.venue, sym, bid_cents=50, ask_cents=50, live=False)

        mkt = body.get("market", body)
        y_bid = _dollars_to_cents(mkt.get("yes_bid_dollars"))
        y_ask = _dollars_to_cents(mkt.get("yes_ask_dollars"))
        if y_bid is None or y_ask is None or y_ask <= y_bid:
            # Missing or crossed/garbage -- do not claim a live quote we can't trust.
            return Quote(
                exchange_id, self.venue, sym, bid_cents=50, ask_cents=50,
                live=False, raw={"market": {k: mkt.get(k) for k in (
                    "yes_bid_dollars", "yes_ask_dollars", "no_bid_dollars", "no_ask_dollars",
                    "last_price_dollars", "status")}},
            )
        return Quote(
            exchange_id, self.venue, sym, bid_cents=y_bid, ask_cents=y_ask, live=True,
            raw={"market": {k: mkt.get(k) for k in (
                "yes_bid_dollars", "yes_ask_dollars", "no_bid_dollars", "no_ask_dollars",
                "last_price_dollars", "status")}},
        )


def _load_env() -> None:
    """Load exchange/.env once (mirrors KalshiLive's loader)."""
    from exchange.venues.kalshi import _load_env_file

    _load_env_file(os.path.join(os.path.dirname(__file__), "venues", "..", ".env"))
    _load_env_file(".env")


__all__ = ["PriceFeed", "SimPriceFeed", "KalshiPriceFeed", "Quote"]
