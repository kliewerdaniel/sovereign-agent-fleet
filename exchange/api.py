"""Exchange REST + SSE control surface.

Wires the sovereign exchange core (matching engine, books, shadow ledger),
the market event bus/SSE stream, the venue adapters + router, and the
risk-tiered governance wrap into a single FastAPI app.

Honesty contract (mirrors fleet/api):
* The front end has ZERO authority. It never signs, approves, or writes to the
  trust boundary. Orders arrive as requests; the server decides authorization
  (decide_trade) and only executes AUTO-tier orders. HUMAN-tier orders return a
  pending approval token the operator must sign out-of-band (D17 path).
* Venues are STUBS until live creds exist — the API labels every route result
  with its ``status`` (NOT_LIVE for stubs) so the UI can show it honestly.
* All execution is simulated/local; no customer funds are held.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from exchange.core import (
    ExchangeBus,
    InstrumentRegistry,
    MatchingEngine,
    OrderBook,
    bus_stream_gen,
    make_limit_order,
)
from exchange.core.events import EventType, quote_event
from exchange.feeds import KalshiPriceFeed, PriceFeed, Quote, SimPriceFeed
from exchange.governance import (
    Authorization,
    approve_trade,
    decide_trade,
    verify_trade_approval,
)
from exchange.routing import Router
from exchange.venues import KalshiStub

app = FastAPI(title="Sovereign Exchange API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo front end; tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- in-process exchange state --------------------------------------------
_state: Dict[int, "Exchange"] = {}


class Exchange:
    """One sovereign trading venue instance (per exchange_id)."""

    def __init__(self, exchange_id: int, live_venues: bool = False, live_feed: bool = False):
        self.exchange_id = exchange_id
        self.bus = ExchangeBus()
        self.book = OrderBook(exchange_id)
        self.engine = MatchingEngine(self.book, bus=self.bus)
        self.registry = InstrumentRegistry()
        # Seed a canonical instrument with a real Kalshi alias so the venue-alias
        # map is exercised (the router stamps venue_ticker for kalshi orders).
        if exchange_id not in self.registry._by_id:
            try:
                self.registry.register(
                    title="Fed decision (sim-backed, Kalshi alias)",
                    venue="kalshi",
                    venue_ticker="KXFEDDECISION-26JUN-C25",
                    exchange_id=exchange_id,
                )
            except ValueError:
                pass
        self.router = Router({"kalshi": KalshiStub(simulate=True)}, registry=self.registry)
        # Price discovery: deterministic sim feed (the "live" market for sim mode)
        # by default. A REAL Kalshi v2 market-data feed is opt-in via live_feed
        # (or env KALSHI_LIVE_FEED=1); it is fail-closed and only goes live when
        # creds + network are present, otherwise it self-degrades to non-live.
        self.live_feed = live_feed or (os.environ.get("KALSHI_LIVE_FEED", "0") == "1")
        self.feed: PriceFeed = (
            KalshiPriceFeed(allow_network=self.live_feed)
            if self.live_feed
            else SimPriceFeed(anchor_mid_cents=50, half_spread_cents=2)
        )
        self.pending: Dict[str, dict] = {}  # approval_token -> decision
        self.live_venues = live_venues

        # Live streaming ticker (v2 WS). Only constructed/started when the live
        # feed is opted in AND creds are present. Otherwise it stays None and the
        # sim/on-demand feed remains the sole (non-live) source.
        self.stream = None
        self._live_cache: Dict[str, Quote] = {}  # ticker -> latest live quote
        if self.live_feed:
            tickers = [
                inst.venue_ticker for inst in self.registry if inst.venue == "kalshi" and inst.venue_ticker
            ]
            try:
                from exchange.ticker_stream import KalshiTickerStream

                self.stream = KalshiTickerStream(
                    market_tickers=tickers,
                    bus=self.bus,
                    registry=self.registry,
                    allow_network=True,
                    on_quote=self._cache_live_quote,
                )
                if not self.stream.start():
                    self.stream = None  # not live-capable (no creds) -> stay sim
            except Exception as e:  # noqa: BLE001 — degrade, never crash init
                self.stream = None
                self._live_cache.clear()

    def _cache_live_quote(self, q: Quote) -> None:
        if q.ticker:
            self._live_cache[q.ticker] = q

    def close(self) -> None:
        if self.stream is not None:
            self.stream.stop()

    def publish_quotes(self) -> None:
        """Push quotes to the bus for every instrument.

        Honesty rule: if a *live* streaming quote exists for an instrument's
        ticker, publish THAT (live=True) rather than a sim or on-demand pull, so
        the bus never shows a non-live quote where a real one is available.
        Instruments with no live coverage fall back to the active feed.
        """
        for inst in self.registry:
            ticker = inst.venue_ticker if inst.venue == "kalshi" else None
            live = self._live_cache.get(ticker) if ticker else None
            if live is not None:
                q = live
            else:
                q = self.feed.quote(inst.exchange_id, ticker=ticker)
            self.bus.publish(
                quote_event(inst.exchange_id, q.venue, q.bid_cents, q.ask_cents, q.ticker, live=q.live)
            )


def get_exchange(exchange_id: int = 1) -> Exchange:
    ex = _state.get(exchange_id)
    if ex is None:
        ex = Exchange(exchange_id)
        _state[exchange_id] = ex
    return ex


# ---- request/response models ----------------------------------------------
class OrderRequest(BaseModel):
    side: str  # BUY / SELL
    qty: int = Field(gt=0)
    limit_cents: Optional[int] = Field(None, ge=1)
    subaccount_id: str
    venue_hint: Optional[str] = None
    intel: str = "VERIFIED"  # HALLUCINATION -> blocked by policy


class OrderResponse(BaseModel):
    order_id: str
    authorization: str
    risk: str
    executed_qty: int = 0
    fills: List[dict] = Field(default_factory=list)
    route: Optional[dict] = None
    approval_token: Optional[str] = None
    reason: str = ""


class ApprovalRequest(BaseModel):
    token: str
    human_id: str
    # In a real deployment the human_sig is produced by the operator's signed
    # console. Here we accept the bound signature fields directly for the demo.
    human_sig: str
    human_pubkey_pem: str  # PEM-encoded Ed25519 public key of the human approver
    approval_id: str
    capability: str = "exchange.trade_execute"
    artifact_hash: str
    decision: str = "approve"
    reason: str = ""
    ts: int


class ApprovalResponse(BaseModel):
    token: str
    accepted: bool
    detail: str = ""


# ---- endpoints ------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "service": "sovereign-exchange"}


@app.get("/book/{exchange_id}")
def book(exchange_id: int = 1):
    ex = get_exchange(exchange_id)
    snap = ex.book.snapshot().to_dict()
    return {"exchange_id": exchange_id, "book": snap, "depth": ex.book.depth()}


@app.get("/instruments")
def instruments():
    """The canonical instrument registry + venue-alias map (honest liveness)."""
    ex = get_exchange()
    return {
        "count": len(ex.registry),
        "instruments": [
            {
                "exchange_id": inst.exchange_id,
                "title": inst.title,
                "venue": inst.venue,
                "venue_ticker": inst.venue_ticker,
                "venue_alias_resolved": bool(inst.venue_ticker),
            }
            for inst in ex.registry
        ],
    }


@app.get("/quotes")
def quotes():
    """Current price-discovery quotes.

    Honest `live` flag: prefers a real streaming (WS) quote when one is cached
    for the instrument's ticker; otherwise falls back to the active feed. The
    `stream` field reports whether the live ticker WS is connected.
    """
    ex = get_exchange()
    out = []
    for inst in ex.registry:
        ticker = inst.venue_ticker if inst.venue == "kalshi" else None
        live = ex._live_cache.get(ticker) if ticker else None
        q = live if live is not None else ex.feed.quote(inst.exchange_id, ticker=ticker)
        d = q.to_dict()
        d["title"] = inst.title
        out.append(d)
    stream_up = bool(ex.stream and ex.stream.connected)
    live_any = any(q["live"] for q in out)
    return {
        "feed": "kalshi-stream" if stream_up else ex.feed.venue,
        "live": live_any,
        "stream_connected": stream_up,
        "quotes": out,
    }


@app.post("/quotes/tick")
def quotes_tick():
    """Advance the sim price feed one tick and broadcast quote events."""
    ex = get_exchange()
    ex.publish_quotes()
    return {"ok": True}


@app.post("/order", response_model=OrderResponse)
def place_order(req: OrderRequest):
    ex = get_exchange()
    venue_live = ex.live_venues
    client_order_id = f"o_{uuid.uuid4().hex[:12]}"
    decision = decide_trade(
        client_order_id=client_order_id,
        exchange_id=ex.exchange_id,
        side=req.side,
        qty=req.qty,
        limit_cents=req.limit_cents,
        venue=list(ex.router.adapters)[0] if ex.router.adapters else "kalshi",
        venue_live=venue_live,
        intel=req.intel,
    )

    if decision.authorization == Authorization.BLOCKED:
        raise HTTPException(status_code=403, detail=decision.reason)

    if decision.authorization == Authorization.HUMAN:
        # hand back a pending token; operator must sign out-of-band
        token = f"apr_{uuid.uuid4().hex[:12]}"
        venue_name = list(ex.router.adapters)[0] if ex.router.adapters else "kalshi"
        ex.pending[token] = {
            "client_order_id": client_order_id,
            "exchange_id": ex.exchange_id,
            "venue": venue_name,
            "side": req.side,
            "qty": req.qty,
            "limit_cents": req.limit_cents,
            "subaccount_id": req.subaccount_id,
            "venue_hint": req.venue_hint,
            "artifact_hash": decision.artifact_hash,
            "decision": decision.to_dict(),
        }
        return OrderResponse(
            order_id=client_order_id,
            authorization=decision.authorization.value,
            risk=decision.risk.value,
            approval_token=token,
            reason=decision.reason,
        )

    # AUTO: execute internally + route to venue
    order = make_limit_order(
        ex.exchange_id,
        side=_side(req.side),
        qty=req.qty,
        price=(req.limit_cents or 0) / 100.0,
        subaccount_id=req.subaccount_id,
        order_id=client_order_id,
    )
    if req.venue_hint is not None:
        order.venue_hint = req.venue_hint
    res = ex.engine.match(order)
    # route the executed qty to the venue adapter (pass-through intent)
    route = None
    if res.fills:
        from exchange.venues.base import NormalizedOrder

        venue = list(ex.router.adapters)[0]
        norm = NormalizedOrder(
            exchange_id=ex.exchange_id,
            side=req.side,
            qty=sum(f.qty for f in res.fills),
            limit_cents=req.limit_cents,
            client_order_id=client_order_id,
            venue_hint=venue,
        )
        route = ex.router.route(norm).to_dict()
    return OrderResponse(
        order_id=client_order_id,
        authorization=decision.authorization.value,
        risk=decision.risk.value,
        executed_qty=sum(f.qty for f in res.fills),
        fills=[_fill_to_dict(f) for f in res.fills],
        route=route,
        reason=decision.reason,
    )


@app.get("/approvals/pending")
def pending():
    ex = get_exchange()
    return [
        {"token": t, **{k: v for k, v in meta.items() if k != "decision"}}
        for t, meta in ex.pending.items()
    ]


@app.post("/approvals/{token}/decide", response_model=ApprovalResponse)
def decide_approval(token: str, body: ApprovalRequest):
    ex = get_exchange()
    meta = ex.pending.get(token)
    if meta is None:
        raise HTTPException(status_code=404, detail="unknown approval token")
    # verify the human signature binds to the EXACT order (fail-closed)
    from fleet.crypto.foundation import AgentCert  # type: ignore

    # reconstruct the human cert from the PEM pubkey the operator signed with
    ok = _verify_bound(
        ex, meta, body, AgentCert(
            agent_id=body.human_id,
            pubkey_pem=body.human_pubkey_pem,
            role="human-approver",
            capabilities=[body.capability],
            issued_at=0,
            expires_at=0,
            cert_seq=0,
            root_sig="",
        )
    )
    if not ok:
        return ApprovalResponse(token=token, accepted=False, detail="approval verification failed")
    # execute the now-authorized order
    order = make_limit_order(
        ex.exchange_id,
        side=_side(meta["side"]),
        qty=meta["qty"],
        price=(meta["limit_cents"] or 0) / 100.0,
        subaccount_id=meta["subaccount_id"],
        order_id=meta["client_order_id"],
    )
    if meta.get("venue_hint") is not None:
        order.venue_hint = meta["venue_hint"]
    res = ex.engine.match(order)
    del ex.pending[token]
    return ApprovalResponse(
        token=token,
        accepted=True,
        detail=f"executed {sum(f.qty for f in res.fills)} contracts",
    )


@app.get("/stream/{exchange_id}")
def stream(exchange_id: int = 1):
    """Server-Sent Events: market data for the exchange (trades + book)."""
    ex = get_exchange(exchange_id)
    return StreamingResponse(
        bus_stream_gen(ex.bus), media_type="text/event-stream"
    )


# ---- helpers --------------------------------------------------------------
def _side(s: str):
    from exchange.core import OrderSide

    return OrderSide.BUY if s == "BUY" else OrderSide.SELL


def _fill_to_dict(f):
    return {
        "fill_id": f.fill_id,
        "price_cents": f.price_cents,
        "qty": f.qty,
        "maker_order_id": f.maker_order_id,
        "taker_order_id": f.taker_order_id,
    }


def _verify_bound(ex, meta, body, cert) -> bool:
    """Verify the approval record binds to the exact order (D17 semantics)."""
    record = {
        "approval_id": body.approval_id,
        "agent_id": "exchange-operator",
        "action_id": meta["client_order_id"],
        "capability": body.capability,
        "artifact_hash": body.artifact_hash,
        "decision": body.decision,
        "reason": body.reason,
        "human_id": body.human_id,
        "human_sig": body.human_sig,
        "ts": body.ts,
    }
    return verify_trade_approval(
        record=record,
        human_cert=cert,
        client_order_id=meta["client_order_id"],
        capability=body.capability,
        exchange_id=ex.exchange_id,
        side=meta["side"],
        qty=meta["qty"],
        limit_cents=meta["limit_cents"],
        venue=list(ex.router.adapters)[0],
    )


def create_app() -> FastAPI:
    return app
