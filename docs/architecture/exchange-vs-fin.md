# `exchange/` (flagship) vs `fleet/fin/` (reference)

There are **two** financial workloads in the repo. They are intentional, not duplicated by
mistake. This document states their relationship so a reader knows which to study.

## The short version

- **`fleet/fin/`** is the **reference** financial workload (D27). It established the
  governed-execution pattern: RiskLayer → `required_trade_authorization`
  (AUTO/HUMAN/BLOCKED) → `TradeAuthorization` → `ExchangeSim.apply` →
  `fleet/fin/verify.py`. It is the cleanest, smallest proof of "the domain changes, the
  authority protocol does not."
- **`exchange/`** is the **flagship** financial workload (D29/D30). It is the more advanced
  evolution: an actual sovereign prediction-market **venue** (matching engine, order books,
  shadow ledger, smart routing, live Kalshi adapter) **plus** a quantitative cognition layer
  (`exchange/quant/` — probability, edge, Kelly, Bayesian, regime, streaming, ZK attestation).

Both reuse the **same governance substrate** (`fleet`): identity, registry, crypto, policy,
gateway, approval, consensus, audit. Only the Layer-3 environment and the cognitive
evidence layer differ.

## Side-by-side

| Aspect | `fleet/fin/` (D27 reference) | `exchange/` (D29/D30 flagship) |
|--------|------------------------------|--------------------------------|
| Layer 3 | `ExchangeSim` (paper portfolio) | sovereign venue: `MatchingEngine` + `OrderBook` + `ShadowLedger` + routing |
| Evidence layer | none (deterministic strategy / brain proposal) | `exchange/quant/`: probability, Bayesian, Kelly, regime, streaming, ZK |
| Risk/authorization | `RiskLayer.assess` + `required_trade_authorization` | `exchange/governance.decide_trade` (reuses `fleet.layers.incident.Authorization`) |
| Market data | `MarketData` adapter (replay/live) | `feeds.py`: `SimPriceFeed` + real Kalshi v2 + WSS ticker stream |
| Verifier | `fleet/fin/verify.py` (PASS/FAIL/CRITICAL) | authorization bound in `place_order`; verifier pattern present |
| UI | `demo_app.py` Streamlit (incident demo shape) | **no dedicated UI** (E7 deferred); REST+SSE `api.py` is the contract |
| Status | complete, tested, **kept as reference** | complete venues+quant, tested; live Kalshi env-gated/fail-closed |

## Why keep both

`fleet/fin/` is the pedagogical anchor: it shows the governed-execution pattern with the
least cognitive noise, and its standalone `verify.py` is the clearest demonstration of the
Run-A = Run-B verifiability thesis. `exchange/` is the demonstration that the pattern scales
to a *real* venue with *real* quantitative reasoning attached — without ever letting the
quant layer become the authority.

They are **not** forced to merge right now. The relationship is documented; consolidation is
an explicit future decision, not an implicit cleanup.

## Boundaries that hold across both

- Quant/Bayesian/Kelly are **evidence**, never authorization inputs (M0).
- Risk/authorization is a **pure function** in governance; the quant output is attached as
  advisory enrichment only.
- Execution validates the authorization against the **exact evaluated state** before mutating
  anything (S1≠S2 defense).
- Everything is signed into the ledger; verification needs only public keys.
