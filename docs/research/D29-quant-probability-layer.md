# D29 — Quantitative Probability / Edge Intelligence Layer

> **Status:** PLANNING LOCKED. This document resolves the Tier-C conflict in D27
> (§14) for the algorithmic-trading-agent / Kalshi hackathon direction and locks
> the host package, invariant, and Tier split for the quantitative intelligence
> layer. It is the prerequisite for Phase Q1 implementation. **No code in
> `fleet/fin/`, `exchange/governance.py`, or `fleet.crypto` may change as a result
> of this layer except by a later, separately-locked Tier-B change.**
>
> **Thesis (unchanged, inherited from D27/D28):** *Do not trust the model.
> Trust the execution protocol.* The quantitative engine is Layer-1 intelligence
> — it proposes evidence; it never authorizes, decides, sizes-binding, or executes.

---

## 0a. Placement answers — the 10 questions (prompt prerequisite)

The prompt required answering 10 placement questions before the architecture.
Each answer maps a concern onto an existing repo layer, grounded in the
verified repo state (§1.1). The through-line: **mathematics, risk, authority,
execution, and evidence are deterministic, inspectable, and sovereign.** The
model's probability output is the *only* thing that is probabilistic-and-
unverifiable; everything downstream of it is reproducible.

| # | Question | Answer (where it lives) |
|---|---|---|
| 1 | What remains in the existing Sovereign **control plane**? | `fleet` runtime: identity/registry (`fleet.crypto`, `fleet.layers.approval`, registry), the **authorization tiering** (`AUTO`/`HUMAN`/`BLOCKED` via `exchange/governance.decide_trade` + `fleet.fin.domain.assess`), the **signed `TradeAuthorization`** (`fleet/fin/authorization.py`), **execution** (`ExchangeSim.apply` S1/S2 recheck / `exchange/venues`), and the **audit `Ledger`** (`fleet.crypto.chriscrypt.ledger`). None of these move. |
| 2 | Where does `fleet/fin/` stay as-is? | Exactly as shipped (D27 LOCKED). `RiskLayer.assess`, `TradeAuthorization`, `ExchangeSim`, `MarketData.state()`, `verify.py` are the authority/execution/audit surface. The quant layer **does not import or modify them**. |
| 3 | Where does the **exchange** (Kalshi) stack stay as-is? | `exchange/venues/kalshi.py` (stub + fail-closed live), `exchange/feeds.py` (`Quote`, `SimPriceFeed`, `KalshiPriceFeed`), `exchange/core/instrument.py` (binary YES/NO model), `exchange/governance.py` (`decide_trade`). The quant layer *reads* these (Quote/instrument) but never calls `decide_trade` as authority. |
| 4 | Where does `fleet/cognition` stay as-is? | Upstream evidence-quality calibration (`calibration.py`, persona/uncertainty weights, the import wall). The quant layer is a **sibling**, not a child — each binds its own evidence to the proposal independently; neither imports the other. |
| 5 | What is the **boundary** between model and authority? | The `exchange/quant` **import wall** (§2.1): it may import ONLY `fleet.crypto` + `exchange.core.instrument` + `exchange.feeds` + `exchange.core.events`. It cannot reach `fleet.fin`, `exchange.governance`, `fleet.layers.*`, or `fleet.cognition`. A boundary test fails the build on violation. Structurally, the quant layer *cannot become* authority. |
| 6 | What belongs in the **Brain** (intelligence source)? | The raw probabilistic belief `P_model(Y=1\|X)` — *whatever produces it* (research fleet, model-release info, news, Reddit). The Brain supplies the number and its uncertainty. It does **not** compute edge, EV, or sizing; it is the upstream oracle the quant layer records and hashes. |
| 7 | What belongs in **deterministic computation**? | Everything the quant layer computes *from* the Brain's number: `EdgeEstimate` (P_model − P_market), `ExpectedValue` (real Kalshi fees/slippage/execution-prob), `MarketProbability` extraction, and `CalibrationRecord` (Brier vs settlements). All pure functions, hashable (`state()`/`compute_hash()`), recomputable by a verifier. |
| 8 | What belongs in **GCP**? | Only signed, reproducible artifacts replicate (per `GAP_REPORT.md`): the audited `Ledger` entries, the signed `QuantEvidence` envelopes, and calibrated-model metadata. **No live trading, no model inference, no secrets.** GCP is a read-only audit mirror, never an execution surface. |
| 9 | What stays **local**? | The model itself, `KALSHI_*` credentials (gitignored `.env`), the sim-first market feed (`SimPriceFeed`), all private keys, the verifier's recomputation, and the honest "sim vs live" flag on every quote. Local-first is the default; live is opt-in + user's legal responsibility. |
| 10 | What is the **smallest credible hackathon MVP**? | (see §0b) A single script that: (a) takes a Brain `P_model` for one Kalshi market, (b) extracts `P_market` from a `Quote`, (c) computes `Edge` + `ExpectedValue` with fees, (d) emits a signed `QuantEvidence` envelope bound to a `TradeProposal`, (e) shows that removing the envelope leaves `decide_trade`'s disposition **identical** (M0), and (f) verifies the envelope signature + proposal binding. No live orders; sim feed only. |

### 0b. Smallest credible hackathon MVP (Q10, concrete)

A 6-file MVP, all local, sim-only, ~0 new authority code:

1. `exchange/quant/probability.py` — `ProbabilityEstimate`, `MarketProbability`,
   `EdgeEstimate`, `extract_market_probability`, `estimate_edge`. *(built Q1)*
2. `exchange/quant/expected_value.py` — `ExpectedValue`, `expected_value`
   (fees/slippage/exec-prob). *(built Q1)*
3. `exchange/quant/evidence.py` — `QuantEvidence`, `build_quant_evidence`,
   `verify_quant_evidence` (signed envelope bound to `proposal_hash`). *(built Q1)*
4. `exchange/quant/calibration.py` — `CalibrationRecord`, `brier_score`
   (proves the Brain's `P_model` is honest over time). *(built Q1)*
5. `demo/quant_demo.py` — wires a `SimPriceFeed` quote → Brain `P_model` →
   edge/EV → signed envelope → a `TradeProposal` → prints `decide_trade`
   disposition **with and without** the envelope (identical ⇒ M0 shown live).
6. `exchange/tests/test_quant_q1.py` — the 15 real tests. *(built Q1)*

Demo narrative: "The model *proposes*; the math *estimates*; the protocol
*authorizes*; the environment *enforces*; the ledger *proves*." Compelling at a
hackathon without ever being an unsafe black-box trading bot — because the
authorization, execution, and verification are the existing, locked, deterministic
Sovereign substrate, and the quant layer is auditable evidence, not authority.


---

## 0. Why this document exists

Two prior directions were drafted against a *hypothesized* repository that did
not match the current tree (they assumed `fleet/fin/` was a thin scaffold and
proposed building a 24-section quant stack largely from zero, and assumed
`exchange/governance/policy.py` + `supervisor.py` existed). Direct inspection
of the shipped repo (D27 §0 verification + fresh reads of `fleet/fin/`,
`fleet/cognition/`, `exchange/`, and D27/D28) showed:

- `fleet/fin/` is **complete, locked, and tested** — `RiskLayer.assess` (10+
  deterministic dimensions), `TradeAuthorization` (full Ed25519 field list),
  `ExchangeSim.apply` (S1/S2 state-binding recheck), `verify.py` (recompute-and-
  check). D27 status: *PLANNING LOCKED — AND IMPLEMENTED.*
- `exchange/` is a **separate, newer, in-progress** top-level package — a
  from-scratch River-Markets-style execution stack. It already owns the Kalshi
  knowledge: `venues/kalshi.py` (`KalshiStub` + fail-closed `KalshiLive`),
  `feeds.py` (`Quote` with `bid_cents`/`ask_cents`, `SimPriceFeed`,
  `KalshiPriceFeed` parsing `yes_bid_dollars`/`yes_ask_dollars`),
  `core/instrument.py` (binary YES/NO, `cents`/`dollars`), and `governance.py`
  (`decide_trade` AUTO/HUMAN/BLOCKED). Status: *E0–E6 implemented, E7 gap report
  in progress.* NOTE: the implemented governance module is `exchange/governance.py`
  (a single file), **not** the `governance/policy.py` + `supervisor.py` the
  original plan sketched — PLANNING.md layout diverged from implementation.
- `fleet/cognition/calibration.py` calibrates **evidence/reasoning quality**
  (persona weights, uncertainty temperature) via `AlignmentEvent` — it is
  **not** market-probability calibration (Brier score vs Kalshi settlements).
  The shared word "calibration" refers to two different things. Conclusion in §2.
- D27 §14 Tier C **explicitly forbids** "alpha research" and "strategy
  optimization" inside `fleet/fin/`. A probability/edge engine is, by any honest
  reading, alpha research. Silently building it in `fleet/fin/` would violate
  the lock.

This document resolves the conflict architecturally (§2) rather than by
stepping around it, following the D28 precedent exactly.

---

## 1. Repository analysis — what exists, what is absent

### 1.1 Real (do NOT rebuild)
| Concern | Where | Notes |
|---|---|---|
| Risk engine (10 dims, pure) | `fleet/fin/domain.py::assess` | locked, tested, recomputable by verifier (I15) |
| TradeAuthorization + Ed25519 signing | `fleet/fin/authorization.py` | full field list; `verify_trade_authorization` |
| S1/S2 state-binding | `fleet/fin/exchange_sim.py::apply` | `portfolio_pre_hash` re-checked inside apply (I7) |
| Standalone verifier | `fleet/fin/verify.py` | recompute risk+disposition+TA; CRITICAL on mismatch |
| Market-data provenance | `fleet/fin/market_adapter.py` | signed envelope → normalized `MarketData` |
| Cognition import wall | `fleet/cognition/__init__.py` + `fleet/tests/test_boundary.py` | may import ONLY `fleet.crypto` + `fleet.layers.handoff` |
| Evidence calibration | `fleet/cognition/calibration.py` | evidence-quality calibration, NOT market-prob |
| Kalshi venue adapter | `exchange/venues/kalshi.py` | stub + fail-closed live; RSA-PSS signing |
| Kalshi market data | `exchange/feeds.py` | `Quote(bid_cents, ask_cents)`, `SimPriceFeed`, `KalshiPriceFeed` |
| Binary instrument model | `exchange/core/instrument.py` | `ExchangeId`, `cents`/`dollars`, YES/NO |
| Trade governance | `exchange/governance.py::decide_trade` | AUTO/HUMAN/BLOCKED, reuses `fleet` as library |
| Signed hash-chain ledger | `fleet.crypto.chriscrypt.ledger.Ledger` | `append(kind, payload)`; `verify_chain` |
| Provenance primitive | `fleet.crypto.foundation.canonical_bytes` + `sha256` | every record uses `state()`+`compute_hash()` |

### 1.2 Genuinely absent (the actual gap this layer fills)
- `ProbabilityEstimate` — `P_model(Y=1|X)` as a typed, hashable, signed record.
- `EdgeEstimate` — `P_model − P_market` (the central opportunity object).
- `ExpectedValue` — binary-EV with real Kalshi cost structure (fees, slippage,
  execution probability, liquidity).
- Market-implied probability extraction from Kalshi order-book data (`yes_bid`/
  `yes_ask` midpoint / last), already carried by `Quote` but never turned into a
  `P_market` record.
- Market-probability calibration (Brier score vs actual Kalshi settlements) —
  **distinct** from `fleet/cognition/calibration.py`.
- Kelly / fractional-Kelly **sizing proposal** flowing in as a *proposed* qty,
  not a binding size.
- A signed **quant-envelope** carrier that binds the quant evidence to the
  existing `TradeProposal`/`proposal_hash` the same way `fleet/cognition`'s
  enrichment binds — readable-by-governance, ignored-by-gates.

### 1.3 Which host — `fleet/quant/` vs `exchange/quant/`
**Decision: `exchange/quant/`.** Rationale:
1. The Kalshi-aware primitives (venue adapter, price feed, binary instrument,
   risk-tiered governance) live under `exchange/`, not `fleet/fin/`.
2. D27 Tier C forbids alpha research in `fleet/fin/`; placing it in `exchange/`
   keeps the financial workload's lock intact.
3. `exchange/` already imports `fleet.crypto` + `fleet.layers` as a *library*
   (literal-rebuild boundary) and runs sim-first — the same discipline this
   layer needs.
4. Phase Q6 (live Kalshi wiring) follows `exchange/`'s existing sim-first-then-
   adapter sequencing, which is already specified and partially built.

---

## 2. Resolving the Tier-C conflict: where "alpha research" goes

D27 locks `fleet/fin/` scope and excludes alpha research. `exchange/PLANNING.md`
does not carry that exclusion (it is a newer, still-open package). The honest
resolution is architectural, mirroring D28 exactly:

**A probability/edge engine is Layer-1 intelligence, not Layer-2 authority.**
D28 already establishes the precedent: `fleet/cognition/` sits upstream of
governance, produces signed *evidence* artifacts, and is import-boundary-
restricted so it structurally cannot become an authority path. **This layer
follows that pattern, not the original prompt's "first-class deterministic
subsystem" framing** (which conflated "deterministic math" with "sits in the
authority chain" — `RiskLayer` is both; this new engine is deterministic but
*advisory*, like `ConsensusGate`).

### 2.1 Import boundary (enforced by a boundary test, before any logic)
`exchange/quant/**` may import ONLY:
- `fleet.crypto` (sign / verify / audit primitives)
- `fleet.crypto.chriscrypt.ledger` (the existing ledger — extend, never clone)
- `exchange.core.instrument` (read instrument model)
- `exchange.feeds` (read `Quote`/`PriceFeed` for market probability)
- `exchange.core.events` (read market events for streaming stats, Phase Q2+)

`exchange/quant/**` must NEVER import:
- `fleet.fin` (`domain.assess`, `authorization`, `exchange_sim`) — do not touch
  the locked risk engine or its authorization.
- `exchange.governance` (`decide_trade`) — it may *read* a disposition only as
  an output target, never call it as an authority.
- `fleet.layers.gateway` / `policy` / `runtime` / `incident` / `approval` /
  `registry` — no authority/execution imports.
- `fleet.cognition` — keep the two intelligence layers independent; each binds
  its own evidence to the proposal separately.

A `test_boundary.py` for `exchange/quant/` (mirroring
`fleet/tests/test_boundary.py`, AST-based) fails the build if any forbidden
import appears. **This is written before any quant logic, per Q0.**

### 2.2 Evidence carrier, not authority input
The quant outputs (`ProbabilityEstimate`, `EdgeEstimate`, `ExpectedValue`, a
Kelly-derived *suggested* size) become a **signed `QuantEvidence` envelope**
carried alongside the `TradeProposal`, bound to `proposal_hash`. This mirrors
D28 §6.3's `enrichment` split:
- the `TradeProposal` (or `NormalizedOrder`) stays the **governance surface**;
- the `QuantEvidence` is **enrichment** — logged, integrity-verifiable, and
  **ignored by `RiskLayer`/`decide_trade`** in the authorization decision.

Governance MAY *read* quant fields as advisory signals (escalation-only, D28
D-B), exactly as consensus does today. The disposition logic (`AUTO`/`HUMAN`/
`BLOCKED`) stays exactly where it is, written exactly how it is written now.
A Kelly-derived size enters only as the *proposed* `qty` on the proposal — the
existing `RiskLayer`/`decide_trade` still independently re-checks it against
`max_order_usd` / position / size limits and can still downsize or block.

### 2.3 M0 applies to this package exactly as to `fleet/cognition/`
> No security invariant may depend on the quant layer's output. The system's
> authorization outcome is identical with or without `QuantEvidence` attached.

The existing `fleet/fin/verify.py` M0 check (strip enrichment → recompute →
identical disposition) already covers any enrichment bound to the proposal,
including `QuantEvidence`, with zero change to `verify.py`.

---

## 3. The invariant (restated for this package)

```
Model proposes ≠ Quant estimates ≠ Exchange(cognition) enriches ≠ Quant/Model decides
             ≠ Quant/Model authorizes

QuantEvidence (probability / edge / EV / regime / Kelly-size proposal)
   → same signed binding to proposal_hash (D28-style enrichment)
   → same RiskLayer / exchange governance policy (UNCHANGED)
   → same authorization tiering (UNCHANGED)
   → same signed authorization (UNCHANGED)
   → same execution path (UNCHANGED, sim-first)
   → same audit ledger (UNCHANGED)
   → same independent verifier, extended to recompute the new evidence
     types the same way it already recomputes RiskAssessment (I15 extended)
```

Every new record type gets a typed contract and a `state()`/`compute_hash()`
pair matching `MarketData`. Every consequential transition is auditable through
the *existing* `Ledger`. **No new signing scheme, no new ledger, no new verifier
class** — extend `fleet/fin/verify.py`'s recompute pattern, do not clone it.

---

## 4. Package boundary diagram

```
                         ┌──────────────────────────────────────────┐
                         │  exchange/quant/  (NEW, Layer-1 evidence) │
                         │  imports ONLY: fleet.crypto |            │
                         │   exchange.core.instrument |             │
                         │   exchange.feeds | exchange.core.events  │
                         └──────────────────────────────────────────┘
                                          │  produces
                                          ▼  signed QuantEvidence
                         ┌──────────────────────────────────────────┐
                         │  TradeProposal / NormalizedOrder          │
                         │   ├─ governance_surface  (unchanged)       │
                         │   └─ QuantEvidence  (enrichment, ignored   │
                         │                      by gates)             │
                         └──────────────────────────────────────────┘
                                          │
                                          ▼  (UNCHANGED authority path)
                         ┌──────────────────────────────────────────┐
                         │  RiskLayer.assess  +  decide_trade        │
                         │   (fleet/fin / exchange/governance)       │
                         │   read quant fields as ADVISORY ONLY      │
                         └──────────────────────────────────────────┘
                                          │
                                          ▼
                         ExchangeSim / VenueAdapter → Ledger → verify.py
```

---

## 5. Staged plan (this effort only — not a restart of financial/exchange work)

Check what is *already queued* before proposing: D27 §15 Tier B lists
(11) live free-feed, (12) cross-feed consistency, (13) LIMIT, (14) graded
`ConsensusGate`, (15) daily-loss/frequency/drawdown — confirm done vs open and
do not re-propose finished items. `exchange/` E7 already implements price
discovery + live feed; do not duplicate it.

| Phase | Scope | Load-bearing? |
|---|---|---|
| **Q0** | This decision doc + `test_boundary.py` for `exchange/quant/` | **Yes** — gates all later phases | IMPLEMENTED |
| **Q1** | Probability core: `ProbabilityEstimate`, market-implied prob from `Quote`, `EdgeEstimate`, `ExpectedValue` (real Kalshi fees/slippage), `QuantEvidence` envelope bound to `proposal_hash` + verified by holder; calibration record (Brier vs settlements) as sibling to `fleet/cognition/calibration.py` | **Yes** | IMPLEMENTED |
| **Q2** | Streaming + anomaly: online stats, rolling windows, z-score/CUSUM/Page-Hinkley over `quote`/`trade` events already on `ExchangeBus` | Medium | IMPLEMENTED (`exchange/quant/streaming.py` + `test_quant_q2.py`; 9 tests) |
| **Q3** | Bayesian updating + regime detection (HMM/Kalman) as evidence fields | Medium | IMPLEMENTED (`exchange/quant/bayesian.py` + `regime.py` + `test_quant_q3.py`; 16 tests) |
| **Q4** | Temporal market/event graph + information gain (local-first) | Low | IMPLEMENTED (`exchange/quant/eventgraph.py` + `test_quant_q4.py`; 12 tests) |
| **Q5** | Kelly sizing proposal → proposed `qty` on proposal (advisory) | Medium | IMPLEMENTED (`exchange/quant/kelly.py` + `test_quant_q5.py`; 9 tests) |
| **Q6** | Quant orchestration: wire Q1+Q2+Q5 into one signed `QuantEvidence` pipeline via `evaluate_quant()`; `QuantContext` carries deterministic inputs, `QuantDecision` is pure advisory data (M0), optional `StreamAnalyzer` folds into audit binding | Medium | IMPLEMENTED (`exchange/quant/orchestrator.py` + `test_quant_q6.py`; 6 tests) |
| **Q6-live** | Wire the orchestrator into `exchange/api.py`'s `place_order` as advisory enrichment — signed `QuantEvidence` attaches to the order response, verdict path (`decide_trade`) untouched, executed qty = `req.qty` (never the Kelly suggestion) | Medium | IMPLEMENTED (`exchange/api.py` `_advisory_quant` + `test_quant_api.py`; 5 tests) |

> Note: the original Q6 ("live Kalshi wiring") is the `exchange/`-level sim-first-then-adapter
> market-data work — that sequencing already exists in `exchange/feeds.py` / `ticker_stream.py`
> (sim feed is authoritative, live is fail-closed opt-in). The quant-side orchestration + API
> advisory binding above is the in-package Q6-live completed here; no live orders ever occur.


---

## 6. Tier split for this package

**TIER A — non-negotiable (this pass):**
1. `exchange/quant/` package skeleton + `test_boundary.py` (import wall enforced).
2. `ProbabilityEstimate`, `EdgeEstimate`, `ExpectedValue` typed records with
   `state()`/`compute_hash()` (mirror `MarketData`).
3. Market-implied probability extraction from a Kalshi `Quote` (midpoint / last),
   feeding `Edge = P_model − P_market`.
4. `ExpectedValue` with real Kalshi cost terms: fee per contract, expected
   slippage from half-spread, execution probability (limit vs market), liquidity
   penalty.
5. `QuantEvidence` signed envelope (built + verified via `fleet.crypto`) bound to
   `proposal_hash`; holder verifies signature + binding without trusting content.
6. `CalibrationRecord` (Brier score vs settlements) as a **sibling** module —
   distinct from `fleet/cognition/calibration.py`.
7. Real tests: edge computation, EV with fees, envelope sign/verify, boundary
   enforcement. Confirm `fleet/fin/` + `exchange/governance.py` byte-untouched.

**TIER B — strongly recommended (later Q phases):**
8. Phase Q2 streaming/anomaly (online stats, CUSUM, Page-Hinkley).
9. Phase Q3 Bayesian updating + regime detection (evidence fields).
10. Phase Q5 Kelly sizing proposal (advisory qty).

**TIER C — explicit OUT (do not build here):**
- Any change to `RiskLayer.assess` disposition logic or `required_trade_authorization`.
- Any second authorization path, signing scheme, ledger, or verifier class.
- Reinventing the matching engine, order book, or Kalshi adapter (already exist).
- Reinventing evidence-quality calibration (`fleet/cognition/calibration.py`).
- Live execution enablement (belongs to `exchange/` Q6, sim-first, gated, user's
  legal responsibility per D27/D-E7).

---

## 7. What a verifier can later prove (honesty contract)

For every quant-backed trade the verifier (extending `fleet/fin/verify.py`, not
replacing it) can recompute: given the logged `ProbabilityEstimate` inputs and
the pure functions in `exchange/quant/`, the recorded `edge_hash` /
`ev_hash` reproduce; the `QuantEvidence` signature verifies under its producer
cert; the envelope binds to the logged `proposal_hash`. It does **not** prove
the model's `P_model` is *correct* — only that the math from stated inputs is
reproducible and the evidence was authentic and unmodified (D28 D-D).

> **The model proposed; the quant estimated; the protocol authorized; the
> environment enforced; the math proves it.**
