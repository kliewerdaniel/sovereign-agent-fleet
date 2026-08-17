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
from exchange.quant.orchestrator import evaluate_quant
from exchange.quant.evidence import verify_quant_evidence
from exchange.quant.learning import new_learner, QuantLearner  # D30 learning loop
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fleet.crypto.foundation import AgentCert  # type: ignore

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

        # Advisory quant producer identity (Ed25519). Used ONLY to sign the
        # QuantEvidence enrichment envelope — never for authorization. Lazily
        # minted once per Exchange instance and cached.
        self._quant_cert: Optional[AgentCert] = None
        self._quant_key = None  # type: ignore[assignment]
        # D30: opt-in learning loop. Lazily created on first /quant/observe.
        self._quant_learner: Optional["QuantLearner"] = None

        # Live streaming ticker (v2 WS). Only constructed/started when the live
        # feed is opted in AND creds are present. Otherwise it stays None and the
        # sim/on-demand feed remains the sole (non-live) source.
        self.stream = None
        self._live_cache: Dict[str, Quote] = {}  # ticker -> latest live quote
        if self.live_feed:
            # Subscribe to ALL markets on the WS and filter/cache client-side:
            # the stream publishes every ticker it sees, _cache_live_quote keeps
            # the latest per ticker, and /quotes / publish_quotes only surface a
            # live quote for an instrument whose ticker is in the cache. Passing
            # an empty ticker list tells Kalshi to push the full tape.
            try:
                from exchange.ticker_stream import KalshiTickerStream

                self.stream = KalshiTickerStream(
                    market_tickers=[],
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
    model_p_yes: Optional[float] = Field(
        None, gt=0.0, lt=1.0,
        description="Advisory quant input (the Brain's P_model). Advisory ONLY — "
                    "never an input to the authorization gate.",
    )
    available_usd: float = Field(
        1000.0, gt=0.0,
        description="Advisory capital for the Kelly sizing proposal. Advisory ONLY.",
    )


class SettlementRequest(BaseModel):
    """D30: one realized Kalshi settlement to fold into the quant learning loop.

    ``model_p_yes`` is the Brain's forecast at forecast time (so calibration can
    measure how far it was from the realized outcome). ``outcome`` is the realized
    YES resolution (1) or NO (0). Advisory — never changes any verdict.
    """

    ticker: str
    model_p_yes: float = Field(gt=0.0, lt=1.0)
    outcome: int = Field(ge=0, le=1)
    ts: int = 0


class CalibrationResponse(BaseModel):
    exchange_id: int
    n_settlements: int
    brier_score: float
    calibration_error: float
    last_rolling_brier: float
    reliability_bins: list
    learned_p_yes: float
    evidence_strength: float
    learner_hash: str = ""


class OrderResponse(BaseModel):
    order_id: str
    authorization: str
    risk: str
    executed_qty: int = 0
    fills: List[dict] = Field(default_factory=list)
    route: Optional[dict] = None
    approval_token: Optional[str] = None
    reason: str = ""
    quant: Optional[dict] = None  # advisory-only quant enrichment (never affects the verdict)


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
    `stream` field reports the live ticker WS status, including a running tick
    count, last-tick age, reconnect count, and uptime (all zero when not live).
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
    stream_status = ex.stream.status() if ex.stream else None
    return {
        "feed": "kalshi-stream" if stream_up else ex.feed.venue,
        "live": live_any,
        "stream_connected": stream_up,
        "stream": stream_status,
        "quotes": out,
    }


@app.get("/stream/status")
def stream_status():
    """Read-only liveness of the live Kalshi v2 Market Ticker WebSocket.

    Exposes connected/live state, a cumulative live tick count, last-tick age,
    reconnect count, and uptime — so operators can see at a glance whether the
    real-time feed is actually flowing. No orders are placed by this stream.
    """
    ex = get_exchange()
    if ex.stream is None:
        return {
            "connected": False,
            "live": False,
            "live_ticks": 0,
            "last_tick_ts": 0.0,
            "last_tick_age_s": None,
            "reconnect_count": 0,
            "uptime_s": 0.0,
            "last_error": None,
            "ws_url": None,
            "market_tickers": [],
            "subscription": "none",
            "seen_markets": 0,
            "note": "live feed not opted in (live_feed=False / KALSHI_LIVE_FEED unset) "
                    "or no creds; running sim-only.",
        }
    return ex.stream.status()


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
    # --- AUTHORITY (verdict) — pure risk math, never sees quant output ----------
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

    # --- ADVISORY QUANT ENRICHMENT (evidence, NOT authority) ------------------
    # Runs AFTER the verdict has been made. The signed QuantEvidence envelope is
    # advisory only: it is recorded on the response so a human/auditor can see
    # the math, but it cannot change authorization, qty, or risk. M0 preserved:
    # decide_trade already returned its result above, independent of this block.
    quant_blob: Optional[dict] = None
    if req.model_p_yes is not None:
        try:
            quant_blob = _advisory_quant(ex, req, client_order_id)
        except Exception:  # noqa: BLE001 — enrichment must never break the order path
            quant_blob = None

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
            quant=quant_blob,
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
        quant=quant_blob,
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


def _quant_producer(ex: "Exchange"):
    """Lazily mint (and cache) the advisory quant producer identity for ex.

    The key signs ONLY the QuantEvidence enrichment envelope. It is never used
    for authorization, approval, or any trust-boundary operation.
    """
    if ex._quant_cert is None:
        key = Ed25519PrivateKey.generate()
        pub_pem = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        cert = AgentCert(
            agent_id=f"quant-advisor-{ex.exchange_id}",
            pubkey_pem=pub_pem,
            role="tool",
            capabilities=["quant_compute"],
            issued_at=0,
            expires_at=2_000_000_000,
            cert_seq=1,
            root_sig="self",
        )
        ex._quant_cert, ex._quant_key = cert, key
    return ex._quant_cert, ex._quant_key


def _advisory_top_event(graph) -> Optional[str]:
    """None-safe id of the event that removed the most uncertainty (Q4)."""
    if graph is None:
        return None
    top = graph.most_informative_event()
    return top.event_id if top is not None else None


def _advisory_quant(ex: "Exchange", req: "OrderRequest", client_order_id: str) -> dict:
    """Run the quant pipeline as PURE advisory enrichment for one order.

    Builds a deterministic QuantContext from the current market quote + the
    request's advisory inputs, runs evaluate_quant, and returns a serialisable
    dict of the signed evidence. Raises on any failure — the caller swallows it
    so the order path is never blocked by quant. M0: this is evidence attached
    AFTER the authorization verdict; it cannot change that verdict.
    """
    from exchange.quant.orchestrator import QuantContext

    # Honesty: prefer a cached LIVE quote; otherwise the active (sim) feed.
    ticker = None
    for inst in ex.registry:
        if inst.venue == "kalshi":
            ticker = inst.venue_ticker
            break
    live = ex._live_cache.get(ticker) if ticker else None
    q: Quote = live if live is not None else ex.feed.quote(ex.exchange_id, ticker=ticker)

    ctx = QuantContext(
        exchange_id=ex.exchange_id,
        model_p_yes=req.model_p_yes,  # type: ignore[arg-type]
        bid_cents=q.bid_cents,
        ask_cents=q.ask_cents,
        side="BUY_YES" if req.side == "BUY" else "SELL_YES",
        available_usd=req.available_usd,
        market_live=q.live,
        ticker=ticker,
        model_id="research-fleet",
        method="quant-orchestrator",
    )
    cert, key = _quant_producer(ex)
    learned = ex._quant_learner.prior() if ex._quant_learner is not None else None
    d = evaluate_quant(ctx, cert, key, proposal_hash=client_order_id, prior_belief=learned)
    ok = verify_quant_evidence(d.evidence, cert)
    return {
        "advisory": True,
        "model_p_yes": d.probability.p_yes,
        "market_mid": d.market.mid_prob,
        "edge": d.edge.edge,
        "ev_cents": d.ev.ev_cents,
        "net_ev_cents": d.ev.net_ev_cents,
        "kelly_recommendation": d.kelly.recommendation,
        "suggested_qty": d.suggested_qty,  # advisory only; execution uses req.qty
        # Q3 advisory evidence
        "bayesian_posterior": d.belief.posterior_p_yes,
        "bayesian_ci": list(d.belief.credible_interval()),
        "bayesian_evidence_strength": d.belief.evidence_strength,
        "regime": d.regime.regime,
        "regime_confidence": d.regime.confidence,
        "regime_drift": d.regime.drift,
        # Q4 advisory evidence: temporal event graph + information gain
        "event_graph_total_ig_bits": d.graph.total_information_gain(),
        "event_graph_final_entropy_bits": d.graph.cumulative_entropy(),
        "event_graph_top_event": _advisory_top_event(d.graph),
        "envelope": {
            "producer": d.evidence.producer_cert_id,
            "proposal_hash": d.evidence.proposal_hash,
            "signature": d.evidence.signature,
            "verified": ok,
        },
        # D30: surface the learned prior actually used (advisory)
        "learned_prior_p_yes": (learned.posterior_p_yes if learned is not None else None),
    }


@app.post("/quant/observe", response_model=CalibrationResponse)
def quant_observe(req: SettlementRequest):
    """D30: feed one realized Kalshi settlement into the learning loop.

    Builds/updates the per-exchange ``QuantLearner`` (opt-in; lazy). Folds the
    outcome as a hard Bernoulli draw into the running conjugate prior and appends a
    ``CalibrationRecord``. ADVISORY ONLY — this route is isolated from ``/order``
    and can never affect a verdict or executed qty.
    """
    ex = get_exchange()
    if ex._quant_learner is None:
        ex._quant_learner = new_learner(ex.exchange_id)
    ex._quant_learner = ex._quant_learner.observe_settlement(
        req.ticker, req.model_p_yes, req.outcome, ts=req.ts,
    )
    report = ex._quant_learner.calibration_report()
    report["learner_hash"] = ex._quant_learner.learner_hash
    return CalibrationResponse(**report)


@app.get("/quant/calibration", response_model=CalibrationResponse)
def quant_calibration(exchange_id: int = 1):
    """D30: read the current calibration report for the learning loop."""
    ex = get_exchange(exchange_id)
    if ex._quant_learner is None:
        ex._quant_learner = new_learner(exchange_id)
    report = ex._quant_learner.calibration_report()
    report["learner_hash"] = ex._quant_learner.learner_hash
    return CalibrationResponse(**report)


def create_app() -> FastAPI:
    return app
