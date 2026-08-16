# Sovereign Exchange — River-Markets Re-Implementation Plan

**Status:** E0–E6 IMPLEMENTED (39 exchange tests green; 263 total with fleet), E7 gap report in progress. Sim-first; Kalshi stubbed; no live creds.
**Date:** 2026-08-16
**Thesis (unchanged):** *Do not trust the model. Trust the execution protocol.*
Authority (signing, approval, secrets, settlement keys) stays local-first; only
signed, cryptographically verifiable artifacts are emitted.

---

## 0. Source model — what River Markets actually is

Reverse-engineered from https://www.rivermarkets.com (full homepage capture,
2026-08-16). River is a **prime brokerage / execution stack for prediction-market
desks** (YC + Haun Ventures, $8.5M seed). Its primitives:

- **Venue aggregation** — one stack across Kalshi, Polymarket, Polymarket US,
  Novig, Crypto.com.
- **Multi-Book + Unified OMS** — place/edit/cancel across venues from one blotter;
  positions, fills, P&L attribution centralized.
- **Smart routing / baskets** — matches contracts across exchanges, routes to best
  price (~2¢ avg improvement).
- **Server-managed complex orders** — Iceberg, Peg, TP/SL, parent/child unwind.
- **Subaccounts** — isolate strategies/books/capital; P&L attributed per subaccount.
- **Unified signed API** — REST + WS, `river_ids` (standardized numeric contract ID
  per venue), **Ed25519-signed requests (private key never leaves process)**,
  streams for books/orders/tradeprints, official Python SDK.
- **Key constraint (FAQ):** River does **NOT** hold customer funds, provide margin,
  custody, or cross-venue netting. It is execution/routing/settlement-facilitation
  *over* venue accounts.

### Why the fit is near-perfect
River's own architecture already mirrors our thesis. Mapping:

| Our fleet primitive | River Markets analog |
|---|---|
| Root-of-trust / local signing | Ed25519-signed API, key never leaves process |
| Agent certs / artifact hashes | `river_ids` (canonical instrument identity) |
| D8 duty separation (R→A→O) | Subaccounts (isolated strategy scopes) |
| Live audit ledger (WS/SSE) | Order/book/tradeprint streams |
| Capability Gateway | Smart routing / venue allowlist |
| D16 → policy → D17 | Risk policy (size/venue/loss) → AUTO vs HUMAN sign-off |

---

## 1. Scope decisions (locked via clarify)

1. **Primary deliverable:** Faithful re-implementation of River's prime-broker
   architecture **AS our own sovereign stack** — we become the venue/aggregator,
   not the desk on top.
2. **Build order:** **Infrastructure-first** — matching engine + order book +
   book/order/tradeprint streams + settlement core first (the hard part), then
   layer governance + signed API.
3. **Venue reality:** **Simulated venues by default**, but with a **pluggable
   venue-adapter interface** so a real exchange can be wired later behind
   credentials. Adapters themselves are stubbed/honest until creds exist.
4. **Code organization:** **New top-level `exchange/` package**, importing
   `fleet.crypto` + `fleet.layers` as a *library* (literal-rebuild pattern from
   `bridge/`+`web/` and `fleet/api/`+`ui/`). Cleanest boundary, additive.
5. **First real venue:** **Kalshi** (regulated US, REST API, API keys, real USD —
   cleanest compliance path). Wired via the venue-adapter interface only after the
   simulated core is proven; live keys never committed.
6. **Settlement model:** **Hybrid** — internal **shadow ledger** for P&L/positions/
   risk + **pass-through execution** to real venue accounts. We track everything
   sovereignly, hold nothing. Mirrors River but with our own tamper-evident audit
   ledger.
7. **Governance wrap:** **Risk-tiered** — AUTO-authorization orders auto-execute;
   HUMAN/BLOCKED tiers trigger D17 + human sign-off; HALLUCINATION intel always
   blocked. Mirrors `fleet/layers/incident.py` matrix.

---

## 2. Architecture

```
                         ┌──────────────────────────────────────────┐
                         │            exchange/  (NEW package)        │
                         │  imports fleet.crypto + fleet.layers ONLY  │
                         └──────────────────────────────────────────┘
                                          │
   ┌──────────────┐   ┌───────────────────┴───────────────────┐   ┌──────────────┐
   │  Venue sim   │   │            Matching Core               │   │  Venue adap. │
   │ (in-process)│   │  OrderBook · MatchingEngine · Fills    │   │  Kalshi (if) │
   └──────┬───────┘   └───────────────────┬───────────────────┘   └──────┬───────┘
          │                                │                              │
          └───────────┬────────────────────┼──────────────────────────────┘
                      ▼                    ▼
              ┌──────────────┐   ┌──────────────────────────────────────┐
              │ Shadow ledger│   │  Streams: books / orders / tradeprints│
              │ P&L positions│   │  (SSE or WS, per river_id subscribe)  │
              └──────────────┘   └──────────────────────────────────────┘
                      │                    │
                      ▼                    ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │  Governance layer (reuse fleet.layers):                             │
   │   Researcher(signal) → Analyst(qualify: sizing/risk/venue) →       │
   │   Operator(route)  — four gates: evidence→capability→policy→approval│
   │   AUTO = auto-execute · HUMAN = D17 human-signed ApprovalRecord ·  │
   │   BLOCKED = fail-closed (HALLUCINATION always blocked)              │
   └──────────────────────────────────────────────────────────────────┘
                      │
                      ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │  Signed API (River-style): REST + WS, Ed25519-signed requests,     │
   │  exchange_ids (our river_id analog), subaccounts, Python SDK.      │
   └──────────────────────────────────────────────────────────────────┘
```

### Module layout (proposed)
```
exchange/
  PLANNING.md                 # this file
  pyproject.toml / __init__.py
  core/
    instrument.py            # exchange_id (numeric), market, outcomes YES/NO
    order.py                 # Order, OrderType (LIMIT/MARKET/ICEBERG/PEG/TP/SL), TIF
    book.py                  # OrderBook (price-time), depth snapshot
    matching.py              # MatchingEngine (deterministic, price-time)
    fills.py                 # Fill, tradeprint emission
    settlement.py            # ShadowLedger: positions, P&L, realized/unrealized
  streams/
    books_stream.py          # SSE/WS per exchange_id
    orders_stream.py
    tradeprints_stream.py
  routing/
    smart_router.py          # cross-venue best-price routing + baskets
    algos.py                 # Iceberg, Peg, TP/SL (server-managed, parent/child)
  venues/
    base.py                  # VenueAdapter ABC (sim + real share interface)
    sim_venue.py             # in-process matching-backed venue
    kalshi_adapter.py        # STUB until creds; honest "not wired" state
  governance/
    policy.py                # trade_authorization(verification, size, venue, action)
                              # → AUTO/HUMAN/BLOCKED (mirrors incident.py)
    supervisor.py            # Researcher→Analyst→Operator trade pipeline
  api/
    app.py                   # FastAPI: REST + WS, Ed25519-signed requests
    sdk.py                   # Python SDK (Sign locally, place anywhere)
  tests/
    test_matching.py
    test_streams.py
    test_routing.py
    test_governance.py
    test_api_signed.py
```

### Reuse from `fleet` (library, not forked)
- `fleet.crypto.foundation` — root Ed25519, agent certs → **order-signing identities**
- `fleet.crypto.chriscrypt.ledger` — **tamper-evident audit ledger** for every
  order/fill/route/sign event
- `fleet.layers.registry` — agent + **subaccount** identity issuance
- `fleet.layers.policy` / `fleet.layers.incident` — authorization matrix template
- `fleet.layers.approval` — **D17 human-signed approval** for HUMAN-tier orders
- `fleet.layers/runtime.py:Operator._act_remediation` — the four-gate pattern we
  mirror for trade execution (G3.1 now lives here at the fleet layer)

---

## 3. Phased build (infrastructure-first)

### Phase E0 — Scaffold `exchange/` package
- `pyproject.toml`, `__init__.py`, import `fleet.crypto` + `fleet.layers` as deps
  (add to a new `requirements-exchange.txt`, kept off the base/GCP audit surfaces).
- No live code; just the module skeleton + this plan.

### Phase E1 — Matching core (the hard part)
- `instrument.py`: `ExchangeId` (numeric, our `river_id` analog), market metadata,
  binary YES/NO outcomes, price ∈ [0.01, 0.99].
- `book.py`: price-time priority, add/cancel/amend, depth snapshot.
- `matching.py`: deterministic price-time matching; produces `Fill`s; emits
  tradeprints. Property tests: no negative inventory, price monotonicity,
  self-trade prevention.
- `settlement.py`: `ShadowLedger` — per-subaccount positions, cash, realized/
  unrealized P&L, fill-by-fill update. **Pass-through only — no real funds.**

### Phase E2 — Streams
- `books_stream` / `orders_stream` / `tradeprints_stream`: subscribe per
  `exchange_id`. SSE now (proven pattern from `fleet/api`); WS later if needed.

### Phase E3 — Venue adapter + sim
- `VenueAdapter` ABC: `submit_order`, `cancel`, `book`, `fills`, `account`.
- `sim_venue.py`: in-process matching-backed venue (deterministic, seeded).
- `kalshi_adapter.py`: **STUB**, honest "not wired" — activated only with creds.

### Phase E4 — Routing + algos
- `smart_router.py`: cross-venue best-price routing + basket split (~2¢ target).
- `algos.py`: Iceberg, Peg, TP/SL — server-managed, parent/child unwind.

### Phase E5 — Governance wrap (risk-tiered)
- `policy.py`: `trade_authorization(verification, size, venue, action)` →
  AUTO/HUMAN/BLOCKED. HALLUCINATION → BLOCKED (fail-closed).
- `supervisor.py`: Researcher(signal)→Analyst(qualify)→Operator(route) pipeline,
  four gates. AUTO = execute; HUMAN = require D17 human `ApprovalRecord`; BLOCKED =
  reject with signed `operator.blocked` audit entry.

### Phase E6 — Signed API + SDK (River-style)
- `api/app.py`: REST + WS, **Ed25519-signed requests** (key never leaves client),
  `exchange_ids`, subaccounts. Every request → audit ledger entry.
- `api/sdk.py`: Python SDK, sync+async, `client.orders.create_order(subaccount_id,
  exchange_id, ...)` mirroring River's ergonomics.

### Phase E7 — UI (optional, reuse pattern)
- New `exchange-ui/` Next.js surface OR extend `fleet/api`+`ui` — terminal,
  multi-book, OMS, P&L, subaccounts. **Deferred** until E1–E6 green.

---

## 4. Compliance / risk notes (real venue = high risk)

- **Keys never committed.** Kalshi API keys live in env / secret store, loaded at
  runtime only. `.gitignore` covers `.env`. Fail-closed if absent.
- **Pass-through only.** We never custody funds; real execution goes to venue
  accounts we own; our ledger is a shadow/attribution layer.
- **Regulated venue.** Kalshi is US-regulated; trading with real funds implies
  KYC/ToS/compliance obligations. The plan treats live mode as **opt-in, gated,
  and the user's legal responsibility** — the agent will not enable it without
  explicit, separate confirmation + creds present.
- **Honest gaps.** Sim venue = not real liquidity. Kalshi adapter = stub until
  wired. Documented in a `GAP_REPORT` for this package before any "done" claim.

---

## 5. Verification gates (per phase, real execution)

- E1: `test_matching.py` property tests green (no negative inventory, price
  monotonicity, self-trade prevented).
- E2: stream emits on fill; replay-watchdog.
- E3: sim venue round-trips an order→fill; adapter stub reports "not wired".
- E4: router beats single-venue by ≥ target on synthetic books.
- E5: AUTO executes, HUMAN requires D17 signature (reuse `test_fleet_api` pattern),
  HALLUCINATION blocked.
- E6: signed request accepted, unsigned/replayed rejected (fail-closed); SDK
  round-trip.
- Full `exchange/tests` + existing `fleet/tests` both green before commit.

---

## 6. Open questions — RESOLVED (2026-08-16)

- **Exchange-id scheme:** ✅ Numeric canonical `exchange_id` (river_id-style) + a
  venue-alias mapping table (`InstrumentRegistry.resolve_venue`). Canonical ID is the
  wire identity; venue native ticker is an alias.
- **Stream transport:** ✅ SSE first (proven in `fleet/api`); WS added in E2 only if
  parity demands.
- **Subaccount model:** ✅ Flat per-strategy subaccounts, P&L attributed per
  subaccount (no nesting).
- **Kalshi timing:** ✅ Kalshi is the first *target* real venue; the `kalshi_adapter`
  is a STUB in E3, wired post-E6 when credentials exist. Build sim-first (E1–E6).

**No code existed until these were resolved. E0/E1 implemented below.**

---

## 7. Implementation status — E0 through E6 (2026-08-16)

All phases E0–E6 are implemented and covered by `exchange/tests/` (39 tests,
all green; full repo `fleet/tests` + `exchange/tests` = 263 green, no
regressions).

| Phase | What shipped | Verification |
|-------|--------------|--------------|
| **E0** | `exchange/` package skeleton, `InstrumentRegistry`, canonical numeric `exchange_id` | imports / structure |
| **E1** | `order.py`, `book.py` (price-time), `matching.py` (deterministic cross, FOK rollback, self-trade prevention), `settlement.py` (shadow ledger, per-subaccount P&L) | `test_matching.py` 11 passed — property tests for no-overfill, price-time, FOK rollback |
| **E2** | `events.py` (pub/sub `ExchangeBus` + `MarketEvent`), `sse.py` (SSE tokenizer, sync + async), engine emits `trade`/`book`/`order.*` events | `test_streams.py` 4 passed |
| **E3** | `venues/base.py` (`VenueAdapter` ABC, `NormalizedOrder`, `RouteResult`), `venues/kalshi.py` (`KalshiStub` — records intent, simulates fill, `is_live()==False`) | `test_venues.py` 4 passed |
| **E4** | `routing/router.py` (`Router`: venue ranking live-first, basket split with exact-qty invariant, price-improvement math) | `test_routing.py` 5 passed |
| **E5** | `governance.py` — risk-tiered `decide_trade` (AUTO/HUMAN/BLOCKED) reusing **fleet as a library**: `Authorization` enum + real `Approval.sign`/`verify_approval` Ed25519 binding (D17 semantics, fail-closed rebinding) | `test_governance.py` 7 passed |
| **E6** | `api.py` — FastAPI surface: `/health`, `/book/{id}`, `/order` (gated by governance), `/approvals/pending`, `/approvals/{token}/decide`, `/stream/{id}` (SSE). Front end has **zero authority** — BLOCKED→403, HUMAN→pending token, AUTO→execute+route | `test_api.py` 5 passed |

### Bugs found & fixed during build (real, not flakes)
1. **Matching loop skipped makers** — `remove_filled` mutated the book level in
   place while iterating it, silently dropping the next resting order. Fixed with
   `for resting in list(level)`.
2. **`_resting_levels` mislabeled its parameter** — mapped `side==BUY→_asks` but
   the arg is the *counter* side, so a BUY aggressor read the bid book. Fixed the
   mapping (BUY hits asks, SELL hits bids).
3. **FOK rollback dropped consumed makers** — `remove_filled` deleted a fully
   filled maker; rollback restored `filled` but never re-inserted it. Fixed via a
   `_consumed` reference dict + re-`add` on rollback.
4. (Test-only) async SSE generator must be primed (`__anext__`) before
   publishing, else the event is lost before subscription.

### Honest gap report (updated 2026-08-16 — live wiring)
- **Kalshi adapter is now REAL (fail-closed).** `KalshiLive` implements Kalshi's
  RSA-PSS request signing (SHA-256 / MGF1-SHA-256 / salt=32) and talks to the
  REST API. Credentials load from a **gitignored** `exchange/.env` (never
  committed; the PEM spans multiple lines and the loader handles that). The
  default route path is **fail-closed**: `route()` rejects unless
  `allow_live_orders=True` is explicitly set on the instance, so the running API
  never places a real order by accident. RSA-PSS signing is unit-verified
  (`test_signature_is_well_formed`).
- **Read-only proof is env-gated.** `get_exchange_status()` performs ONE
  authenticated `GET /exchange/status` (no order). It is skipped in the build
  sandbox, which cannot resolve `*.kalshi.com` (DNS/egress restriction) — not a
  code defect. Run on a networked host with creds to see the 200/401/403.
- **Live market data / price discovery still NONE.** Even with `KalshiLive`, the
  internal matching engine still matches only against orders *we* inject; there
  is no live book feed pulled from Kalshi. P&L is still attributed against
  internal fills.
- **Venue-alias mapping is a stub.** `KalshiLive.route()` maps
  `NormalizedOrder.exchange_id` directly to the Kalshi `ticker`. Real
  integration needs `InstrumentRegistry.resolve_venue` to surface the canonical
  `exchange_id` → Kalshi ticker before any order is safe to send (currently
  guarded by `allow_live_orders=False`).
- **Settlement is shadow-only.** `ShadowLedger` tracks positions/P&L per
  subaccount but holds nothing and settles nothing; real settlement is a
  pass-through to venue accounts (not implemented — would accompany live venue
  wiring).
- **UI (E7, original scope) is DEFERRED.** The control surface is the Fleet
  `ui/` Next.js app pattern; a dedicated exchange UI was scoped optional and is
  not built. The REST+SSE API is the integration contract for whenever it is.
- **No `exchange/` Playwright e2e** (the fleet `ui/` e2e exists separately).
  Venue coverage is via `TestClient`/unit integration tests only.

### Compliance / honesty notes (unchanged from plan)
- Keys never committed; `.gitignore` covers `.env`; fail-closed if absent.
- Pass-through only — never custody funds.
- Live Kalshi mode is opt-in, gated, and the user's legal responsibility; the
  agent will not enable it without explicit separate confirmation + creds.
