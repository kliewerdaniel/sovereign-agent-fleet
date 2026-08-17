"""Temporal market/event graph + information gain (Q4, Layer-1 evidence).

Q4: a *local-first* (pure, in-memory, no network) directed graph of market
events. Each event records the market's believed P(YES) **before** and
**after** it was observed, and we measure the **information gain** of each
event as the drop in Bernoulli entropy it produced:

    IG(event) = H(p_before) - H(p_after)        [bits, >= 0]

where ``H(p) = -p*log2(p) - (1-p)*log2(1-p)`` is the entropy of a binary
outcome belief. A settlement that confirms a near-certain market adds ~0 bits
(no surprise); a regime shift that moves the belief from 0.50 to 0.80 removes
real uncertainty about the eventual outcome and scores a large gain.

The graph is *temporal*: events are ordered by ``ts`` and linked as a chain
(latest predecessor -> event), so we can also report cumulative information
gain and the single most-informative event. An optional ``parent_id`` on an
event creates a conditional edge (one event conditioned on another) for
graph-shaped provenance.

Why this is "local-first": it is a pure data structure. No feeds, no model
inference, no BLAS — just arithmetic over a list of observed (before, after)
pairs. A verifier replays the same event list and gets byte-identical hashes.

BOUNDARY (same wall as the rest of exchange/quant): imports ONLY
``fleet.crypto`` + intra-package modules. Never imports ``fleet.fin``,
``exchange.governance``, ``fleet.layers.*``, or ``fleet.cognition``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from fleet.crypto.foundation import canonical_bytes, sha256

# Probability bounds (open interval, like Q1/Q3).
_PROB_EPS = 1e-9


def _clamp_prob(p: float) -> float:
    if p <= 0.0:
        return _PROB_EPS
    if p >= 1.0:
        return 1.0 - _PROB_EPS
    return float(p)


def bernoulli_entropy(p: float) -> float:
    """Shannon entropy (bits) of a Bernoulli(p) belief.

    H(p) = -p*log2(p) - (1-p)*log2(1-p); H(0) = H(1) = 0 (deterministic).
    Raw endpoints are treated as exactly 0 entropy before clamping, so a
    certain belief reports exactly 0 bits (not a 1e-9 dust value from clamping).
    """
    if p <= 0.0 or p >= 1.0:
        return 0.0
    p = _clamp_prob(p)
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))


def information_gain(p_before: float, p_after: float) -> float:
    """Bits of uncertainty removed by moving belief from before -> after.

    Non-negative by construction (entropy is concave on [0,1] and 0/1 are the
    minima), but we never let float dust flip the sign.
    """
    g = bernoulli_entropy(p_before) - bernoulli_entropy(p_after)
    return max(0.0, g)


@dataclass(frozen=True)
class MarketEvent:
    """One observed market event with its belief impact.

    ``p_yes_before`` / ``p_yes_after`` are the market/agent P(YES) immediately
    before and after the event. ``parent_id`` is optional: set it to the
    ``event_id`` of an earlier event to declare a conditional edge (this event
    is "conditioned on" its parent for graph-shaped provenance).
    """

    event_id: str
    ts: int
    kind: str
    ticker: str
    p_yes_before: float
    p_yes_after: float
    exchange_id: int = 0
    parent_id: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "p_yes_before", _clamp_prob(self.p_yes_before))
        object.__setattr__(self, "p_yes_after", _clamp_prob(self.p_yes_after))

    @property
    def gain(self) -> float:
        return information_gain(self.p_yes_before, self.p_yes_after)

    def state(self) -> dict:
        return {
            "event_id": self.event_id,
            "ts": self.ts,
            "kind": self.kind,
            "ticker": self.ticker,
            "p_yes_before": self.p_yes_before,
            "p_yes_after": self.p_yes_after,
            "parent_id": self.parent_id,
        }

    def compute_hash(self) -> str:
        return sha256(canonical_bytes(self.state()))


class EventGraph:
    """A temporal graph of MarketEvents with information-gain analytics.

    Local-first: just arithmetic over a list. Deterministic + hashable — the
    same event list always yields the same hashes and gains.
    """

    def __init__(self, exchange_id: int, model_id: str = "unknown"):
        self.exchange_id = exchange_id
        self.model_id = model_id
        self._events: List[MarketEvent] = []

    # -- mutation ----------------------------------------------------------
    def add_event(self, event: MarketEvent) -> "EventGraph":
        # exchange_id 0 means "inherit from container" (default when a caller
        # builds an event without specifying an exchange). Any explicit,
        # mismatched id is rejected so provenance stays coherent.
        if event.exchange_id != 0 and event.exchange_id != self.exchange_id:
            raise ValueError("event exchange_id does not match graph")
        self._events.append(event)
        self._events.sort(key=lambda e: (e.ts, e.event_id))
        return self

    @classmethod
    def from_events(
        cls, exchange_id: int, events: List[MarketEvent], model_id: str = "unknown"
    ) -> "EventGraph":
        g = cls(exchange_id, model_id=model_id)
        for e in events:
            g.add_event(e)
        return g

    # -- analytics ---------------------------------------------------------
    def per_event_gains(self) -> List[Tuple[MarketEvent, float]]:
        return [(e, e.gain) for e in self._events]

    def total_information_gain(self) -> float:
        """Sum of per-event information gains (bits)."""
        return sum(e.gain for e in self._events)

    def cumulative_entropy(self) -> float:
        """Entropy of the FINAL belief = entropy after the last event."""
        if not self._events:
            return 0.0
        return bernoulli_entropy(self._events[-1].p_yes_after)

    def most_informative_event(self) -> Optional[MarketEvent]:
        """The single event that removed the most uncertainty."""
        if not self._events:
            return None
        return max(self._events, key=lambda e: e.gain)

    def conditional_gain(self, event_id: str) -> Optional[float]:
        """Information gain of an event *given its parent already happened*.

        = entropy(after parent) - entropy(after this event). Only defined when
        the event has a ``parent_id`` that resolves to an earlier event.
        """
        child = self.get(event_id)
        if child is None or child.parent_id is None:
            return None
        parent = self.get(child.parent_id)
        if parent is None:
            return None
        return max(0.0, bernoulli_entropy(parent.p_yes_after) - bernoulli_entropy(child.p_yes_after))

    def get(self, event_id: str) -> Optional[MarketEvent]:
        for e in self._events:
            if e.event_id == event_id:
                return e
        return None

    def event_count(self) -> int:
        return len(self._events)

    # -- provenance --------------------------------------------------------
    def state(self) -> dict:
        return {
            "exchange_id": self.exchange_id,
            "model_id": self.model_id,
            "events": [e.state() for e in self._events],
        }

    def compute_hash(self) -> str:
        return sha256(canonical_bytes(self.state()))


# -- convenience constructor from a raw numeric series ----------------------
def info_gain_from_series(
    exchange_id: int,
    p_yes_series: List[float],
    *,
    ts_start: int = 0,
    ts_step: int = 1,
    ticker: str = "DEFAULT",
    kind: str = "OBSERVATION",
    model_id: str = "unknown",
) -> EventGraph:
    """Build an EventGraph from a *sequence* of P(YES) snapshots.

    Each consecutive pair (p[i-1] -> p[i]) becomes one event carrying the
    belief movement between adjacent snapshots. Useful for feeding a streaming
    belief trajectory straight into the graph.
    """
    g = EventGraph(exchange_id, model_id=model_id)
    if not p_yes_series:
        return g
    prev = _clamp_prob(p_yes_series[0])
    for i in range(1, len(p_yes_series)):
        cur = _clamp_prob(p_yes_series[i])
        g.add_event(
            MarketEvent(
                event_id=f"{ticker}-{i}",
                ts=ts_start + i * ts_step,
                kind=kind,
                ticker=ticker,
                p_yes_before=prev,
                p_yes_after=cur,
                parent_id=(f"{ticker}-{i-1}" if i > 1 else None),
            )
        )
        prev = cur
    return g


__all__ = [
    "bernoulli_entropy",
    "information_gain",
    "MarketEvent",
    "EventGraph",
    "info_gain_from_series",
]
