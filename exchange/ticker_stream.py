"""Live Kalshi v2 Market Ticker WebSocket stream.

This is the *streaming* half of price discovery: instead of polling
``GET /markets/{ticker}`` on demand, we hold one authenticated WebSocket to
Kalshi and receive real-time ``ticker`` updates (yes_bid/yes_ask in dollar
strings) for the markets we care about, parsing each into a ``Quote`` and
publishing it as a ``quote`` event on the existing market bus with ``live=True``.

Fail-closed + gated (mirrors the rest of the exchange package):

* The stream is ONLY constructed/started when ``allow_network=True`` AND creds
  are present. Otherwise ``KalshiTickerStream`` is never instantiated and the
  sim feed remains the sole (non-live) source.
* It places NO orders. Subscribe-only to the ``ticker`` channel.
* Connection/auth errors degrade gracefully: the stream retries with backoff
  and, if it can never connect, simply stays dark (``live=False``) — it never
  fabricates liveness or raises into the exchange core.
* A ``tick_callback`` (optional) lets the host cache the latest live quote per
  ticker so ``/quotes`` can prefer the streaming price over a stale on-demand
  pull.

Honesty: every quote published from this stream carries ``live=True`` because
the bytes genuinely arrived from Kalshi's v2 ticker channel. If the stream drops,
liveness falls back to whatever the sim/on-demand feed reports.
"""
from __future__ import annotations

import asyncio
import threading
import time
from typing import Callable, Dict, Optional

import websockets

from exchange.core.events import EventType, MarketEvent, quote_event
from exchange.feeds import Quote, _dollars_to_cents
from exchange.venues.kalshi import KalshiLive

WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
WS_PATH = "/trade-api/ws/v2"  # signed path for the handshake


class KalshiTickerStream:
    """Authenticates to Kalshi v2 WS, subscribes to ``ticker``, streams Quotes.

    Construct only when ``allow_network=True``. Lifecycle: ``start()`` spins an
    asyncio event loop on a daemon thread; ``stop()`` tears it down. Thread-safe
    to call once each.
    """

    def __init__(
        self,
        market_tickers: list[str],
        bus,
        registry=None,
        base_url: str = WS_URL,
        allow_network: bool = True,
        on_quote: Optional[Callable[[Quote], None]] = None,
        send_initial_snapshot: bool = True,
        reconnect_base_s: float = 2.0,
        reconnect_max_s: float = 30.0,
    ):
        self.market_tickers = list(market_tickers)
        self.bus = bus
        self.registry = registry
        self.base_url = base_url
        self.allow_network = allow_network
        self.on_quote = on_quote
        self.send_initial_snapshot = send_initial_snapshot
        self._reconnect_base = reconnect_base_s
        self._reconnect_max = reconnect_max_s

        self._client = KalshiLive(base_url=_rest_base_for(base_url), allow_live_orders=False)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.connected = False
        self.last_error: Optional[str] = None

        # -- live stats (thread-safe, read by the API from another thread) ----
        # live_ticks: count of well-formed ticker messages received since start.
        # last_tick_ts: epoch seconds of the most recent ticker message.
        # reconnect_count: how many times the loop has (re)connected.
        self._stats_lock = threading.Lock()
        self.live_ticks = 0
        self.last_tick_ts = 0.0
        self.reconnect_count = 0
        self.started_ts = 0.0

    # -- control ------------------------------------------------------------
    def is_live(self) -> bool:
        """True only when creds are loaded AND we're allowed to connect."""
        return self.allow_network and self._client.is_live()

    def start(self) -> bool:
        """Start the streaming loop on a daemon thread. Returns False (no-op) if
        not actually live-capable; True if a loop was started."""
        if not self.is_live():
            return False
        if self._thread is not None and self._thread.is_alive():
            return True
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, name="kalshi-ticker", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # -- asyncio loop -------------------------------------------------------
    def _run_loop(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        backoff = self._reconnect_base
        while not self._stop.is_set():
            try:
                await self._connect_once()
                backoff = self._reconnect_base  # reset on clean connect
            except asyncio.CancelledError:
                break
            except Exception as e:  # noqa: BLE001 — degrade, never crash the host
                self.last_error = f"{type(e).__name__}: {e}"
                self.connected = False
            if self._stop.is_set():
                break
            # backoff before reconnect
            await asyncio.sleep(min(backoff, self._reconnect_max))
            backoff = min(backoff * 2, self._reconnect_max)

    async def _connect_once(self) -> None:
        headers = self._client.ws_auth_headers(WS_PATH)
        async with websockets.connect(
            self.base_url, additional_headers=headers, ping_interval=20, ping_timeout=20,
            open_timeout=15, close_timeout=5,
        ) as ws:
            self.connected = True
            self.last_error = None
            with self._stats_lock:
                self.reconnect_count += 1
                if self.started_ts == 0.0:
                    self.started_ts = time.time()
            # Subscribe to the ticker channel.
            await ws.send(_subscribe_cmd(self.market_tickers, self.send_initial_snapshot))
            async for raw in ws:
                if self._stop.is_set():
                    break
                self._handle(raw if isinstance(raw, str) else raw.decode("utf-8", "replace"))

    # -- parsing ------------------------------------------------------------
    def _handle(self, raw: str) -> None:
        try:
            msg = _loads(raw)
        except Exception:
            return
        if not isinstance(msg, dict):
            return
        mtype = msg.get("type")
        if mtype == "ticker":
            self._handle_ticker(msg.get("msg") or {})
        # 'ok' / 'error' / 'heartbeat' responses are ignored for pricing.

    def _handle_ticker(self, m: dict) -> None:
        ticker = m.get("market_ticker")
        if not ticker:
            return
        bid = _dollars_to_cents(m.get("yes_bid_dollars"))
        ask = _dollars_to_cents(m.get("yes_ask_dollars"))
        if bid is None or ask is None or ask <= bid:
            return  # invalid / crossed / missing — do not publish a bogus quote
        eid = self.registry.get_by_ticker(ticker) if self.registry else None
        eid = eid if eid is not None else 0  # 0 == unmapped live market
        q = Quote(
            exchange_id=eid,
            venue="Kalshi",
            ticker=ticker,
            bid_cents=bid,
            ask_cents=ask,
            live=True,
            raw={"ticker": m},
        )
        with self._stats_lock:
            self.live_ticks += 1
            self.last_tick_ts = time.time()
        if self.on_quote is not None:
            try:
                self.on_quote(q)
            except Exception:
                pass
        self.bus.publish(
            quote_event(eid, "Kalshi", bid, ask, ticker, live=True)
        )

    def status(self) -> dict:
        """Read-only snapshot of the stream's liveness (safe across threads)."""
        with self._stats_lock:
            ticks = self.live_ticks
            last_tick = self.last_tick_ts
            reconnects = self.reconnect_count
            started = self.started_ts
        return {
            "connected": self.connected,
            "live": self.is_live(),
            "live_ticks": ticks,
            "last_tick_ts": last_tick,
            "last_tick_age_s": (time.time() - last_tick) if last_tick else None,
            "reconnect_count": reconnects,
            "uptime_s": (time.time() - started) if started else 0.0,
            "last_error": self.last_error,
            "ws_url": self.base_url,
            "market_tickers": self.market_tickers,
        }


# -- helpers ----------------------------------------------------------------
def _rest_base_for(ws_url: str) -> str:
    """Map a WS URL to a REST base for the signing client.

    The signing client only needs a loaded private key + an API key id; the
    signed payload for WS is path-based and host-independent, so the exact REST
    host doesn't matter for the handshake. We point it at the demo REST base
    (matching the demo creds this package loads).
    """
    return "https://external-api.demo.kalshi.co/trade-api/v2"


def _subscribe_cmd(market_tickers: list[str], send_initial_snapshot: bool) -> str:
    from json import dumps

    params: dict = {"channels": ["ticker"]}
    if market_tickers:
        params["market_tickers"] = market_tickers
    params["send_initial_snapshot"] = send_initial_snapshot
    return dumps({"id": 1, "cmd": "subscribe", "params": params})


def _loads(s: str):
    from json import loads

    return loads(s)


__all__ = ["KalshiTickerStream", "WS_URL", "WS_PATH"]
