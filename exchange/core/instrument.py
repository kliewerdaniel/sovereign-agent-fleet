"""Core instrument model: the canonical exchange identifier (`exchange_id`).

Mirrors River's `river_id`: a standardized numeric identifier for every contract on
every venue. The canonical `ExchangeId` is the wire identity; a venue-native ticker
(e.g. Kalshi's `KXFEDDECISION-26JUN-C25`) is an *alias* resolved via the registry.

Prediction-market contracts here are binary YES/NO markets priced in [0.01, 0.99]
(one cent to 99 cents), matching the integer-cent convention used by real venues.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Optional

# A canonical id is a positive integer (river_id-style).
ExchangeId = int

_PRICE_MIN = 1  # $0.01
_PRICE_MAX = 99  # $0.99


def cents(price: float) -> int:
    """Convert a dollar price (0.01..0.99) to integer cents (1..99)."""
    c = round(price * 100)
    if c < _PRICE_MIN or c > _PRICE_MAX:
        raise ValueError(f"price {price} out of range [{0.01}, {0.99}]")
    return c


def dollars(c: int) -> float:
    """Convert integer cents back to a dollar float (e.g. 27 -> 0.27)."""
    return c / 100.0


@dataclass(frozen=True)
class Instrument:
    """A binary prediction-market contract (YES/NO) on a venue."""

    exchange_id: ExchangeId
    title: str
    venue: str  # e.g. "sim", "kalshi"
    venue_ticker: str  # venue-native symbol (alias); "" if sim-native
    outcomes: tuple[str, str] = ("YES", "NO")

    def validate(self) -> None:
        if not (1 <= self.exchange_id <= 2**53):
            raise ValueError(f"exchange_id {self.exchange_id} out of range")
        if self.outcomes != ("YES", "NO"):
            raise ValueError("only binary YES/NO outcomes supported")


@dataclass
class InstrumentRegistry:
    """Resolves canonical `exchange_id`s and their venue aliases.

    The canonical id is the authority; the venue ticker is an alias. Lookup is
    bidirectional (by id or by (venue, ticker)).
    """

    _by_id: Dict[ExchangeId, Instrument] = field(default_factory=dict)
    _by_venue_ticker: Dict[tuple[str, str], ExchangeId] = field(default_factory=dict)
    _next: ExchangeId = 1

    def register(
        self,
        title: str,
        venue: str,
        venue_ticker: str = "",
        exchange_id: Optional[ExchangeId] = None,
    ) -> Instrument:
        if exchange_id is None:
            exchange_id = self._next
            self._next += 1
        elif exchange_id in self._by_id:
            raise ValueError(f"exchange_id {exchange_id} already registered")
        inst = Instrument(
            exchange_id=exchange_id,
            title=title,
            venue=venue,
            venue_ticker=venue_ticker,
        )
        inst.validate()
        self._by_id[exchange_id] = inst
        if venue_ticker:
            self._by_venue_ticker[(venue, venue_ticker)] = exchange_id
        return inst

    def get(self, exchange_id: ExchangeId) -> Instrument:
        try:
            return self._by_id[exchange_id]
        except KeyError:
            raise KeyError(f"no instrument for exchange_id={exchange_id}") from None

    def resolve_venue(self, venue: str, venue_ticker: str) -> ExchangeId:
        """Map a (venue, ticker) alias to its canonical exchange_id."""
        try:
            return self._by_venue_ticker[(venue, venue_ticker)]
        except KeyError:
            raise KeyError(f"no mapping for ({venue}, {venue_ticker})") from None

    def get_by_ticker(self, venue_ticker: str, venue: str = "kalshi") -> Optional[ExchangeId]:
        """Best-effort reverse lookup: ticker -> canonical exchange_id.

        Returns None when the ticker isn't in the registry (e.g. a live WS
        ticker message for a market we haven't modeled). Never raises.
        """
        return self._by_venue_ticker.get((venue, venue_ticker))

    def __iter__(self):
        return iter(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)


_TICKER_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
