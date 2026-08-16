"""Tests for the live Kalshi v2 Market Ticker WebSocket stream.

Sim/unit tests are sandbox-safe (no network). The live test is network-marked and
proves a real WS connection streams ticker quotes with the loaded RSA-PSS creds.
"""
import asyncio
import json
import threading
import time

import pytest

from exchange.core import ExchangeBus, InstrumentRegistry
from exchange.core.events import EventType
from exchange.feeds import Quote
from exchange.ticker_stream import (
    KalshiTickerStream,
    _rest_base_for,
    _subscribe_cmd,
)
from exchange.venues.kalshi import KalshiLive


# -- unit: subscribe command + rest-base mapping (no network) ---------------
def test_subscribe_cmd_shape():
    cmd = json.loads(_subscribe_cmd(["KXABC-25DEC-T3.00"], send_initial_snapshot=True))
    assert cmd["cmd"] == "subscribe"
    assert cmd["params"]["channels"] == ["ticker"]
    assert cmd["params"]["market_tickers"] == ["KXABC-25DEC-T3.00"]
    assert cmd["params"]["send_initial_snapshot"] is True


def test_subscribe_cmd_no_tickers_subscribes_all():
    cmd = json.loads(_subscribe_cmd([], send_initial_snapshot=False))
    assert "market_tickers" not in cmd["params"]
    assert cmd["params"]["send_initial_snapshot"] is False


def test_rest_base_for_is_demo():
    # Signing client host is irrelevant to WS signing; always demo base.
    assert _rest_base_for("wss://api.elections.kalshi.com/trade-api/ws/v2").endswith("/trade-api/v2")
    assert _rest_base_for("wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2").endswith("/trade-api/v2")


def test_stream_gated_off_is_noop():
    """Without allow_network, the stream never starts and reports not-live."""
    bus = ExchangeBus()
    s = KalshiTickerStream(market_tickers=[], bus=bus, allow_network=False)
    assert s.is_live() is False
    assert s.start() is False
    assert s.running is False


def test_stream_parses_ticker_to_live_quote():
    """The internal ticker parser maps a v2 ticker msg to a live Quote + event."""
    bus = ExchangeBus()
    reg = InstrumentRegistry()
    reg.register(title="x", venue="kalshi", venue_ticker="KXABC-25DEC-T3.00", exchange_id=7)
    captured = []
    s = KalshiTickerStream(market_tickers=["KXABC-25DEC-T3.00"], bus=bus, registry=reg, allow_network=False)
    bus.subscribe(lambda e: captured.append(e) if e.type == EventType.QUOTE else None)
    raw = json.dumps({
        "type": "ticker",
        "sid": 1,
        "msg": {
            "market_ticker": "KXABC-25DEC-T3.00",
            "market_id": "abc",
            "price_dollars": "0.53",
            "yes_bid_dollars": "0.52",
            "yes_ask_dollars": "0.54",
            "volume_fp": "100.00",
            "open_interest_fp": "200.00",
            "dollar_volume": 53,
            "dollar_open_interest": 106,
            "yes_bid_size_fp": "10.00",
            "yes_ask_size_fp": "20.00",
            "last_trade_size_fp": "5.00",
            "ts": 123,
            "ts_ms": 123000,
        },
    })
    s._handle(raw)
    assert len(captured) == 1
    ev = captured[0]
    assert ev.payload["live"] is True
    assert ev.payload["bid_cents"] == 52
    assert ev.payload["ask_cents"] == 54
    assert ev.exchange_id == 7  # resolved from ticker via registry


def test_stream_ignores_crossed_or_missing():
    bus = ExchangeBus()
    seen = []
    s = KalshiTickerStream(market_tickers=[], bus=bus, allow_network=False)
    bus.subscribe(lambda e: seen.append(e) if e.type == EventType.QUOTE else None)
    # crossed (ask <= bid) -> ignored
    s._handle(json.dumps({"type": "ticker", "sid": 1, "msg": {
        "market_ticker": "KXBAD", "market_id": "x", "price_dollars": "0.5",
        "yes_bid_dollars": "0.60", "yes_ask_dollars": "0.50"}}))
    # missing fields -> ignored
    s._handle(json.dumps({"type": "ticker", "sid": 1, "msg": {"market_ticker": "KXBAD2"}}))
    assert seen == []


def test_stream_on_quote_callback_fires():
    bus = ExchangeBus()
    s = KalshiTickerStream(market_tickers=[], bus=bus, allow_network=False)
    got = []
    s.on_quote = lambda q: got.append(q)
    s._handle(json.dumps({"type": "ticker", "sid": 1, "msg": {
        "market_ticker": "KXQ", "market_id": "x", "price_dollars": "0.4",
        "yes_bid_dollars": "0.39", "yes_ask_dollars": "0.41"}}))
    assert len(got) == 1 and got[0].live is True


@pytest.mark.network
def test_stream_live_receives_real_ticker():
    """Real v2 WS: connect with creds, subscribe, receive live ticker quotes.

    Skips if no creds/network. Never places an order. Verified against
    api.elections.kalshi.com (shared demo-cred host).
    """
    if not KalshiLive(base_url="https://external-api.demo.kalshi.co/trade-api/v2").is_live():
        pytest.skip("no Kalshi creds in exchange/.env")

    bus = ExchangeBus()
    seen = []
    bus.subscribe(lambda e: seen.append(e) if e.type == EventType.QUOTE else None)

    s = KalshiTickerStream(market_tickers=[], bus=bus, allow_network=True)
    if not s.start():
        pytest.skip("stream could not start (creds/host)")
    try:
        # give it time to connect + receive at least one ticker frame
        deadline = time.time() + 12
        while time.time() < deadline and not seen:
            time.sleep(0.25)
    finally:
        s.stop()
        # allow the daemon loop to exit
        time.sleep(0.5)
    assert any(e.payload.get("live") for e in seen), "no live ticker quote received"
    assert all(0 <= e.payload["bid_cents"] < e.payload["ask_cents"] <= 100 for e in seen)
