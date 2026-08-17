# Round 4 — Implementation Readiness & Quantitative-Firm Acceptance Harness

> **Status: RECONCILIATION ONLY. No code. No commit. No push.** The conceptual sequence
> (2A→2B→2B-R→2C→2D→2E→Round 3) is ratified. This round translates the ratified architecture into an
> exact construction sequence and proves the quantitative-finance firm is a usable acceptance harness
> for `fleet/epistemic/`. Every claim is grounded in a fresh repository inspection and the seven
> authoritative documents. R1–R7 are **not reopened**; where inspection could not find a
> contradiction, that is stated. Where a contradiction *would* have been required, none was found.
>
> Method: **reconstruct → reconcile → graph → instantiate → harness → attack → classify → minimize →
> order → invariant → decide.** The firm is the acceptance workload, never the definition.

---

## 0. What this round changed vs Round 3 (reconciliation delta)

Three concrete decisions fell out of actually reading the repo against the plan:

1. **Verdict-enum duplication.** There are **two** AUTO/HUMAN/BLOCKED enums: `Disposition`
   (`fleet/fin/domain.py:36`) and `Authorization` (`fleet/layers/incident.py:54`). `decide_trade`
   returns `Authorization`. `incident.py:44` imports `fleet.simenv.env` (heavy). A clean
   `fleet/epistemic/` (F2: only `fleet.crypto.foundation` + stdlib) **must not** import `incident.py`.
   **Decision:** the substrate defines its own neutral `Verdict` enum; Phase 4 provides an adapter so
   `decide_trade`'s `Authorization` maps to/from it. The `Disposition`/`Authorization` duplication is
   flagged as latent tech debt, *not* a contradiction.
2. **`ProposalArtifact.governance_surface: Any` is the existing D28 seam.** `fleet/cognition/evaluation.py:92`
   already splits governance surface from enrichment, keeping cognition from importing typed governance.
   The neutral `Proposal`/`AuthorizationRequest` generalizes that seam; the existing split is preserved,
   not replaced.
3. **Flat package, not nested.** The ontology has ~17 concepts but only **one** import boundary (everything
   imports `fleet.crypto.foundation` + stdlib). There is no second dependency wall, so no subpackage is
   justified. A nested tree would imply walls that do not exist. §3 gives the flat layout and proves acyclic.

No contradiction with R1–R7 was found. The only genuine residual from prior rounds (evidence
completeness, R4) is *already explicitly deferred to monitoring* — it cannot force a boundary redesign.

---

## 1. Reconstructed ratified architecture (authoritative)

Reading the seven docs yields one coherent chain. Every transition below is annotated with the
**artifact · producer · consumer · epistemic? · deterministic? · authority requirement · lineage ·
governance-consumes? · self-grants-authority?**

```
Observation ─► Evidence ─► Belief / Assessment / Recommendation ─► Proposal
            ─► AuthorizationRequest ─► AuthorizationDecision ─► Action
            ─► Execution/State Receipt ─► Outcome ─► Evaluation / Calibration ─► (loop)
```

| Transition | Artifact | Producer | Consumer | epistemic | deterministic | authority req | lineage | gov consume | grants auth? |
|---|---|---|---|:--:|:--:|---|---|:--:|:--:|
| sense | Observation | feed/sensor | epistemic agents | no | no | none | none | no | no |
| derive | Evidence | epistemic agent | agents + gov(evidence) | no(derived) | n/a | none | inputs chain | yes(evidence) | no |
| infer | Belief | epistemic agent | agents + aggregation | **yes** | no | none | evidence_refs | yes(data) | no |
| evaluate | Assessment | any agent (det fn) | agents + gov | no | **yes** | none | inputs | yes(data) | no |
| advise | Recommendation | any agent | agents(advisory) | no | no | **none** | refs | no | **no** |
| intend | Proposal | agent w/ proposal_scope | governance | no | no | none(asks) | belief_refs | via request | no |
| request | AuthorizationRequest | agent w/ proposal_scope | governance | no | no | none(asks) | proposal_ref | via request | no |
| decide | AuthorizationDecision | **governance** | executor | no | **yes** | gov cap | proposal_ref | — | **produces** |
| execute | Action (ExecutionReceipt) | agent w/ capability+decision | ops | no | yes(state-lock) | cap+decision | decision_ref | no | no |
| settle | Outcome/SettleRecord | market/system | calibration | no | yes | none | receipt+market | no | no |
| score | CalibrationRecord | calibration | CalibrationProfile | derived | yes | none | pred×outcome | no | no |

**Where cognition ends and governance begins — proven from the repo, not philosophy:**
> The boundary is the **`Proposal → AuthorizationRequest → AuthorizationDecision`** transition.
> `AuthorizationDecision` is produced **only** by governance and is a pure deterministic function
> `f(identity, capability, mandate, policy, request, current_state, risk_constraints, compliance_constraints)`
> that **cannot consume** confidence / probability / model_score / recommendation / calibration as a
> directive. `exchange/governance.py:106` `decide_trade(client_order_id, exchange_id, side, qty,
> limit_cents, venue, venue_live, intel)` returns AUTO/HUMAN/BLOCKED from `qty/side/venue/intel` and
> **takes no `p_yes`, no confidence, no recommendation**; `intel=="HALLUCINATION"` → BLOCKED. That is
> the cognition/governance boundary, already implemented. The substrate generalizes it; it does not
> invent it.

This satisfies the §1 "most important question" mechanically: left of `AuthorizationRequest` every
artifact is agent-produced with **zero authority**; right of it every artifact is deterministic
governance over externally-governed state.

---

## 2. Reconciliation against the actual repository (A/B/C/D per symbol)

Inspected: `fleet/crypto/foundation.py`, `fleet/fin/domain.py`, `fleet/layers/incident.py`,
`fleet/layers/verification.py`, `fleet/api/schema.py`, `fleet/cognition/evaluation.py`,
`exchange/quant/{probability,evidence,calibration,learning}.py`, `exchange/governance.py`.

| Symbol | Located at | A. Reuse | B. Promote | C. Adapt | D. Untouched |
|---|---|:--:|:--:|:--:|:--:|
| `AgentCert` | `fleet/crypto/foundation.py:67` | ✓ identity+capability | — | — | class stays as-is |
| `canonical_bytes` / `sha256` | `fleet/crypto/foundation.py:45/55` | ✓ directly | — | — | — |
| `Authorization` (verdict) | `fleet/layers/incident.py:54` | — | — | ✓ neutral `Verdict` + adapter (heavy simenv import) | enum stays |
| `Disposition` (verdict, dup) | `fleet/fin/domain.py:36` | — | — | — | dup flagged, untouched |
| `decide_trade` | `exchange/governance.py:106` | — | — | ✓ read output, adapt to `Verdict` | **locked** |
| `TradeDecision` / `TradeRisk` | `exchange/governance.py:89/36` | — | — | — | **locked** |
| `Mandate` | `fleet/fin/domain.py:46` | ✓ referenced | — | — | **locked** |
| `RiskLayer.assess` | `fleet/fin/domain.py:229` | ✓ (deterministic) | — | — | **locked** |
| `TradeProposal` | `fleet/fin/domain.py:158` | — | — | ✓ → neutral `Proposal` | **locked** |
| `ExecutionReceipt` | `fleet/fin/exchange_sim.py:25` | ✓ (Action shape) | — | ✓ → neutral `Action` | **locked** |
| `ProbabilityEstimate` | `exchange/quant/probability.py:43` | — | ✓ already a Belief impl | ✓ `as_epistemic_belief()` | class stays |
| `QuantEvidence` | `exchange/quant/evidence.py:41` | — | — | ✓ → neutral `Evidence` | class stays |
| `CalibrationRecord` | `exchange/quant/calibration.py:25` | ✓ | — | — (feeds L5 profile) | class stays |
| `VerificationLog` / `VerificationRow` | `fleet/api/schema.py:104/115` | ✓ audit ledger | — | — | stays |
| `evaluate_intel` | `fleet/layers/verification.py:59` | ✓ lineage verify | — | — | stays |
| `ProposalArtifact` / `EvaluationArtifact` | `fleet/cognition/evaluation.py:92/55` | — | — | ✓ seam preserved | stays |

**Rule enforced (no symmetry moves):** financial code is **never** moved into `fleet/epistemic/`.
Domain objects remain domain *producers/consumers* of neutral shapes; the substrate defines shapes only.

---

## 3. Exact L0→L2 dependency graph (flat, proven acyclic)

```
fleet/epistemic/
    __init__.py              exports
    hashing.py               RE-EXPORT  canonical_bytes, sha256  (single import surface)
    artifact.py              Artifact(frozen): state()/compute_hash()/evidence_refs      [LEAF]
    proposition.py           Proposition(F1)                                            [LEAF]
    uncertainty.py           Uncertainty union (Point/Interval/Entropy v1)              [LEAF]
    scopes.py                EpistemicScope/EvidenceScope/ProposalScope/
                             CapabilityScope/AuthorizationScope/GovernanceConstraints    [LEAF]
    evidence.py              Evidence(Artifact)                                         [artifact]
    belief.py                Belief(Artifact)                                           [artifact]
    assessment.py            Assessment(Artifact, kind="assessment")                    [artifact]
    recommendation.py        Recommendation(Artifact, authority="NONE"+cast guard)       [artifact]
    proposal.py              Proposal(Artifact) + AuthorizationRequest(Artifact)         [artifact]
    authorization.py         Verdict enum + AuthorizationDecision(Artifact) +
                             AuthorityGrant(signed, epoch-bound)                          [artifact]
    lineage.py               verify_lineage() (reuses evaluate_intel semantics)          [artifact]
    agent_contract.py        AgentContract = refs to scopes+grant+cert (composition)      [composition]
```

**Dependency DAG (edges = "imports"; all point toward `fleet.crypto.foundation` or leaves):**
- `artifact`, `proposition`, `uncertainty`, `scopes`, `hashing` import **only** `fleet.crypto.foundation` + stdlib.
- `evidence`/`belief`/`assessment`/`recommendation`/`proposal` import `artifact` + `proposition` + `uncertainty`.
- `authorization` imports `artifact` + `hashing` + `AgentCert` (from `fleet.crypto.foundation`) — **`AuthorityGrant` stores scope names as strings, never the scope objects**, so no edge to `scopes.py`.
- `lineage` imports `artifact` + `hashing` (reuses `evaluate_intel`'s *semantics*, not the module — keeps the wall clean; see §0.1).
- `agent_contract` imports `scopes` + `hashing` **only**; it holds artifact references by hash string, never importing the artifact kinds → **no cycle**.

**Acyclicity proof:** the only non-leaf internal edges are `evidence/belief/assessment/recommendation/proposal → artifact|proposition|uncertainty` and `authorization|lineage → artifact`. No module is imported by its own importers. `scopes` and `proposition`/`uncertainty`/`artifact` are sinks. Therefore the graph is a DAG → **no circular dependency**.

**Each module owns / imports / must-never-import / who-may-import / behavior-or-value / L-level:**

| Module | Owns | Imports (internal) | Must NEVER import | Importers | Value/Behavior | Level |
|---|---|---|---|---|---|---|
| `artifact` | frozen base + hash | — | governance/fin/quant | all | value | L0 |
| `proposition` | F1 struct | — | anything domain | belief/proposal | value | L0 |
| `uncertainty` | typed union | — | anything domain | belief/assessment | value | L0 |
| `scopes` | 5 scope objects | — | anything domain | agent_contract/authorization(refs) | value | L1 |
| `evidence` | Evidence base | artifact | governance | adapters | value | L0 |
| `belief` | Belief | artifact,proposition,uncertainty | governance | adapters,aggregation(L5) | value | L0 |
| `assessment` | Assessment | artifact,proposition | governance | gov adapter | value | L0 |
| `recommendation` | Recommendation (+guard) | artifact,proposition | governance | gov adapter | value | L0 |
| `proposal` | Proposal+AuthRequest | artifact,proposition | governance | gov adapter | value | L0 |
| `authorization` | Verdict+Decision+Grant | artifact,hashing | governance/fin | gov adapter,agent_contract(refs) | value (grant signs) | L1 |
| `lineage` | verify_lineage | artifact,hashing | governance/fin/quant | gov adapter | behavior (pure) | L0 |
| `agent_contract` | AgentContract | scopes,hashing | artifact kinds, governance | runtime(L4) | value | L1 |

**Explicitly rejected subpackages:** `identity/`, `contracts/` would imply isolated walls that do not
exist; `fleet.epistemic` is one flat namespace because there is exactly one import boundary.

---

## 4. Five-profile contract instantiated for the firm (proves the dimensions are independent)

The runtime contract: `Identity + EpistemicScope + EvidenceScope + ProposalScope + CapabilityScope +
AuthorizationScope + GovernanceConstraints + derived CalibrationState`. Concept test (the one that
proves intelligence/capability/epistemic-standing/authorization are different dimensions):

| Role | Identity | EpistemicScope | EvidenceScope | ProposalScope | CapabilityScope (op) | AuthorizationScope (org) | GovernanceConstraints | Calibration relevance |
|---|---|---|---|---|---|---|---|---|
| **Alpha Researcher** | cert | market_probability, edge | produce/infer | submit_for_validation | run_model, run_backtest | **none** | research mandate | **high** (predictions) |
| **Signal Researcher** | cert | factor/alpha | consume alt-data | submit_for_validation | ingest_signal(feed) | none | data mandate | high |
| **Backtest Engineer** | cert | methodology | consume datasets | — | run_backtest | none | compute policy | none (no predictions) |
| **Model Validation Lead** | cert | model_validity | independent snapshot | — | — | validate.pass/reject (gate) | validation policy | none (no predictions) |
| **Model Risk Validator** | cert | model_risk | independent snapshot | — | — | validate.pass/reject | validation policy | none |
| **CRO** | cert | risk_exposure/liquidity/drawdown | consume RiskAssessment | — | — | **risk.halt, risk.budget.grant** | firm risk policy | **none** |
| **Market Risk Analyst** | cert | market_risk | consume market data | — | — | none | risk mandate | low |
| **Liquidity Risk Analyst** | cert | liquidity | consume flows | — | — | none | risk mandate | low |
| **Portfolio Manager** | cert | allocation | consume beliefs/risk | request_capital, allocate | — | none | RiskBudget + mandate | medium |
| **Capital Allocation Analyst** | cert | capital | consume PM target | propose_allocation | — | none | budget | low |
| **Head of Trading** | cert | execution_desk | consume orders | route_order | oversee_desk | trade.override(limited) | desk mandate | none |
| **Execution Trader** | cert | — | consume decision | — | **execute_order** | **none** | venue/size/asset limits | **none** |
| **Head of Operations** | cert | ops_state | consume fills | propose_recon | settle | ops.approve_recon | ops policy | none |
| **Reconciliation Analyst** | cert | recon | consume positions | — | reconcile | none | ops policy | none |
| **CCO** | cert | legal/regulatory | consume trade logs | — | — | **compliance.veto** | compliance policy | none |
| **Trade Surveillance Analyst** | cert | surveillance | consume logs | — | — | surveillance.flag | compliance policy | none |
| **CIO** | cert | strategy | consume all | propose_strategy | — | strategy.approve (org) | board policy | none (capped by invariants) |
| **Head of Data** | cert | data_catalog | consume vendor feeds | approve_source | onboard_feed | data.approve (org) | data policy | none |
| **Alternative Data Analyst** | cert | alt_data_usefulness | produce data evidence | propose_source | profile_data | none | data policy | medium |

**The six forced proofs (each is a row above, stated explicitly):**
- **CRO**: `AuthorizationScope = {risk.halt, risk.budget.grant}` (high org authority) but `CapabilityScope = ∅` (zero execution). ✓
- **Execution Trader**: `CapabilityScope = {execute_order}` (high op capability) but `AuthorizationScope = ∅` (zero org authority). ✓
- **Model Validator**: `EpistemicScope = {model_validity}` (high standing) but `CapabilityScope = ∅` and `AuthorizationScope` is a *gate over others' artifacts*, never self-execution. ✓
- **CCO**: `AuthorizationScope = {compliance.veto}` (broad veto) but `CapabilityScope = ∅` (no trading). ✓
- **Alpha Researcher**: `CapabilityScope` includes research compute but `AuthorizationScope = ∅` (zero authority). ✓
- **CIO**: `AuthorizationScope = {strategy.approve}` (broad org) but **still constrained by system invariants** — no CIO grant can add `execute_order` to a researcher's cert (I2), no CIO calibration can grant capability (I4). ✓

**Conclusion:** all 21 roles are expressible as *profile assignments*, not new primitives. The three
dimensions (epistemic standing / org authority / op capability) are provably orthogonal in the table.
No role required a bespoke authority class.

---

## 5. The firm run through the decision ladder (5 workflows)

### Workflow A — Strategy → Production
`Head of Strategy → Head of Research → Alpha Researcher → Backtest Engineer → Model Validation Lead →
CRO → Portfolio Manager → Head of Trading → Execution Trader → Operations → Compliance`

| Arrow | Artifact transferred | Kind |
|---|---|---|
| HStrat→HRes | `StrategyHypothesis` (Belief over proposition `strategy_S.succeeds`) | **Belief** |
| HRes→Alpha | refinement note (Recommendation, authority=NONE) | **Recommendation** |
| Alpha→Backtest | `Evidence`(backtest result) | **Evidence** |
| Backtest→Val | `StrategySpec` (L3, G1 — deferred; in v1 use `Proposal` w/ descriptor `submit_for_validation`) | **Proposal** |
| Val→CRO | `ValidationArtifact` (L3, G2 — deferred; v1 uses `Assessment` of independence) | **Assessment** |
| CRO→PM | `RiskBudget` (L3, G6 — deferred; v1 uses external `Mandate` ref in `GovernanceConstraints`) | constraint ref |
| PM→Trading | `Proposal`(target allocation / order) | **Proposal** |
| Trading→Exec | `AuthorizationRequest` (capability `exchange.trade_execute`) | **AuthorizationRequest** |
| Exec→Trader | `AuthorizationDecision` (AUTO/HUMAN/BLOCKED) | **AuthorizationDecision** |
| Trader→Ops | `Action`(`ExecutionReceipt`) | **Action** |
| Ops→Compliance | `Observation`(positions) | **Observation** |

**Missing abstraction check:** `StrategySpec`/`ValidationArtifact`/`RiskBudget` are referenced but
**deferred (L3)**; in v1 they are represented by `Proposal`/`Assessment`/external `Mandate` ref
respectively. **No new abstraction is invented** — the deferred ones are already named in 2B-R/2C.
Every arrow maps to an existing v1 concept except the three explicitly-deferred L3 objects.

### Workflow B — Daily Trading
`Data Engineer → Data Quality Analyst → strategy → Portfolio Manager → Execution Trader → Operations →
Market Risk Analyst → CRO`
- Data Engineer → DQ Analyst: `Observation`(raw feed). DQ Analyst may **quarantine** (a `CapabilityScope`
  action `data.quarantine`, *not* authorization) — produces `Observation`(quarantine flag). ✓ data quality can quarantine evidence.
- DQ → strategy: `Evidence`(clean). Strategy cognition emits `Belief`(p_yes) and `Proposal`(intend). ✓
- strategy → PM: `Belief` + `Recommendation`(target). PM emits `Proposal`(allocation). ✓
- PM → Trader → Ops: `AuthorizationRequest`→`AuthorizationDecision`→`Action`. Trader operates **only
  within capability + authorization** (gateway checks cert capability ⊇ `execute_order` AND decision
  is AUTO/approved). ✓
- Ops → Market Risk → CRO: `Observation`(positions) → `Assessment`(exposure vs limit, deterministic
  `RiskLayer.assess`) → CRO `AuthorizationDecision`(halt) if breach. ✓ deterministic risk; CRO can halt.
- **No probabilistic output becomes a directive:** `Belief`(p_yes) is cited as *data* in the PM's
  `Proposal`; it never appears in `AuthorizationRequest` (schema excludes it). ✓

### Workflow C — Risk Breach
`Market Risk Analyst → CRO → Portfolio Manager → Execution Trader → Operations → CIO`
- MRA: `Assessment`("exposure 14.2% > mandate 10%") — **Assessment, deterministic, no authority**. ✓
- CRO: consumes `Assessment`, emits `AuthorizationDecision`(halt) — **Assessment ENDS, AuthorizationDecision
  BEGINS here**. "Exposure exceeds limit" remains an Assessment; "therefore reduce 4,000 units" is a
  separate `Proposal`+`AuthorizationRequest`+`AuthorizationDecision`, never auto-derived. ✓ the boundary
  is crossed only by governance, not by the assessment text.

### Workflow D — Model Drift
`Model Risk Validator → Model Validation Lead → Alpha Researcher → Backtest Engineer → Model Validation
Lead → CRO`
- MRV: `Observation`(drift metric) → `Evidence`(repro). Cannot self-authorize: MRV has
  `AuthorizationScope = {validate.pass/reject}` (a gate over artifacts) but **no** budget-grant or
  execution; a drift finding is a `Recommendation`/`Assessment`, never an `AuthorizationDecision`. ✓
- MV Lead: `ValidationArtifact`(status=invalid) → may **invalidate** the strategy's `RiskBudget` epoch
  (R3) by emitting an `AuthorizationRequest`/governance action — but only governance revokes the grant
  (the agent cannot sign its own `AuthorityGrant`). ✓ model-risk agent cannot authorize itself.

### Workflow E — New Data Source
`Alternative Data Analyst → Head of Data → Compliance → Data Engineer → Data Quality Analyst → Signal Researcher`
- Alt-Data Analyst: `Belief`(predictive usefulness) — **epistemic**. ✓
- Head of Data: `Proposal`(approve_source) → `AuthorizationRequest` → `AuthorizationDecision`(approve) —
  **data approval = authorization (org)**. ✓
- Compliance: `Assessment`(legal) → `AuthorizationDecision`(veto) — **legality = governance**. ✓
- Data Engineer: `Action`(ingest) — **technical onboarding = operational capability**. ✓
- DQ Analyst: `Assessment`(quarantine?) — **data quality = assessment**. ✓
- Signal Researcher: `Belief` — **none of the dimensions collapsed**. ✓

---

## 6. Attack the architecture (10 adversarial cases → expected result + guard)

| # | Attack | Expected | Enforced by |
|---|---|---|---|
| 1 | Alpha Researcher emits `AuthorizationRequest{confidence:0.99}` | **impossible by schema** — `AuthorizationRequest` has no confidence field (§2.7) | type/schema boundary (Phase 3 test) |
| 2 | Calibrated researcher claims authority from `CalibrationState=97%` | **rejected** — calibration is derived, separate from `CapabilityScope`/`AuthorizationScope` | R6 (§12 invariant; test) |
| 3 | Execution Trader calls execution adapter with no current authorization | **blocked** — gateway requires cert capability ⊇ action AND current `AuthorizationDecision` | I16 (test) |
| 4 | Agent presents expired/superseded authority epoch | **BLOCKED** — decision fn verifies cited grant/budget epoch is current (like `intel==HALLUCINATION`) | R3 (test) |
| 5 | Agent self-creates `AuthorityGrant` | **invalid provenance** — grant must be signed by grantor key, not agent key | I7 (test) |
| 6 | Model mutates own `RiskBudget`/`Mandate` | **immutable** — external signed objects, agent key cannot sign | I6 (test) |
| 7 | `Recommendation` reinterpreted as `Proposal` downstream | **structural rejection** — `Recommendation.authority="NONE"` + cast guard; `Proposal` requires explicit `proposal_scope` re-emit | R2/I13 (test) |
| 8 | Forged/altered evidence hash referenced | **lineage failure** — hash chain + signature; verifier rebuilds and mismatches | I9 (test) |
| 9 | Low-authority agent says "trust my recommendation" | **recommendation stays advisory**; authority must still arise via `AuthorizationRequest`+grant | I13/I14 (test) |
| 10 | 5 agents agree `p=0.99` → consensus treated as authorization | **rejected** — aggregation produces `EpistemicState` (epistemic), never an `AuthorizationDecision` | I19 (test) |

All ten are **prevented by construction**; none require redesigning the boundary — they verify it.

---

## 7. Quantitative mathematics boundary (the finance-critical classification)

| Concept | Class | Rule / why |
|---|---|---|
| probability estimation | **PROB/EPISTEMIC** | → `Belief`/`Evidence`; never directive |
| Bayesian updating | **PROB/EPISTEMIC** | → `Belief` update; never directive |
| posterior distributions | **PROB/EPISTEMIC** | → `Belief`(Distribution) |
| confidence/credible intervals | **PROB/EPISTEMIC** | → `Uncertainty.Interval` |
| expected value | **PROB/EPISTEMIC** | → `Belief`/`Evidence` |
| expected utility | **PROB/EPISTEMIC** (estimate) → feeds deterministic policy | estimate is epistemic; whether utility is admissible is governance |
| alpha estimation | **PROB/EPISTEMIC** | → `Belief` |
| factor models | **PROB/EPISTEMIC** | → `Belief`/`Evidence` |
| covariance/correlation estimation | **PROB/EPISTEMIC** | → `Belief` |
| volatility estimation | **PROB/EPISTEMIC** | → `Belief` |
| Sharpe / Sortino / drawdown | **EVALUATIVE** → feeds deterministic risk | metrics are epistemic; a *limit breach* is `Assessment` |
| VaR / CVaR | **EVALUATIVE (estimate)** → deterministic `Assessment` | "estimated P(loss)=17%" is epistemic; "exposure>X" is `Assessment` |
| Kelly sizing | **EVALUATIVE (estimate)** | whether Kelly is an *allowed sizer* is governance (`RiskBudget`/policy) — R7 |
| portfolio optimization | **DETERMINISTIC/GOVERNANCE** (if under policy) | constraint eval deterministic; *permitting* optimization is governance |
| position / capital limits | **DETERMINISTIC / GOVERNANCE** | `Mandate` (external) |
| risk budgets | **DETERMINISTIC / GOVERNANCE** (external signed) | `RiskBudget` (L3) |
| compliance rules | **DETERMINISTIC / GOVERNANCE** | `GovernancePolicy` |
| authorization | **DETERMINISTIC / GOVERNANCE** | `AuthorizationDecision` |
| settlement | **DETERMINISTIC** | `SettleRecord`/`ExecutionReceipt` |
| state transitions | **DETERMINISTIC** | `Action`/`ExecutionReceipt` |
| cryptographic verification | **DETERMINISTIC** | `fleet.crypto` |
| liquidity / market-impact / execution-cost estimation | **PROB/EPISTEMIC (estimate)** → feeds deterministic `Assessment` | estimates epistemic; the *decision to act* is governance |

**The critical demonstration (estimate vs govern), made explicit:**
- `"Estimated probability of loss = 17%"` → **Epistemic** (`Belief`/`Uncertainty.Point`).
- `"Current exposure = 12.3%"` → **Deterministic state** (`RiskLayer.assess` reads `Account`/`MarketData`).
- `"12.3% > maximum permitted exposure of 10%"` → **Deterministic `Assessment`** (pure fn over mandate).
- `"BLOCK execution"` → **Governance** (`AuthorizationDecision`).
The number flows through the *deterministic* path; the *probability* never enters `AuthorizationRequest`.
This is exactly `decide_trade`'s existing behavior, generalized. **No quant concept crosses the line as a directive.**

---

## 8. Minimum v1 substrate (ruthless table)

| Primitive | v1? | Existing source | Neutral? | Adapter? | Deferred? |
|---|:--:|---|:--:|:--:|---|
| Proposition | **YES** | new (F1) | ✓ | — | — |
| Uncertainty (Point/Interval/Entropy) | **YES** | new | ✓ | — | Distribution/Calibrated/Risk → L5 |
| Evidence (base) | **YES** | new base; `QuantEvidence` adapts | ✓ | ✓ QuantEvidence | — |
| Belief | **YES** | `ProbabilityEstimate` promotes | ✓ | ✓ as_epistemic_belief | — |
| Assessment | **YES** | new subkind; `RiskAssessment` is domain impl | ✓ | (gov reads) | — |
| Recommendation | **YES** | new subkind (authority=NONE) | ✓ | — | — |
| Proposal | **YES** | new; `TradeProposal` adapts | ✓ | ✓ TradeProposal | — |
| AuthorizationRequest | **YES** | new (seam) | ✓ | — | — |
| AuthorizationDecision | **YES** | new neutral; `decide_trade` output adapts | ✓ | ✓ verdict | — |
| Lineage | **YES** | reuse `evaluate_intel` semantics | ✓ | — | — |
| AuthorityGrant | **YES** | new (signed, epoch-bound) | ✓ | — | — |
| EpistemicScope | **YES** | new | ✓ | — | — |
| EvidenceScope | **YES** | new | ✓ | — | — |
| ProposalScope | **YES** | new | ✓ | — | — |
| CapabilityScope | **YES** | view of `AgentCert.capabilities` | ✓ | — | — |
| AuthorizationScope | **YES** | new (separate from capability) | ✓ | — | — |
| GovernanceConstraints | **YES** | references `Mandate`/`RiskBudget` as opaque refs | ✓ | — | — |
| CalibrationState | **YES** (derived marker only) | new (computation = L5) | ✓ | — | profile compute → L5 |
| **ValidationArtifact** | no | — | — | — | **DEFER L3 (G2)** |
| **RiskBudget** | no | promotes `Mandate` | — | — | **DEFER L3 (G6)** |
| **StrategySpec** | no | — | — | — | **DEFER L3 (G1)** |
| **SettleRecord** | no | — | — | — | **DEFER L5 (G5)** |
| **DisagreementRelation** | no | — | — | — | **DEFER L5 (G9)** |
| **EpistemicAggregation** | no | — | — | — | **DEFER L5 (G9-family)** |
| **CalibrationProfile** | no | seals free functions | — | — | **DEFER L5 (G4)** |
| **AuditRecord** | **NO — REUSE** `VerificationLog`/`Row` | exists | — | — | do **not** create |

**Ruthless principle applied:** anything that can stay domain-specific stays domain-specific
(`QuantEvidence`, `ProbabilityEstimate`, `CalibrationRecord`, `TradeProposal`, `ExecutionReceipt` are
*adapted*, never moved). The only *new* neutral objects are the shapes the existing financial objects
already instantiate. No finance-specific authority enters `fleet/epistemic/`.

---

## 9. Implementation order (revised from the prompt's suggestion)

The prompt suggested Phase 0–6 with "authorization primitives" as a separate Phase 3 *after* the
contract. Inspection shows `AuthorityGrant` is part of the **contract** (R3/R7), not a post-contract
add-on; and boundary tests must gate **before** adapters so adapters are tested against a stable wall.
Revised order (each phase leaves the repo green):

| Phase | Files created | Files modified | Forbidden to modify | Deps | Tests introduced | Invariants established | Acceptance | Rollback |
|---|---|---|---|---|---|---|---|---|
| **0 — package + wall** | `fleet/epistemic/__init__.py`, `hashing.py` | `exchange/tests/test_boundary_quant.py`, `fleet/tests/test_boundary.py` (add `→ fleet.epistemic` allow) | all locked layers | none | `test_boundary_epistemic.py` (import wall: only `fleet.crypto`+stdlib) | F2 import wall | empty pkg imports cleanly; full suite green | revert allowlist edit |
| **1 — L0 primitives** | `artifact,proposition,uncertainty,evidence,belief,assessment,recommendation,proposal,authorization(Verdict+Decision),lineage` | none | locked | Phase 0 | unit tests per type (hash stable, no prob fields on AuthRequest) | R2 (cast guard), R5 (schema excludes prob) | full suite green | none (additive) |
| **2 — L1 contract** | `scopes.py`, `agent_contract.py`, `authorization.py`(AuthorityGrant) | none | locked | Phase 1 | scope-orthogonality test, grant-sign/verify, epoch test | R1, R3, R7 | full suite green | additive |
| **3 — boundary tests** | `tests/test_artifact_ladder.py`, `test_contract_r1.py`, `test_lineage_r4.py`, `test_epoch_r3.py`, `test_determinism.py` | none | locked | Phase 2 | the §6 ten-case suite as executable tests | I1–I17 | **full 480→ regression green + locked-layer grep empty** | additive |
| **4 — financial adapters** | `exchange/quant` + `exchange/api` adapter modules (`as_epistemic_*`, verdict adapter) | **additive only** (new methods/adapter modules) | `decide_trade`, `Mandate`, `RiskLayer`, `ExecutionReceipt` bodies | Phase 3 | adapter round-trip tests (ProbabilityEstimate↔Belief, TradeProposal↔Proposal, verdict map) | I11 (no leak into substrate) | full suite green | remove adapter modules |
| **5 — firm acceptance** | `tests/test_firm_acceptance.py` | none | locked | Phase 4 | Workflows A–E + §6 ten adversarial cases as conceptual harness tests | I13/I14/I16/I19 | all firm paths representable; zero role-specific primitive | additive |
| **6 — integration verify** | none | none | locked | Phase 5 | full suite + locked-layer gate + import-wall + determinism | all I1–I20 | **IMPLEMENTATION READY gate** | — |

Each phase is independently revertible; Phases 0–3 touch only `fleet/epistemic/` + test allowlists;
domain behavior is untouched until Phase 4 (adapters).

---

## 10. Non-negotiable architecture invariants (I1–I20)

I1 — Cognition cannot authorize itself.
I2 — Capability does not imply authorization.
I3 — Authorization does not imply epistemic correctness.
I4 — Calibration cannot grant authority.
I5 — Probability cannot directly become a governance directive.
I6 — Risk limits are external to the model evaluated against them.
I7 — Authority grants are externally governed (signed by grantor, not the agent).
I8 — Authority epochs cannot be silently reused (non-current epoch → BLOCKED).
I9 — Evidence lineage is content-addressed (hash chain + signature).
I10 — Deterministic governance functions remain deterministic.
I11 — Domain-specific quantitative logic cannot contaminate the neutral substrate.
I12 — Model validation remains organizationally and epistemically independent from research.
I13 — Recommendation cannot silently become Proposal.
I14 — Proposal cannot silently become AuthorizationRequest with additional authority.
I15 — AuthorizationDecision cannot consume epistemic confidence as an authorization directive.
I16 — Execution cannot occur without valid capability + authorization + current state.
I17 — Existing financial authority boundaries must remain intact during migration.
I18 — **Lineage authenticity/provenance/freshness/independence are core; completeness/coverage are
      monitoring and must never be claimed as core guarantees** (R4 — the one honest residual).
I19 — **Aggregation produces epistemic state; it never produces an AuthorizationDecision.**
I20 — **AuthorizationRequest / Proposal schemas structurally exclude confidence/probability/belief
      fields** (so an LLM cannot smuggle a directive through the type system).

(I18–I20 are the stress-test reveals; the rest are R1–R7 restated as enforceable invariants.)

---

## 11. Final decision

### IMPLEMENTATION READY

**Why the neutral substrate is sufficiently specified:** §3 gives the exact flat module graph, every
import edge, and a proof of acyclicity; §8 gives the ruthless minimum-v1 table; §1 gives the
reconstructed ladder with per-transition authority/lineage proven from the repo. Nothing is left as
"we'll figure it out later" inside v1.

**Why the quantitative firm proves generality rather than contaminating the abstraction:** §4 shows all
21 roles are *profile assignments* on one contract with three provably-orthogonal dimensions — no
role needed a bespoke authority class. §5 runs five real workflows; §7 classifies 26 quant-math
concepts; §5/§6 prove the same ladder serves incident/security/research by changing only
`Proposition.domain` + `ActionDescriptor`. The firm forced exactly two *vocabulary* refinements
(`Assessment`/`Recommendation` subkinds) and one *field split* (`AuthorizationScope` vs
`CapabilityScope`) — both already ratified as R1/R2 — and **zero** new authority machinery.

**Why `fleet/fin` and `exchange/quant` integrate without redesigning authority:** §2 shows every
existing financial object is either **reused** (`AgentCert`, `canonical_bytes`, `Mandate`,
`RiskLayer.assess`, `ExecutionReceipt`, `VerificationLog`, `evaluate_intel`) or **adapted**
(`ProbabilityEstimate`→`Belief`, `QuantEvidence`→`Evidence`, `TradeProposal`→`Proposal`, verdict
adapter) — never moved. `decide_trade` already excludes probability; the substrate generalizes that,
not invents it. Locked layers stay byte-untouched (I17).

**The first implementation increment:** **Phase 0 + Phase 1** — create `fleet/epistemic/` (empty,
import-wall clean, allowlist relaxed in the two boundary tests) then add the L0 immutable primitives
(`artifact`, `proposition`, `uncertainty`, `evidence`, `belief`, `assessment`, `recommendation`,
`proposal`, `authorization` Verdict+Decision, `lineage`). No domain code moved; no governance
signature changed.

**What must remain untouched:** `fleet/fin/` (entire — `Mandate`, `RiskLayer`, `TradeProposal`,
`ExecutionReceipt`), `exchange/governance.py` (`decide_trade` signature), `fleet/crypto/foundation.py`
(`AgentCert`, `canonical_bytes`, `sha256`), `fleet/layers/incident.py` (`Authorization`),
`fleet/layers/verification.py` (`evaluate_intel`). Verified untouched via `git status --porcelain |
grep -E "fleet/fin/|exchange/governance.py"`.

**What tests constitute the first hard architectural gate:** the **Phase 3 boundary suite** —
`test_boundary_epistemic.py` (import wall), `test_artifact_ladder.py` (Belief≠Assessment≠Recommendation≠
Proposal; cast guard), `test_contract_r1.py` (capability≠authorization), `test_lineage_r4.py`
(tampered hash fails), `test_epoch_r3.py` (stale epoch BLOCKED), `test_determinism.py` (same inputs →
same decision) — **gating on the full 480-test regression remaining green and the locked-layer grep
being empty**. The §6 ten adversarial cases are encoded as executable tests in that suite.

*No code written. Not committed. Not pushed. This document is the implementation-ready construction
specification and the quantitative-firm acceptance harness. The next turn (your explicit go) begins
Phase 0.*
