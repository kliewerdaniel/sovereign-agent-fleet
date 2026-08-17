"""Q2 tests: streaming stats + anomaly detection over the REAL exchange bus.

No mocks: we build a genuine ``ExchangeBus``, publish ``quote_event``/``trade_event``
events (the same objects the sim feed emits), subscribe a ``StreamAnalyzer``, and
assert the deterministic detectors fire correctly. Also proves replay
reproduces identical stats (I15-style temporal reproducibility).
"""
from __future__ import annotations

import math

import pytest
from exchange.core.events import (
    EventType,
    ExchangeBus,
    MarketEvent,
    quote_event,
    trade_event,
)
from exchange.quant.streaming import (
    AnomalyAlert,
    CusumDetector,
    OnlineStats,
    PageHinkleyDetector,
    StreamAnalyzer,
    StreamStat,
)


def _quote(eid: int, bid: int, ask: int, ts: int) -> MarketEvent:
    return quote_event(eid, "sim", bid, ask, ticker=f"M{eid}", live=False)


def _q(eid: int, mid_c: int, ts: int) -> MarketEvent:
    """A quote event at integer mid in cents."""
    return quote_event(eid, "sim", mid_c - 2, mid_c + 2, ticker=f"M{eid}", live=False)


def test_online_stats_welford_matches_bruteforce():
    vals = [0.5, 0.55, 0.6, 0.52, 0.48, 0.61, 0.59, 0.5]
    s = OnlineStats(window=4)
    for v in vals:
        s.update(v)
    bf_mean = sum(vals) / len(vals)
    bf_var = sum((v - bf_mean) ** 2 for v in vals) / (len(vals) - 1)
    assert s.mean == pytest.approx(bf_mean, rel=1e-9)
    assert s.var == pytest.approx(bf_var, rel=1e-9)
    # rolling window is last 4
    assert s.window_mean() == pytest.approx(sum(vals[-4:]) / 4, rel=1e-9)


def test_stream_stat_is_hashable_and_recomputable():
    s = OnlineStats(window=10)
    for v in [0.5, 0.51, 0.49]:
        s.update(v)
    st = StreamStat(exchange_id=1, n=s.n, mean=s.mean, var=s.var, std=s.std,
                    window_mean=s.window_mean(), window_std=s.window_std(),
                    last_value=0.49, kind="quote", ts=3)
    assert st.std == pytest.approx(math.sqrt(st.var), rel=1e-9)
    assert st.ss_hash == __import__("fleet.crypto.foundation", fromlist=["sha256"]).sha256(
        __import__("fleet.crypto.foundation", fromlist=["canonical_bytes"]).canonical_bytes(st.state())
    )


def test_cusum_detects_sustained_mean_shift():
    c = CusumDetector(target=0.5, h=0.05, k=0.02)
    # warmup at target, then a sustained upward shift
    for _ in range(20):
        c.update(0.5)
    shifted = 0.0
    for _ in range(20):
        shifted = c.update(0.62)
    assert c.triggered(shifted) is True


def test_page_hinkley_detects_abrupt_change():
    ph = PageHinkleyDetector(alpha=0.005, threshold=7.0)
    for _ in range(40):
        ph.update(0.5)
    stat = 0.0
    for _ in range(40):
        stat = ph.update(0.78)   # abrupt jump
    assert ph.triggered(stat) is True


def test_analyzer_subscribes_to_real_bus_and_builds_stats():
    bus = ExchangeBus()
    ana = StreamAnalyzer(exchange_ids=[1], window=10, z_threshold=3.0, z_min_samples=5)
    unsub = ana.subscribe_to(bus)
    # publish a stable mid around 50c
    for i, mid in enumerate([50, 51, 49, 50, 52, 48, 51, 50, 49, 50]):
        bus.publish(_q(1, mid, ts=100 + i))
    st = ana.latest_stat(1)
    assert st is not None
    assert st.n == 10
    assert st.window_mean == pytest.approx(0.50, abs=0.03)
    # no anomalies on a stable stream
    assert ana.latest_alerts(1) == []
    unsub()
    # after unsubscribe, publishing does nothing
    before = st.n
    bus.publish(_q(1, 90, ts=999))
    assert ana.latest_stat(1).n == before


def test_analyzer_fires_zscore_on_outlier():
    bus = ExchangeBus()
    ana = StreamAnalyzer(exchange_ids=[2], window=10, z_threshold=3.0, z_min_samples=5)
    ana.subscribe_to(bus)
    # stable ~0.50 with natural micro-noise (so window_std > 0)
    stable = [50, 51, 49, 50, 52, 48, 51, 50, 49, 50]
    for i, mid in enumerate(stable):
        bus.publish(_q(2, mid, ts=100 + i))
    # then a wild dislocation to 90c
    bus.publish(_q(2, 90, ts=200))
    alerts = ana.latest_alerts(2)
    z_alerts = [a for a in alerts if a.kind == "zscore" and a.triggered]
    assert z_alerts, "expected a z-score anomaly on the outlier"
    assert z_alerts[-1].value_at == pytest.approx(0.90, abs=1e-6)


def test_analyzer_ingests_trade_events():
    bus = ExchangeBus()
    ana = StreamAnalyzer(exchange_ids=[3], window=10, z_threshold=3.0, z_min_samples=3)
    ana.subscribe_to(bus)
    # trade fills at 50, 51, 49, 52 -> mid prob derived from price_cents
    for i, c in enumerate([50, 51, 49, 52]):
        bus.publish(trade_event(3, c, 1, __import__("exchange.core.events", fromlist=["OrderSide"]).OrderSide.BUY, "a", "b", f"t{i}", "m{i}"))
    st = ana.latest_stat(3)
    assert st is not None and st.kind == "trade"
    assert st.n == 4


def test_determinism_replay_reproduces_stats():
    events = [_q(1, m, ts=100 + i) for i, m in enumerate([50, 51, 49, 50, 52, 48, 99, 51, 50, 49, 50, 47])]
    a1 = StreamAnalyzer(exchange_ids=[1], window=10)
    a1.replay_into(events)
    a2 = StreamAnalyzer(exchange_ids=[1], window=10)
    a2.replay_into(list(events))   # independent replay
    s1, s2 = a1.latest_stat(1), a2.latest_stat(1)
    assert s1 is not None and s2 is not None
    assert s1.mean == s2.mean
    assert s1.window_mean == s2.window_mean
    assert s1.n == s2.n
    # alerts identical (same stream -> same detections)
    assert [(a.kind, round(a.value, 6), a.triggered) for a in a1.latest_alerts(1)] == \
           [(a.kind, round(a.value, 6), a.triggered) for a in a2.latest_alerts(1)]


def test_analyzer_ignores_non_price_events():
    bus = ExchangeBus()
    ana = StreamAnalyzer(exchange_ids=[1])
    ana.subscribe_to(bus)
    bus.publish(MarketEvent(type=EventType.HEARTBEAT, exchange_id=1, payload={}))
    bus.publish(MarketEvent(type=EventType.ORDER_ACCEPTED, exchange_id=1, payload={"qty": 5}))
    assert ana.latest_stat(1) is None
