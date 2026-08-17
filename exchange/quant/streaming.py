"""Streaming statistics + anomaly detection (Q2, Layer-1 evidence).

Subscribes to the REAL exchange market bus (``exchange.core.events.ExchangeBus``)
and turns the quote/trade stream into hashable evidence records:
    * ``StreamStat``   -- running + rolling-window mean/variance per market
    * ``AnomalyAlert`` -- z-score, CUSUM (mean shift), Page-Hinkley (change pt)

This is the temporal counterpart to Q1's static edge/EV: instead of one snapshot
of P_model vs P_market, we watch the *stream* for regime shifts, thin liquidity,
or sudden dislocations that a single estimate would miss.

BOUNDARY (same wall as the rest of exchange/quant): may import ONLY
``fleet.crypto`` + ``exchange.core.events`` (+ same-package modules). It MUST
NOT import ``fleet.fin``, ``exchange.governance``, ``fleet.layers.*``, or
``fleet.cognition``. It observes the bus as a *reader*; it never authorizes,
sizes, or executes. A boundary test fails the build on violation.

All detectors are deterministic: given the same ordered event stream they
produce identical stats + alerts, so a verifier can replay the bus and recompute
them (I15-style reproducibility, extended to the temporal domain).
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional

from fleet.crypto.foundation import canonical_bytes, sha256
from exchange.core.events import EventType


@dataclass(frozen=True)
class StreamStat:
    """Running + rolling-window statistics for one market's probability stream.

    ``mean``/``var``/``std`` are Welford online estimates over the whole stream;
    ``window_mean``/``window_std`` are over the last ``window`` observations only
    (robust to slow drift). All values are probabilities in (0,1).
    """

    exchange_id: int
    n: int
    mean: float
    var: float
    std: float
    window_mean: float
    window_std: float
    last_value: float
    kind: str = "quote"          # "quote" (mid prob) or "trade" (fill prob)
    ts: int = 0
    ss_hash: str = ""

    def __post_init__(self):
        std = round(math.sqrt(max(0.0, self.var)), 9)
        object.__setattr__(self, "std", std)
        if not self.ss_hash:
            object.__setattr__(self, "ss_hash", self.compute_hash())

    def state(self) -> dict:
        return {
            "exchange_id": self.exchange_id,
            "n": self.n,
            "mean": self.mean,
            "var": self.var,
            "std": self.std,
            "window_mean": self.window_mean,
            "window_std": self.window_std,
            "last_value": self.last_value,
            "kind": self.kind,
            "ts": self.ts,
        }

    def compute_hash(self) -> str:
        return sha256(canonical_bytes(self.state()))


@dataclass(frozen=True)
class AnomalyAlert:
    """A detector fired (or was evaluated) on the stream at one observation.

    ``triggered`` is True only when the statistic crossed its threshold. The
    alert is evidence, not an action: the governance gate never reads it; an
    orchestrator may escalate advisory flags from it (one-way, like Q1).
    """

    exchange_id: int
    kind: str                    # "zscore" | "cusum" | "page_hinkley"
    value: float                 # the statistic (z, cumsum, or PH sum)
    threshold: float
    triggered: bool
    value_at: float              # the observation that triggered (probability)
    basis: str = "window"
    ts: int = 0
    alert_hash: str = ""

    def __post_init__(self):
        if not self.alert_hash:
            object.__setattr__(self, "alert_hash", self.compute_hash())

    def state(self) -> dict:
        return {
            "exchange_id": self.exchange_id,
            "kind": self.kind,
            "value": self.value,
            "threshold": self.threshold,
            "triggered": self.triggered,
            "value_at": self.value_at,
            "basis": self.basis,
            "ts": self.ts,
        }

    def compute_hash(self) -> str:
        return sha256(canonical_bytes(self.state()))


class OnlineStats:
    """Welford running mean/variance + bounded rolling window."""

    def __init__(self, window: int = 50):
        self.window = max(1, window)
        self.n = 0
        self._mean = 0.0
        self._m2 = 0.0
        self._recent: Deque[float] = deque(maxlen=window)

    def update(self, x: float) -> None:
        self.n += 1
        delta = x - self._mean
        self._mean += delta / self.n
        delta2 = x - self._mean
        self._m2 += delta * delta2
        self._recent.append(x)

    @property
    def mean(self) -> float:
        return self._mean

    @property
    def var(self) -> float:
        return self._m2 / (self.n - 1) if self.n > 1 else 0.0

    @property
    def std(self) -> float:
        return math.sqrt(self.var)

    @property
    def window_values(self) -> List[float]:
        return list(self._recent)

    def window_mean(self) -> float:
        if not self._recent:
            return 0.0
        return sum(self._recent) / len(self._recent)

    def window_std(self) -> float:
        w = list(self._recent)
        if len(w) < 2:
            return 0.0
        m = sum(w) / len(w)
        return math.sqrt(sum((v - m) ** 2 for v in w) / (len(w) - 1))

    def state(self) -> dict:
        """Deterministic provenance snapshot (hashable Layer-1 evidence)."""
        return {
            "window": self.window,
            "n": self.n,
            "mean": self._mean,
            "m2": self._m2,
            "recent": list(self._recent),
        }
class CusumDetector:
    """Two-sided CUSUM for a sustained mean shift (gold standard, Lorden)."""

    def __init__(self, target: Optional[float] = None, h: float = 0.05, k: float = 0.02):
        self.target = target
        self.h = h                      # decision threshold (in prob units)
        self.k = k                      # slack / half expected shift
        self.s_pos = 0.0
        self.s_neg = 0.0
        self._warm: List[float] = []

    def update(self, x: float) -> float:
        if self.target is None:
            # estimate target from a short warmup
            self._warm.append(x)
            if len(self._warm) >= 20:
                self.target = sum(self._warm) / len(self._warm)
            return 0.0
        self.s_pos = max(0.0, self.s_pos + (x - self.target - self.k))
        self.s_neg = max(0.0, self.s_neg - (x - self.target - self.k))
        return max(self.s_pos, self.s_neg)

    def triggered(self, stat: float) -> bool:
        return stat > self.h


class PageHinkleyDetector:
    """Page-Hinkley test for an abrupt change point (with forgetting factor)."""

    def __init__(self, alpha: float = 0.005, threshold: float = 12.0):
        self.alpha = alpha              # minimum detectable change / 2
        self.threshold = threshold
        self._t = 0
        self._mt = 0.0
        self._pos = 0.0
        self._neg = 0.0

    def update(self, x: float) -> float:
        self._t += 1
        self._mt += (x - self._mt) / self._t
        self._pos = max(0.0, self._pos + (x - self._mt) - self.alpha)
        self._neg = max(0.0, self._neg + (self._mt - x) - self.alpha)
        return max(self._pos, self._neg)

    def triggered(self, stat: float) -> bool:
        return stat > self.threshold


class StreamAnalyzer:
    """Consume the market bus, maintain per-market stats + anomaly alerts.

    Pure Layer-1 evidence: subscribes as a reader, never imports authority,
    never mutates the book. Determinism: replaying the same event sequence
    reproduces the same ``StreamStat``/``AnomalyAlert`` records.
    """

    def __init__(
        self,
        *,
        exchange_ids: Optional[List[int]] = None,
        window: int = 50,
        z_threshold: float = 3.0,
        z_min_samples: int = 10,
        cusum_h: float = 0.05,
        cusum_k: float = 0.02,
        ph_alpha: float = 0.005,
        ph_threshold: float = 8.0,
    ):
        self.exchange_ids = set(exchange_ids) if exchange_ids else None
        self.window = window
        self.z_threshold = z_threshold
        self.z_min_samples = z_min_samples
        self._stats: Dict[int, OnlineStats] = {}
        self._cusum: Dict[int, CusumDetector] = {}
        self._ph: Dict[int, PageHinkleyDetector] = {}
        self.latest: Dict[int, StreamStat] = {}
        self.alerts: Dict[int, List[AnomalyAlert]] = {}
        self._cusum_h = cusum_h
        self._cusum_k = cusum_k
        self._ph_alpha = ph_alpha
        self._ph_threshold = ph_threshold

    # -- bus wiring ---------------------------------------------------------
    def subscribe_to(self, bus) -> callable:
        """Attach to an ``ExchangeBus``; returns an unsubscribe callable."""
        return bus.subscribe(self.handle)

    # -- event intake -------------------------------------------------------
    def handle(self, event) -> None:
        """Handle one ``MarketEvent`` (read-only)."""
        if event.type not in (EventType.QUOTE, EventType.TRADE, EventType.BOOK):
            return
        eid = event.exchange_id
        if self.exchange_ids is not None and eid not in self.exchange_ids:
            return
        p = self._prob_from_event(event)
        if p is None:
            return
        self._ingest(eid, p, kind=self._kind_of(event), ts=int(event.ts))

    def replay_into(self, events: List) -> None:
        for e in events:
            self.handle(e)

    def _prob_from_event(self, event) -> Optional[float]:
        payload = event.payload or {}
        if event.type == EventType.TRADE:
            pc = payload.get("price_cents")
            if pc is None:
                return None
            return max(0.01, min(0.99, pc / 100.0))
        # QUOTE / BOOK carry bid/ask (BOOK may carry full snapshot; use mid)
        bid = payload.get("bid_cents")
        ask = payload.get("ask_cents")
        if bid is None or ask is None:
            # BOOK snapshots may embed a nested book; fall back to mid_cents
            mid = payload.get("mid_cents")
            if mid is None:
                return None
            return max(0.01, min(0.99, mid / 100.0))
        mid = (bid + ask) / 2.0
        return max(0.01, min(0.99, mid / 100.0))

    def _kind_of(self, event) -> str:
        return "trade" if event.type == EventType.TRADE else "quote"

    # -- core ingestion -----------------------------------------------------
    def _ingest(self, eid: int, p: float, kind: str, ts: int) -> None:
        if eid not in self._stats:
            self._stats[eid] = OnlineStats(window=self.window)
            self._cusum[eid] = CusumDetector(h=self._cusum_h, k=self._cusum_k)
            self._ph[eid] = PageHinkleyDetector(alpha=self._ph_alpha, threshold=self._ph_threshold)
            self.alerts[eid] = []
        st = self._stats[eid]
        # z-score uses the ESTABLISHED window (before this point is folded in),
        # so the point under test does not contaminate its own reference dist.
        prior_wmean = st.window_mean()
        prior_wstd = st.window_std()
        st.update(p)
        # record the snapshot stat (post-update)
        self.latest[eid] = StreamStat(
            exchange_id=eid, n=st.n, mean=st.mean, var=st.var, std=st.std,
            window_mean=st.window_mean(), window_std=st.window_std(),
            last_value=p, kind=kind, ts=ts,
        )
        # z-score (test new point against the prior window)
        if st.n > 1 and prior_wstd > 0:
            z = (p - prior_wmean) / prior_wstd
            if abs(z) > self.z_threshold:
                self.alerts[eid].append(AnomalyAlert(
                    exchange_id=eid, kind="zscore", value=round(z, 6),
                    threshold=self.z_threshold, triggered=True, value_at=p,
                    basis="window", ts=ts,
                ))
        # CUSUM
        cval = self._cusum[eid].update(p)
        if self._cusum[eid].triggered(cval):
            self.alerts[eid].append(AnomalyAlert(
                exchange_id=eid, kind="cusum", value=round(cval, 6),
                threshold=self._cusum_h, triggered=True, value_at=p,
                basis="cusum", ts=ts,
            ))
        # Page-Hinkley
        pval = self._ph[eid].update(p)
        if self._ph[eid].triggered(pval):
            self.alerts[eid].append(AnomalyAlert(
                exchange_id=eid, kind="page_hinkley", value=round(pval, 6),
                threshold=self._ph_threshold, triggered=True, value_at=p,
                basis="ph", ts=ts,
            ))

    # -- read API -----------------------------------------------------------
    def latest_stat(self, eid: int) -> Optional[StreamStat]:
        return self.latest.get(eid)

    def latest_alerts(self, eid: int) -> List[AnomalyAlert]:
        return list(self.alerts.get(eid, []))

    def state(self) -> dict:
        """Deterministic provenance snapshot (hashable Layer-1 evidence)."""
        return {
            "window": self.window,
            "z_threshold": self.z_threshold,
            "z_min_samples": self.z_min_samples,
            "cusum_h": self._cusum_h,
            "cusum_k": self._cusum_k,
            "ph_alpha": self._ph_alpha,
            "ph_threshold": self._ph_threshold,
            "stats": {str(k): v.state() for k, v in self._stats.items()},
            "alerts": {
                str(k): [a.state() for a in v if a.triggered]
                for k, v in self.alerts.items()
            },
        }

    def compute_hash(self) -> str:
        """sha256(canonical(state())) — lets an orchestrator bind the analyzer
        state into a QuantEvidence audit log for replay/verification."""
        return sha256(canonical_bytes(self.state()))


__all__ = [
    "StreamStat",
    "AnomalyAlert",
    "OnlineStats",
    "CusumDetector",
    "PageHinkleyDetector",
    "StreamAnalyzer",
]
