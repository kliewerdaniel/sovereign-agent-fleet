# D27 — Financial Agent Reference Workload: Architecture & Scope Lock

> **Status:** PLANNING LOCKED — **AND IMPLEMENTED**. This document consolidates
> the decisions made across Rounds 1–6 of the Sovereign Agent Fleet
> financial-reference-workload discovery and is the authoritative record for the
> shipped `fleet/fin/` implementation (domain, authorization, exchange_sim,
> market_adapter, strategy, standalone `verify.py`); wired into `runtime.py`.
> No new scope or design remains open.
>
> **Central thesis (unchanged):** *The model is not the authority. The
> execution protocol is.* Sovereign Agent Fleet is a **general-purpose,
> local-first authorization, verification, and execution-control substrate for
> autonomous agents.** The financial system is a **second reference workload**
> alongside the existing incident-remediation workload. The domain changes; the
> authority protocol does not.

---

## 1. Hard architectural constraints (Rounds 1–6)

| ID | Constraint |
|----|-----------|
| C1 | **Paper-only.** No real brokerage, real financial accounts, real capital, live order execution, or real settlement — ever, unless explicitly discussed as a hypothetical future architecture. Simulated settlement only. Realistic external market data is permitted; execution remains deterministic and simulated. |
| C2 | **Direction B-as-D.** Fleet remains a general substrate; finance is one of (at least) two reference workloads. Fleet is NOT a trading application. |
| C3 | **Both workloads retained.** Incident + financial share identity, registry, certs, capabilities, policy, gateway, approval, crypto, audit, verification, runtime principles. Only domain workloads differ. |
| C4 | **Market data is an adapter, not a fundamental authority dependency.** Live/free feed is optional; deterministic replay is authoritative and offline. A demo must never require an external service to demonstrate core security properties. |
| C5 | **GCP optional, off by default** for the financial workload. Local system authoritative. GCP may replicate signed artifacts only and holds no authority over identity, policy, signing, approval, or execution. |
| C6 | **Dual-brain consensus is advisory only**, never a source of truth. Graded `agreement_score` influences authorization tier but cannot rescue a policy violation. Genuine model independence is a deployment property, documented, not protocol-enforced. |
| C7 | **Completion bar.** Complete reference implementation of the authorization/control plane **plus** a complete financial vertical slice. Every security mechanism on the golden path must be real, implemented, and tested. No "security theater" — superficial trading demo on mostly mocked security is explicitly rejected. |
| C8 | **Brain independence.** Local inference is the canonical sovereign path. Gemini is a first-class brain path, not a different architecture. The same schema/handoff/policy/capability/verification/approval/execution protocol applies regardless of which brain produced the proposal. |
| C9 | **No premature abstraction.** Prove the pattern with two independent workloads before abstracting into a generic consequential-action framework. |

---

## 2. Three-layer trust model (Round 3 central architecture)

Each layer trusts only the interface immediately below it. This is the central
conceptual architecture of the project.

```
┌─────────────────────────────┐
│       LAYER 1 — INTELLIGENCE │  observe, reason, propose, disagree,
│  (may be wrong / compromised)│  err. NO authority.
└──────────────┬──────────────┘
               │ proposal (schema-validated, evidence-grounded)
               ▼
┌─────────────────────────────┐
│    LAYER 2 — DETERMINISTIC   │  identity, capability, policy, risk,
│         GOVERNANCE           │  approval requirement, cryptographic binding.
│  (model-agnostic; never      │  NO reasoning, NO execution.
│   reasons about the model)   │
└──────────────┬──────────────┘
               │ signed, state-bound TradeAuthorization
               ▼
┌─────────────────────────────┐
│  LAYER 3 — CONSEQUENTIAL     │  verifies authorization, verifies state,
│     ENVIRONMENT (paper)      │  performs transition, issues receipt.
│  (does NOT trust the model)  │
└──────────────┬──────────────┘
               │ ExecutionReceipt
               ▼
        INDEPENDENT VERIFIER (public keys only)
```

| Layer | Trusts | Does NOT trust | Responsibility |
|-------|--------|---------------|---------------|
| 1 Intelligence | its own inputs (evidence) | the environment; the ledger | observe, reason, propose, disagree, err, be compromised |
| 2 Governance | identity registry + its own pure policy/risk functions | the model's reasoning or "confidence" | authenticate, authorize, bind cryptographically |
| 3 Environment | the signed authorization + current state | the model | validate, transition, receipt |

**Six-stage security framing (locked):**
```
Model:              "What should we do?"            (untrusted, proposal-only)
Evidence system:    "What do we know, and can the proposal be grounded?"
Policy/risk engine: "What authority does this action require?"
Operator:           "Can I construct a valid authorization?"
Environment:        "Is this authorization valid for the state that exists right now?"
Verifier:           "Can I independently prove what happened?"
```

**Incident already exhibits this (implicitly).** Financial makes Layer 3 explicit
and stateful: `ExchangeSim.apply` re-verifies `portfolio_pre_hash` against the
live account before mutating — independent validation of the authorization
against current reality, exactly as `SimEnv` validates transitions.

---

## 3. Meta-invariant M0 (Round 4 addition)

> **No financial security invariant may depend on model behavior.**

The model may lie, hallucinate, disagree, or deliberately propose the worst
possible action — the authority boundary must hold regardless. Model
`confidence`, `thesis`, or "agreement" appears in **zero** authorization paths.
The only model-derived artifacts entering Layer 2 are (a) the proposal content
(grounded via D16 evidence refs) and (b) the advisory consensus signal (which
can only escalate).

---

## 4. Consolidated security-invariant catalog (Rounds 1–5)

Legend: **ENF** = enforced today in `fleet/` (current suite = 480; the historical D26 baseline was a 205-test suite);
**SPEC** = locked design, implemented in `fleet/fin/`;
**VER** = independently verifiable by `fleet/fin/verify.py`.

| # | Invariant | Basis (never model) | Status | VER |
|---|-----------|---------------------|--------|-----|
| M0 | No security invariant depends on model behavior | — | ENF (by construction) | VER |
| I1 | Model cannot directly execute consequential action | 4-gate Operator; Brain has no `act` | ENF | VER |
| I2 | Action outside capability scope denied | `Gateway` + default-deny P1 | ENF (policy) | VER |
| I3 | Approval cannot authorize a different trade | `verify_approval` binds action_id+cap+ta_hash | ENF | VER |
| I4 | Revoked/rotated identity cannot execute | `Registry.discover`→None; Gateway cache re-validates cert_seq (A3) | ENF | VER |
| I5 | Authorization not replayable | nonce + idempotency + `expiration`; `Runtime.idempotent` | ENF | VER |
| I6 | Tampered TA rejected | `ExchangeSim` verifies TA sig over canonical body | SPEC (pattern ENF) | VER |
| I7 | TA evaluated at S1 cannot run at S2 | re-verify `portfolio_pre_hash` == live account hash **inside** `apply` | SPEC (critical) | VER |
| I8 | Excess position blocked | `RiskLayer.position_pct_after` → BLOCKED/HUMAN | SPEC | VER |
| I9 | Unauthorized asset blocked | `RiskLayer.asset_allowed` + mandate | SPEC | VER |
| I10 | Stale market data rejected | `MarketData.ts` → `data_fresh` → BLOCKED/HUMAN | SPEC | VER |
| I11 | Forged approval rejected | `verify_approval` fail-closed | ENF | VER |
| I12 | Model disagreement cannot become VERIFIED/authorized | `ConsensusGate` graded → advisory only; escalation-only | ENF + SPEC grade | VER |
| I13 | All gates fail closed | missing/invalid input → DENY/BLOCKED | ENF | VER |
| I14 | Audit ledger tamper-evident | Ed25519 hash-chain + checkpoint | ENF | VER |
| I15 | Risk decision recomputable by verifier | full `RiskAssessment`+inputs LOGGED; verifier imports pure `RiskLayer` | SPEC (headline) | VER |
| I16 | Feed authenticity proven (not truth) | `verify_tool_envelope`; cross-feed when ≥2 | ENF (auth) / LOGGED (truth) | VER (auth only) |
| I17 | GCP holds no authority | one-directional mirror; verify-only console | ENF | VER |

No invariant is merely documented for the financial path. The one honest
non-guarantee is **I16's truth axis**: a signed feed is authentic, not true;
cross-feed validation occurs only when ≥2 independent feeds are available.

---

## 5. Uniform fail-closed taxonomy (Round 5 lock)

Missing, malformed, expired, unverifiable, or contradictory security-relevant
input produces a **non-executing** result. No gate reads absence as permission.

| Gate | On missing / invalid / contradictory input |
|------|--------------------------------------------|
| D16 (evidence) | HALLUCINATION → BLOCKED |
| Gateway (capability) | unknown role/cap → DENY; revoked/expired cert → DENY |
| RiskLayer (risk) | no portfolio/market → BLOCKED; breach → BLOCKED/HUMAN |
| Approval (human) | no record → DENY (if HUMAN tier); bad sig/rebound → DENY |
| ExchangeSim (env) | no TA / no account → REFUSE; sig fail / state mismatch / limit breach → REFUSE (no mutation) |

---

## 6. Semantic hierarchy (Round 5 refinement)

```
PROPOSED → EVALUATED → AUTHORIZED / ESCALATED / BLOCKED → EXECUTED / REFUSED → VERIFIED
```

- **BLOCKED / REFUSED** = correct, expected protocol behavior. A secure system
  produces *many* of these.
- **CRITICAL** = the system's recorded evidence of authorization cannot be
  independently reproduced (system itself may be compromised). A secure system
  produces *zero unexplained* CRITICAL events.
- **Distinction:** a blocked trade is normal. A verifier discovering
  inconsistency (recompute mismatch) is fundamentally different and is
  `CRITICAL`, failing the whole verification run.

---

## 7. Target financial architecture (Round 2/3)

```
EXTERNAL FEEDS (untrusted)            Feed A ┐
   Feed B ┘→ MarketDataAdapter → cross-validate (when ≥2)
   Replay ──────────────┘ → normalized signed local snapshot
        │ SourcedEvidence (signed Handoff)
LAYER 1: Researcher → Strategist Brain (propose TradeProposal) → Analyst (D16) → QualifiedIntel
         ConsensusGate (advisory, graded, optional)
        │ QualifiedIntel
LAYER 2: Registry → Gateway(request_authority) → RiskLayer.assess →
         required_trade_authorization(AUTO/HUMAN/BLOCKED) →
         verify_approval (HUMAN tier) → build TradeAuthorization (signed) → AuditTrail
        │ signed, state-bound TradeAuthorization
LAYER 3: ExchangeSim.apply(order_id, TA):
           (a) verify TA sig + identity epoch
           (b) re-verify portfolio_pre_hash == live account hash   (I7, critical)
           (c) verify order constraints (qty/price/asset)
           (d) mutate account INSIDE idempotent commit
         → ExecutionReceipt (signed) → ledger
VERIFIER: fleet/fin/verify.py reconstructs inputs, recomputes risk + disposition,
          verifies TA sig/state-binding, verifies ledger chain → PASS / FAIL / CRITICAL
        │ optionally replicate SIGNED artifacts only → GCP (OFF by default)
```

The incident workload remains a sibling: same Layers 1–2, with `SimEnv` as its
Layer 3. Both share identity/registry/policy/gateway/approval/crypto/audit.

---

## 8. Execution paths — deterministic vs AI strategy (Round 6 lock)

```
┌─────────────────────┐
│  Proposal Sources   │
├─────────────────────┤
│ Deterministic       │ ← baseline / protocol proof (known-good source)
│ Gemma               │ ← canonical AI path (local, sovereign)
│ Gemini              │ ← optional demonstration path (demo-only)
└──────────┬──────────┘
           │  SAME proposal interface (schema-validated)
           ▼
   SAME GOVERNANCE PATH (D16 → Capability → Risk → Approval)
           ▼
   SAME TradeAuthorization
           ▼
   SAME ExchangeSim
           ▼
   SAME Verifier
```

> **Deterministic strategy proves the protocol. AI strategy demonstrates the protocol.**

The deterministic no-brain strategy is architecturally important, not merely a
demo convenience: it provides a known-good deterministic proposal source that
proves the governance protocol independently of model quality. The exact same
proposal (or an AI-generated one) flows through identical governance. If Gemma
produces garbage, the system still refuses it correctly; if Gemma produces a
valid proposal, the system still treats it as merely a proposal. Security
properties are identical in both cases (M0).

---

## 9. Financial domain model (Round 2)

| Object | Shape | Origin |
|--------|-------|--------|
| MarketData | `{symbol, ts, bid, ask, last, vol, source_id, snapshot_hash}` | ADAPTER (signed) |
| Account | `{account_id, cash, positions, base_ccy, mandate}` | CORE (new) |
| Position | `{symbol, qty, avg_price, mkt_value, side}` | CORE (new) |
| Portfolio | `{account_id, cash, positions, total_value, unrealized_pnl, daily_pnl, drawdown_pct}` | CORE (new) |
| TradeProposal | `{symbol, side, qty, limit_price?, thesis, confidence, evidence_refs, strategy_id}` | Brain output (schema) — PROPOSAL ONLY |
| RiskAssessment | `{position_pct_after, gross_exposure_pct, cash_ok, asset_allowed, size_ok, price_ok, data_fresh, daily_loss_ok, frequency_ok, risk_score, reason}` | RiskLayer (PURE fn) |
| TradeAuthorization | see §11 | Operator-built (signed) |
| ExecutionReceipt | `{order_id, filled_qty, fill_price, ts, prev_state_hash, new_state_hash, ledger_seq, operator_sig}` | ExchangeSim (signed) |

---

## 10. Risk layer (Rounds 2–6 — 10 dimensions, locked)

**10 risk dimensions, no 11th in v1:**

1. position% (post-trade)   2. gross exposure%   3. cash   4. asset restriction
5. (asset) allowed sides     6. order size (notional)   7. price constraint
8. stale data (freshness)    9. drawdown   10. daily loss   11+. frequency (daily order count)

> NOTE: the canonical 10-item set from Round 3/5 is: position%, exposure, cash,
> asset restriction, order size, price constraint, stale data, drawdown, daily
> loss, frequency. (Asset "allowed sides" is folded into the mandate; the 10
> remain the test-backed dimensions. No dimension beyond these is added in v1.)

`RiskLayer.assess(proposal, portfolio_pre, market, mandate) → RiskAssessment`
is a **pure, deterministic function** with no model calls. `required_trade_authorization`
maps the assessment to `AUTO / HUMAN / BLOCKED`, mirroring
`incident.required_authorization`.

**Disposition rules:**
- BLOCKED on any hard breach: `!asset_allowed | !cash_ok | !price_ok | !data_fresh | daily_loss breach | frequency breach`.
- HUMAN on soft breach (e.g. `position_pct_after` over warn threshold) or weak consensus.
- BLOCKED on severe consensus disagreement (advisory signal can only ESCALATE).
- AUTO only if all within limits and consensus strong/absent.

**Consensus (advisory, escalation-only, Round 4 lock):** `AUTO → HUMAN → BLOCKED`,
never reverse. Two models agreeing cannot turn a policy violation into an
authorized action.

---

## 11. TradeAuthorization specification (Round 3/4 lock)

Built by the Operator after all 4 gates pass; signed by the Operator key. In
HUMAN tier, additionally bound to a human `ApprovalRecord`.

```
TradeAuthorization (canonical, signed fields only):
  agent_id            str
  identity_epoch      int
  strategy_id         str
  account_id          str
  symbol              str
  side                enum          # BUY | SELL (LONG-only v1 → BUY dominant)
  qty                 Decimal
  price_constraint    {type: MARKET|LIMIT, limit: float, band: float}
  proposal_hash       str           # sha256(canonical(TradeProposal))
  portfolio_pre_hash  str           # sha256(canonical(account snapshot AT EVAL))
  market_hash         str           # sha256(canonical(MarketData used))
  risk_assessment_hash str          # sha256(canonical(RiskAssessment))
  policy_id           str           # e.g. "cap:operator:trade_execute"
  disposition         enum          # AUTO | HUMAN | BLOCKED (BLOCKED never reaches here)
  approval_id         str|null      # set iff disposition==HUMAN
  nonce               str           # replay defense
  ts                  int
  expiration          int           # ts + MAX_ORDER_TTL
  order_hash          str           # sha256(canonical(TA minus signature))
  signature           str           # operator_key.sign(canonical(TA minus signature))
```

**Cryptographically bound:** agent + epoch + strategy + account + exact order +
evaluated portfolio state + evaluated market + risk verdict + policy + approval +
nonce + expiry. Any mutation → signature fails → `ExchangeSim` refuses (I6).
State re-check at apply enforces I7. Reuses `canonical_bytes` + Ed25519 — no new crypto.

---

## 12. RiskAssessment specification (Round 3/8 lock)

```
INPUTS (all canonical, all LOGGED for verifier reconstruction):
  proposal:    TradeProposal (or its hash)
  portfolio_pre: Account snapshot at evaluation time  → portfolio_pre_hash
  market:      MarketData used                         → market_hash
  mandate:     {allowed_assets, max_position_pct, max_order_usd,
               max_daily_loss_usd, max_orders_per_day, allowed_sides}

RiskAssessment (canonical, deterministic):
  position_pct_after  float
  gross_exposure_pct  float
  cash_ok             bool
  asset_allowed       bool
  side_allowed        bool
  size_ok             bool
  price_ok            bool
  data_fresh          bool
  daily_loss_ok       bool
  frequency_ok        bool
  risk_score          float   # in [0,1]; derived from breaches (lower=worse)
  reason              str
  risk_assessment_hash str     # sha256(canonical(RiskAssessment fields))
```

**Verifiability (headline, Round 3/4/5 lock):** the verifier receives
`RiskAssessment` + `market_hash` + `portfolio_pre_hash` + `proposal_hash` +
`mandate` from the ledger, imports the pure `RiskLayer.assess`, recomputes, and
asserts `recomputed.risk_assessment_hash == logged` and
`required_trade_authorization(recomputed) == logged disposition`. **VERIFIABLE**,
not asserted.

---

## 13. State-binding / replay model (Round 3/4 lock)

| Mechanism | Purpose | Status |
|-----------|---------|--------|
| `nonce` (unique per order) | replay defense at TA level | SPEC (pattern ENF) |
| `expiration` (ts+TTL) | stale-authorization defense | SPEC |
| `idempotency_key` (TA.order_id) | `Runtime.idempotent` returns prior result on replay | ENF |
| `portfolio_pre_hash` re-checked at `apply` | S1≠S2 defense (critical) | SPEC (inside ExchangeSim) |
| `market_hash` + `data_fresh` | stale-data defense | SPEC |
| Gateway idempotency cache bound to `cert_seq` | revoked/rotated agent can't reuse grant | ENF (A3) |
| ledger `seq` + signed checkpoint | post-hoc tamper detection | ENF |

**The S1/S2 defense:** `RiskLayer.assess` runs against `portfolio_pre` and logs
`portfolio_pre_hash`. `ExchangeSim.apply(TA)` computes `live_hash =
sha256(canonical(current_account))` and **refuses** if `live_hash !=
TA.portfolio_pre_hash`. Guarantees the authorization was valid for the *exact*
state it executes against. The `#1` implementation trap; covered by
`test_state_binding_s1_s2`.

---

## 14. CORE / REFERENCE / ADAPTER / DEMO / FUTURE (Round 2/3 lock)

- **CORE (pre-existing, ENF):** identity, registry, certs, crypto, audit, gateway,
  policy, handoff, D16, approval, runtime, consensus (E2), compliance (E1),
  incident workload.
- **CORE (new, must be real & tested):** `fleet/fin/` = `TradeAuthorization`,
  `RiskLayer.assess` + `required_trade_authorization`, `ExchangeSim`,
  `bind_trade`, `Operator._act_trade` (4-gate fork), `MarketData` model,
  financial brain schemas (`trade_signal` / `trade_proposal`).
- **REFERENCE:** market-data adapter (live free feed OR deterministic replay);
  cross-feed consistency check.
- **ADAPTER:** external feed source(s) (pluggable); GCP verification mirror (off by default).
- **DEMO:** extend existing `demo_app.py` — golden path + adversarial triggers.
- **FUTURE (explicitly deferred):** real-ZK (D24), TPM/enclave (D25), genuine
  multi-model independence hardening, real brokerage (out of scope / hypothetical only).

---

## 15. What must be implemented for "complete" (Round 2/6 lock — TIER A + B)

**TIER A — non-negotiable:**
1. `fleet/fin/` domain module (TA, RiskLayer, ExchangeSim, bind_trade, MarketData).
2. `Operator._act_trade` — 4-gate fork reusing `request_authority`/`verify_approval`/`idempotent`.
3. `"trade_execute"` (+ optional `"trade_execute_large"`) added to operator role.
4. Financial brain schemas + `assert_no_policy_leak`.
5. `MarketDataAdapter`: `verify_tool_envelope` → `sanitize_tool_result` → normalize
   → sign local snapshot; **deterministic replay fixture loader** (offline-authoritative).
6. State binding re-verified **inside** `ExchangeSim.apply` (I7).
7. Full risk logging (`portfolio_pre`, `market`, `mandate`, proposal, `RiskAssessment`,
   hashes, disposition) → I15. Verifiability over minimal ledger size.
8. `fleet/fin/verify.py` — reconstruct → recompute risk → recompute disposition →
   verify TA sig/state → verify ledger → **PASS / FAIL / CRITICAL**.
9. 13 adversarial tests, strict 1:1 (incl. `test_model_worst_proposal`).
10. Demo slice in `demo_app.py`: golden path + adversarial triggers.

**TIER B — strongly recommended (v1 scope):**
11. Live free-feed adapter (optional; only if trivial) + replay authoritative.
12. Cross-feed consistency check when ≥2 feeds available (logs discrepancy).
13. `LIMIT` order support (exercises `price_ok` binding).
14. Graded `ConsensusGate` extension wired to escalation (I12).
15. Daily-loss / frequency / drawdown limits in `mandate`.

**TIER C — explicit OUT (do not build):**
Real brokerage/capital/settlement; shorts/options/futures/crypto/FX/leverage/
multi-account; backtesting engine; alpha research; strategy optimization;
real-ZK (D24); TPM/enclave (D25); large market-data aggregation; production DB;
new UI framework; premature generic consequential-action refactor.

---

## 16. Adversarial test plan — strict 1:1 coverage (Round 5 lock)

Every invariant gets an explicit test (modeled on `test_adversarial_beats_phase5.py`
/ `test_incident_e2e.py`). A representative subset is insufficient.

| Test | Proves |
|------|--------|
| `test_injection_poisoned_feed` | forged/unsigned feed + injection → refused at armor boundary (I16) |
| `test_excess_position` | 10× cap → RiskLayer BLOCKED (I8) |
| `test_unauthorized_asset` | forbidden ticker → RiskLayer BLOCKED (I9) |
| `test_replay_order` | resubmit approved TA → DENIED "replay" (I5) |
| `test_forged_approval` | tampered human sig / rebound → `verify_approval` False (I3/I11) |
| `test_revoked_identity` | revoked operator → Gateway DENY; cache invalidated (I4) |
| `test_tampered_ta` | flip field post-signing → `ExchangeSim` refuses (I6) |
| `test_state_binding_s1_s2` | eval at S1, mutate account, apply → `portfolio_pre_hash` mismatch REFUSE (I7) |
| `test_stale_market` | old `MarketData.ts` → `data_fresh=False` → BLOCKED/HUMAN (I10) |
| `test_consensus_cannot_rescue` | two brains agree on policy-violating trade → still BLOCKED (I12) |
| `test_model_worst_proposal` | Brain deliberately worst (unauth asset + 100× size + stale) → ALL gates refuse independently (M0, headline) |
| `test_verifier_recompute_pass` | golden-path trade → `verify.py` PASS, all steps |
| `test_verifier_detects_tamper` | mutate logged RiskAssessment → `verify.py` CRITICAL (I15/I14) |

---

## 17. Verifier contract — `fleet/fin/verify.py` (Round 4/5 lock)

**Inputs (public-key-only; no authority):** the audit ledger (financial entries);
root public key, Operator/Human public certs; the pure `RiskLayer` +
`required_trade_authorization` source; the mandate logged at evaluation time.

**Per `TradeAuthorization` record:**
1. TA signature verifies under Operator cert; cert `identity_epoch` is a known root epoch.
2. State binding (I7): `sha256(canonical(reconstructed portfolio_pre)) == TA.portfolio_pre_hash`.
3. Risk recomputation (I15): `RiskLayer.assess(...)` → `recomputed.risk_assessment_hash == TA.risk_assessment_hash`.
4. Disposition recomputation: `required_trade_authorization(recomputed, ...) == TA.disposition` (consensus advisory, escalation-only).
5. HUMAN binding (if HUMAN): `verify_approval` passes against ta_hash/action_id/capability.
6. Environment applied: `ExecutionReceipt` exists with `prev_state_hash == TA.portfolio_pre_hash`, chains to next entry.
7. Ledger integrity: `AuditTrail.verify()` over the chain.

**Output:** per-trade `PASS`/`FAIL` with reason code + overall verdict.
**CRITICAL rule (Round 5 lock):** if steps 2–4 recompute differently from the
logged values, this is an integrity/compromise finding — the aggregate result
is **FAIL/CRITICAL**, never overall PASS. A secure system produces zero
unexplained CRITICAL events.

---

## 18. Financial vs incident workload (Round 2/3)

| Aspect | Incident (exists) | Financial (SPEC) | Reuses |
|--------|-------------------|-----------------|--------|
| Layer 1 | Researcher/Analyst/Brain → remediation proposal | Researcher/Strategist/Brain → Trade | same |
| Layer 2 cap | `incident_remediate` | `trade_execute` | Gateway + policy |
| Layer 2 risk | `required_authorization(verif,sev,blast,asset)` | `required_trade_authorization(risk,...)` | same pattern |
| Layer 3 env | `SimEnv.transition(workload,state,action)` | `ExchangeSim.apply(account,order)` | same pure-fn-in-idempotent |
| Binding | `bind_artifact(workload,action,target_state)` | TA binds portfolio_pre_hash+market+risk+approval | same |
| PROTECTED | `identity-svc` isolate/quarantine blocked | asset/cash/limits second-line | same defense |
| Verifiable | audit + E1 attestation | audit + RiskAssessment recompute + E1 | same |

Financial is **structurally identical** to incident at the architecture level.
The substrate is unchanged. This is the proof: "the domain changes, the
authority protocol does not."

---

## 19. Demo narrative (Round 2/3)

Golden path: market evidence → AI (or deterministic) proposal → D16 qualification
→ deterministic risk → capability → authorization → cryptographic binding →
ExchangeSim → receipt → ledger → independent verification. A verifier confirms
the trade was authorized for exactly the state it executed against. The AI
proposed; the protocol authorized; the environment enforced; the math proves it.

Adversarial demo: trigger each of the 13 cases (injection, excess position,
unauthorized asset, replay, forged approval, revoked identity, tampered TA,
state-binding S1≠S2, stale data, consensus-cannot-rescue, model-worst-proposal)
and watch the relevant gate refuse — each a passing test; verifier confirms
refusals recorded and ledger intact.

---

## 20. Residual risks (honest, Round 2/3/5)

1. **Trade correctness not guaranteed (irreducible).** Authorization ≠ wisdom. Documented; demo never implies otherwise.
2. **Correlated model failure (cannot be guaranteed).** Consensus mitigates, doesn't solve; independence is a deployment contract. Documented.
3. **RiskLayer trust.** Trusted local code; mitigated by full logging + verifier recompute (I15). Holds only if full logging ships (locked).
4. **State-binding implementation trap (I7).** Re-verify must be inside `apply`, not just preflight. Covered by `test_state_binding_s1_s2`.
5. **Single-feed truth (I16).** Authentic ≠ true; cross-feed only when ≥2 available. Documented limit.
6. **Human-approval theater.** HUMAN tier must be a genuine gate in the demo.
7. **Verifier completeness.** Recompute claim holds only if `verify.py` actually imports `RiskLayer` + reads all logged inputs. Ship verifier with the slice.
8. **Demo credibility.** Paper + UI must carry the three-layer story; attack narrative is the differentiator.
9. **Scope discipline (Round 6).** Hold at 10 risk dimensions; live feed only if trivial; reuse `demo_app.py`; minimal brain schemas; deterministic baseline strategy to keep demo brain-independent.

---

## 21. Planning-phase exit

Rounds 1–6 are complete and locked. This document (D27) is the consolidation.
**No implementation occurs until explicit instruction: "planning complete,
proceed."** At that point, implementation proceeds mechanically from §15 (TIER A
then TIER B), the Operator fork, adapter, verifier, 13 adversarial tests, and
the demo slice — in that dependency order.
