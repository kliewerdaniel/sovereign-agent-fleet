# Round 2B — Organizational Epistemics: mapping the quant firm onto the EOM

> **Status: DESIGN ONLY. No code. No commit.** This is the concrete stress-test of the
> Round 2A Epistemic Object Model (`epistemic-object-model.md`) using the supplied
> Quantitative Finance Firm organizational design as the use case. It determines whether
> the EOM is *sufficient* to represent a real population of heterogeneous, conflicting-
> incentive agents — and names the primitives it is missing.
>
> Constraints honored: no runtime code, no behavior change, no commit. Conclusions are
> grounded in the actual repo. Ambiguity is surfaced as a question, not silently decided.

**Central invariant (held throughout):**
> COGNITION PROPOSES. EVIDENCE SUPPORTS. GOVERNANCE DECIDES. CRYPTOGRAPHY VERIFIES. THE LEDGER REMEMBERS.

---

## 1. Grounding in the existing repo

The EOM is not invented from scratch. Three existing artifacts already implement its financial
half, which is why the org stress-test largely *validatees* rather than *refutes* the model:

| Existing object | File | What it already is in EOM terms |
|-----------------|------|----------------------------------|
| `QuantEvidence` | `exchange/quant/evidence.py:41` | A signed **Evidence envelope** bound by hash to a proposal; carries *only hashes* of its constituents (`probability_hash`, `market_prob_hash`, `edge_hash`, `ev_hash`, `calibration_hash`); the gates **never read it** (`exchange/governance.py` `decide_trade` takes `qty/side/venue/intel`, no probability). This is M0 realized. |
| `ProbabilityEstimate` | `exchange/quant/probability.py:43` | A frozen, hashable **Belief**-shaped record (`p_yes`, `uncertainty`, `model_id`, `method`) — but with an *unstructured* subject (just `exchange_id`), i.e. **pre-F1**. |
| `CalibrationRecord` | `exchange/quant/calibration.py:25` | An immutable **Prediction × Outcome** record (`predicted_prob`, `outcome`, `model_id`) — exactly the "prediction stays immutable, outcome makes a new record" discipline. |
| `brier_score` / `rolling_brier` / `reliability_bins` | `exchange/quant/calibration.py:56+` | **Calibration statistics** computed over `CalibrationRecord`s — currently free functions, not a sealed object. |
| `RiskLayer.assess` / `decide_trade` | `exchange/governance.py:106` | The **deterministic authority** path. Pure function of risk tier; probabilistic input is excluded by construction. |
| `EvaluationArtifact` (+ `validate_evaluation_payload`) | `fleet/cognition/evaluation.py:54` | The **signals-not-flags** scanner — cognition cannot smuggle `authorization`/`disposition`/`requires_human_review` into enrichment. Seed of the Belief→Proposal boundary. |
| `AgentCert` + capability | `fleet.crypto.foundation` | The existing **authority primitive** — certs carry `role` + `capabilities`; the gateway enforces them. This is where financial "AUTONOMOUS / APPROVE / veto" authority lives. |

**Conclusion of grounding:** the substrate already separates cognition from authority on the
financial path. The org doc does not break the architecture; it *exposes the vocabulary gaps* that
make the separation hard to express for the *full* firm (not just a single order).

---

## 2. EOM ↔ organization mapping (role → epistemic objects)

Role categories discovered (a role may span several): **OBSERVER, RESEARCHER, FORECASTER,
VALIDATOR, AGGREGATOR, AUTHORIZER, EXECUTOR, AUDITOR, MONITOR.** For each role we list what it
observes / which EOM objects it emits / what authority it does **not** have.

| Role | Primary category | Observes | Emits (EOM) | Authority it does NOT have |
|------|------------------|----------|------------|----------------------------|
| **CIO** | AUTHORIZER | risk/perf reports | `AuthorizationDecision` (firm limits), `RiskBudget` | places no trade; builds no model |
| **Head of Strategy** | RECOMMEND | landscape | `Proposal`(strategy roadmap) | cannot launch strategy alone |
| **Head of Research** | AGGREGATOR/RECOMMEND | research output | `Proposal`(backlog) | no validation authority |
| **Alpha Researcher** | FORECASTER/RESEARCHER | datasets, prior research | `Observation`→`Evidence`→`Belief`(edge)→`Proposal`(strategy spec) | **no capital, no execution** |
| **Signal Researcher** | RESEARCHER | raw/alt data | `Evidence`(signal lib) | no strategy authority |
| **Backtest Engineer** | VALIDATOR | strategy spec | `ValidationArtifact(methodology)` | cannot approve a *strategy* (only reject on method) |
| **Head of Data** | AUTHORIZER(infra) | data requests | `AuthorizationDecision`(source onboard) | no trading |
| **Data Engineer** | EXECUTOR(infra) | feeds | `Observation`(clean datasets) | no research authority |
| **Data Quality Analyst** | AUDITOR | ingested data | `Observation`(quarantine flag) | cannot build models |
| **Alternative Data Analyst** | RECOMMEND | vendors | `Proposal`(onboard source) | no direct integration |
| **Model Validation Lead** | VALIDATOR (independent) | strategy spec + own held-out data | `ValidationArtifact`(reject/pass) | **cannot place a trade** despite veto power |
| **CRO** | AUTHORIZER | validated specs, live exposure | `RiskBudget`, `AuthorizationDecision`(halt) | not the best forecaster |
| **Market Risk Analyst** | MONITOR | live positions | `Observation`(breach alert) | no direct execution |
| **Model Risk Validator** | MONITOR | live perf | `Observation`(drift signal) | no pre-launch authority |
| **Liquidity Risk Analyst** | ADVISORY | depth data | `Belief`(liquidity cap) | no binding limit alone |
| **Portfolio Manager** | AGGREGATOR/AUTHORIZER | budgets, conditions | `Proposal`(target positions), `AuthorizationRequest` | cannot exceed CRO budget |
| **Capital Allocation Analyst** | AGGREGATOR | stats | `Belief`(weights) | no execution |
| **Head of Trading** | AUTHORIZER(exec) | positions | `AuthorizationDecision`(venue policy) | no strategy selection |
| **Execution Trader** | EXECUTOR | target positions, mkt | `Action`(`ExecutionReceipt`) | cannot choose strategy |
| **Market Microstructure Analyst** | RESEARCHER | fills/book | `Belief`(exec tuning) | no live trading |
| **Head of Operations** | AUDITOR | fills, statements | `Observation`(recon), `AuthorizationDecision`(recon sign-off) | no P&L authority |
| **Trade Support / Settlement / Recon** | EXECUTOR/AUDITOR | trade data | `Observation`s, `Action`s | no strategy |
| **CCO** | AUTHORIZER(veto) | specs, logs | `AuthorizationDecision`(block) | cannot trade |
| **Trade Surveillance** | MONITOR/AUDITOR | trade logs | `Observation`(anomaly) | no trade |
| **Regulatory Reporting** | EXECUTOR | positions | `Action`(filing) | needs CCO sign-off |
| **Head of Engineering / Platform / ML / DevOps** | EXECUTOR(infra) | requirements | `Action`s (deploy) | no business authority |

**Key insight:** the org's "decision authority" (AUTONOMOUS/RECOMMEND/APPROVE/ADVISORY) maps onto
the EOM **only as a capability encoded in `AgentCert` + a gate**, never as a property the agent
asserts about itself. A `Model Validation Lead`'s veto is an `APPROVE` gate on the strategy-spec
edge; it is *not* a belief about the market. This is exactly the cognition/authority split.

---

## 3. Competing beliefs (objects + relationships first, no weighting formula)

**Concrete proposition** (F1-structured): `Proposition{domain="market_probability",
subject="<ticker>:<event_id>", predicate="P_yes", params={"horizon": <ts>}}`.

Five agents emit `Belief{proposition=P, estimate=Point(p), evidence_refs=[...], model_id=...}`:
A=0.72, B=0.61, Macro=0.48, Micro=0.67, PM=0.64.

Answers to the ten questions:

1. **Same-proposition identity** — `(domain, subject, predicate, params)` match (F1). Without this,
   the five numbers are unrelated floats. The EOM's `Proposition` *is* this identity key.
2. **Disagreement representation** — not a scalar; a set of `Belief` records sharing `proposition`,
   each with its own `estimate` + `evidence_refs`. Disagreement = the spread/divergence of that set.
3. **Independent vs repeated source** — derivable from `evidence_refs`: if all five `Belief`s cite
   the *same* upstream `Evidence` hash, they are not independent. **EOM gap:** there is no explicit
   `IndependenceAttestation` asserting non-shared lineage; today you must *infer* it by intersecting
   `evidence_refs`. (See §9, gap G3.)
4. **Calibration effect on aggregation** — a `Belief` from a producer with a good `CalibrationProfile`
   could carry `estimate = Calibrated(p, score, n)`; the aggregator *reads* that, it does not
   overwrite `p`.
5. **Uncertainty effect** — `estimate` carries `epistemic`/`aleatoric`; an aggregator can down-weight
   high-epistemic-uncertainty beliefs (they should be resolved by more data, not averaged).
6. **Evidence quality** — carried on the referenced `Evidence` (kind, `producer`, freshness); the
   aggregator reads quality via the hash chain, not the agent's self-report.
7. **Role specialization** — `model_id`/cert `role` is *epistemic standing*, NOT authority. The
   Microstructure Analyst may have low weight on a macro prediction regardless of title.
8. **Recency** — `ts` on `Belief` and on `Proposition.params.horizon`; stale beliefs expire.
9. **Model correlation** — needs the `IndependenceAttestation` / shared-`evidence_refs` signal (G3).
10. **Disagreement as informative** — yes: a `EpistemicAggregation` records `disagreement_stats`
    (variance, max-min spread, number of distinct `evidence_refs` clusters); high disagreement can
    *raise* an `ASSERTED` trust tier or trigger a `ValidationArtifact`, it is never auto-resolved.

---

## 4. Calibration model

Three immutable stages (no rewriting predictions):
```
Prediction (frozen Belief about a future event)
    ↓ Outcome (immutable Observation)
    ↓ CalibrationRecord (Prediction × Outcome, per realized event)   [EXISTS: calibration.py:25]
    ↓ CalibrationProfile (rolling stats per producer+template)
```

**Metric classification** (A=immutable observation, B=derived evidence, C=calibration statistic,
D=governance input):

| Metric | Class | Note |
|--------|-------|------|
| `predicted_prob`, `outcome`, `model_id`, `ts` | **A** | the raw `CalibrationRecord` |
| Brier / log-loss / reliability-bin empirical freq | **B** | derived from A, hash-chained |
| rolling Brier, reliability curve, discrimination, resolution, calibration error | **C** | the `CalibrationProfile` (currently free functions → promote to sealed object, G4) |
| sample count, recency, regime tag, horizon, proposition class | **C** (metadata dims) | dimensions the profile is keyed on |
| a "this agent is now trusted with more capital" rule | **D** | **MUST NOT** be derived from C. Calibration affects *epistemic aggregation weight* only. |

**Hard rule (from the prompt):** calibration is **epistemic standing**, never an authority
credential. An agent with Brier≈0 gets higher *belief weight* in aggregation; it gets **no**
additional `capability` in its `AgentCert`. Authority is governed separately (§6).

**Gap G4:** `CalibrationProfile` should become a sealed, hash-addressed object (per
`(producer, proposition_template, regime, horizon)`) so the verifier can recompute it from
`CalibrationRecord`s — currently it is only computed in-memory.

---

## 5. Strategy lifecycle as an epistemic pipeline

```
StrategyHypothesis   (Belief-ish: a proposed Edge over a Proposition)
   → EvidenceSet     (backtest results, OOS data)            [Evidence]
   → StrategySpec    (hypothesis + signal + backtest + limits)  [NEW first-class: G1]
   → ValidationArtifact  (independent replication, held-out data, method ver)  [NEW: G2]
   → RiskAssessment  (VaR/CVaR/drawdown — PROBABILISTIC + DETERMINISTIC)  [Evidence → Risk]
   → AuthorizationRequest (PM requests capital under CRO budget)  [EOM type]
   → AuthorizationDecision (CRO/Governance: AUTO/HUMAN/BLOCKED)  [governance]
   → ExecutionReceipt (live fill, state-locked)  [Action — EXISTS]
   → SettleRecord     (realized P&L)              [Outcome — NEW: G5]
   → CalibrationRecord / ModelRisk (drift signal) [Evaluation]
```

**New first-class categories required (gaps):**
- **G1 `StrategySpec`** — the handoff artifact between Research and Validation. Carries hypothesis,
  signal def, backtest result hashes, *and the data snapshot id* it was trained on (so Validation
  can prove independence).
- **G2 `ValidationArtifact`** — the independent gate. Fields: `claimant`, `validator`,
  `independent_evidence_refs`, `data_snapshot_id` (deliberately *different* from the claimant's),
  `methodology_version`, `model_version`, `replication_result` (pass/conditional/reject),
  `disagreements`, `unresolved_uncertainty`, `validation_status`. Critically **not** a Belief
  about the market — it is an Evidence object about *a claim's reproducibility*.
- **G5 `SettleRecord`** — the realized outcome feeding `CalibrationRecord` and `ModelRisk`.

Everything else maps onto existing EOM types. No forcing.

---

## 6. Risk as a boundary case (the critical classification)

Risk estimates must never become implicit authority. Classification:

| Quantity | Class | Lives in | Consumed by |
|----------|-------|----------|-------------|
| VaR / CVaR / expected-loss distribution | **PROBABILISTIC** | cognition/quant (Belief/Evidence) | `RiskAssessment` math only |
| drawdown, concentration, correlation, factor exposure (measured) | **PROBABILISTIC/observed** | monitoring Observations | `RiskAssessment` |
| Kelly sizing, capital allocation suggestion | **PROPOSAL** | PM `Proposal` | governance input |
| position ≤ X, liquidity cap | **DETERMINISTIC** (computed) | `RiskLayer` (fin) | `AuthorizationDecision` |
| "this strategy is FORBIDDEN from exceeding X" | **GOVERNANCE** | `AgentCert` capability + `RiskBudget` (external authority record) | `decide_trade` |

**The wall:** the model that *computes* VaR (probabilistic) cannot be the object that *sets* the
position limit (deterministic/governance). The limit is an external `RiskBudget`/`AgentCert`
capability, exactly as today's `decide_trade` excludes probability. **Gap G6:** there is no sealed
`RiskBudget`/`AuthorityGrant` object external to the risk model — `decide_trade` currently derives
tier from `qty` alone. For the full firm, a `RiskBudget` (signed by CRO, bound to a strategy spec
hash) is the clean primitive.

---

## 7. The firm as an agent graph (typed edges)

The org is not `Agent→Agent`; it is a graph with **edge types** carrying different EOM objects:

```
DATA_FLOW          Data Engineer ──► Alpha Researcher
EVIDENCE_FLOW      Alpha Researcher ──► Backtest Engineer
BELIEF_FLOW        Alpha Researcher ──► Model Validation      (claim as Belief/StrategySpec)
VALIDATION_EVIDENCE Model Validation ──► Risk                  (ValidationArtifact)
RISK_ASSESSMENT    Risk ──► Portfolio                         (RiskAssessment)
PROPOSAL_FLOW      Portfolio ──► Governance                    (AuthorizationRequest)
AUTHORIZATION_FLOW Governance ──► Trading                     (AuthorizationDecision)
EXECUTION_FLOW     Trading ──► Operations                      (ExecutionReceipt)
OBSERVATION_FLOW   Operations ──► Risk                         (positions)
DRIFT_SIGNAL       Risk ──► Model Validation                   (re-validation loop)
OVERSIGHT_FLOW     Compliance ──► (everyone)                   (standing read, veto)
AUDIT_FLOW         Operations/Compliance ──► Ledger           (recon sign-off)
CALIBRATION_FLOW   Outcomes ──► Cognition                      (CalibrationProfile)
ESCALATION_FLOW    Market Risk ──► CRO ──► CIO                 (halt authority)
```

**Does fleet need to distinguish these edge types?** Conceptually **yes** — today the boundary is
enforced by *module* import walls, but the *orchestration layer* (`fleet/layers/runtime.py`,
`exchange/api.py`) passes messages without labeling them. Promoting edge types to first-class
routing labels lets the runtime enforce "a `BELIEF_FLOW` may never carry an `AUTHORIZATION_FLOW`
payload" at the message layer, not just the module layer. **Gap G7:** typed message/edge labels in
the orchestration surface.

---

## 8. Role Card evolution

The supplied Role Card (Role ID, Department, Mandate, Decision Authority, Inputs, Outputs,
Tools, Escalation, KPIs, Upstream/Downstream) is **not enough** for the sovereign runtime. It
needs to be split into *runtime primitives* vs *metadata*:

**Genuinely architectural primitives (must be in the runtime/schema):**
- `epistemic_scope` — which `(domain, predicate)` this role may emit `Belief`s about.
- `authority_scope` — which `capability` strings its `AgentCert` carries (the only real authority).
- `proposition_domains` — the `Proposition.domain` set it is allowed to touch (specialization).
- `allowed_action_types` — which `ActionDescriptor` kinds it may request (e.g. Execution Trader:
  `execute_order`; Researcher: none).
- `evidence_requirements` / `lineage_requirements` — for financial roles, mandatory full lineage
  (F3); for others, best-effort.
- `independence_constraints` — e.g. Model Validation **must not** share `data_snapshot_id` or
  `methodology_version` with the claimant (enforced by `ValidationArtifact` field check).
- `forbidden_capabilities` — explicit negative list (a Researcher's cert simply omits
  `exchange.trade_execute`).

**Metadata that must stay OUTSIDE the runtime (org/HR, not architecture):**
- Mandate prose, KPIs, escalation path *as text*, upstream/downstream as org chart. (Escalation
  *as a capability* — e.g. CRO `halt` — is runtime; the prose description is not.)

So: add `epistemic_scope`, `authority_scope`, `proposition_domains`, `allowed_action_types`,
`evidence_requirements`, `lineage_requirements`, `independence_constraints`, `forbidden_capabilities`
to the *runtime* Role Card. Drop KPI/mandate/escalation-prose to a side document.

---

## 9. Missing primitives (the key deliverable)

1. **EOM concepts surviving unchanged:** Observation, Evidence, Belief, Proposal,
   AuthorizationRequest, AuthorizationDecision, Action, Outcome, CalibrationRecord, the
   hash-linked lineage, the epistemic/aleatoric split, the neutral `fleet/epistemic/` home.
2. **Existing repo concepts to promote into the EOM:** `QuantEvidence`→Evidence envelope;
   `ProbabilityEstimate`→Belief (add F1 `Proposition`); `CalibrationRecord`→Outcome×Prediction;
   `brier_score`/`rolling_brier`→`CalibrationProfile` (seal it); `AgentCert` capability→`authority_scope`.
3. **Organizational concepts exposing gaps:**
   - same-proposition identity for *competing* beliefs (F1, already in 2A but untested until now)
   - independent validation with held-out data + separate methodology
   - strategy lifecycle as a typed pipeline
   - risk *budget/limit* as an external authority record
   - typed message/edge labels in orchestration
4. **New primitives necessary:**
   - **G1 `StrategySpec`** (Research→Validation handoff, carries data-snapshot id)
   - **G2 `ValidationArtifact`** (independent replication record; NOT a market Belief)
   - **G3 `IndependenceAttestation`** (asserts non-shared `evidence_refs` / separate snapshot — or
     infer it from intersecting `evidence_refs` and leave explicit attestation optional)
   - **G4 `CalibrationProfile`** (sealed, per producer+template+regime+horizon)
   - **G5 `SettleRecord`** (realized outcome feeding calibration + model-risk)
   - **G6 `RiskBudget` / `AuthorityGrant`** (signed limit external to the risk model)
   - **G7 typed message/edge labels** in the orchestration surface
5. **Concepts that should remain OUTSIDE the EOM:** KPI definitions, mandate prose, HR
   escalation text, vendor cost, compensation. These are org metadata, not epistemic objects.
6. **Belong to governance, not cognition:** `RiskBudget`, position/drawdown *limits* (the
   deterministic/governance row of §6), `AuthorizationDecision`, veto power, halt authority,
   `AgentCert` capability grants.
7. **Belong to calibration/evaluation:** `CalibrationProfile`, reliability/resolution/disagreement
   stats, `ModelRisk` drift signal. Never authority.
8. **Belong to execution/operations:** `ExecutionReceipt`, `SettleRecord`, recon sign-off, the
   actual state transition + settlement (already in `exchange/` books/settlement).

---

## 10. Architecture implications

- The org stress-test **does not refute** the EOM; it confirms it and adds ~7 first-class objects
  (G1–G7), all *additive* — none require changing the closed loop or M0.
- **Generalizability holds.** The same objects serve incident response (Proposition domain =
  `incident_compromised`), security ops (domain = `host_breached`), research (domain =
  `hypothesis_true`). Only `Proposition.domain/predicate` and `ActionDescriptor` change. The
  financial firm is the *best experimental environment* because outcomes are measurable — exactly
  as the Round 2A doc argued.
- The biggest architectural *lift* is **G2 `ValidationArtifact` + G3 independence**: these are what
  make "research proposes, independent validation gate decides reproducibility" a first-class,
  verifiable relation — the single most important org principle (Model Validation ≠ Research).
- The **cognition/authority split is already enforced** by import walls + `decide_trade` excluding
  probability; the org doc's value is making the *vocabulary* for expressing it across a full firm
  explicit (Role Card runtime fields, typed edges).

---

## 11. Round 2B ratification questions (derived from the gaps above)

These are where your answer *materially* changes the architecture. I have not decided them.

**A. Competing beliefs & independence**
1. Is same-proposition identity enough to detect non-independence, or do we need an explicit
   `IndependenceAttestation` (G3)? (i.e. infer shared-source from intersecting `evidence_refs`, vs
   require a signed claim of independence.)
2. Should `EpistemicAggregation` be (a) a new first-class artifact that *produces* a child `Belief`,
   or (b) a `Belief` whose `evidence_refs` point at the constituent beliefs? (This decides whether
   aggregation is "evidence about beliefs" or "a belief about a proposition.")

**B. Validation & independence**
3. Must `ValidationArtifact` carry a *provably different* `data_snapshot_id` + `methodology_version`
   from the claimant (hard independence), or is self-attestation + audit sufficient?
4. Should `ValidationArtifact.validation_status` be allowed to feed *into* `RiskAssessment` as
   evidence (it should), but explicitly **never** into `AuthorizationDecision` directly? (Confirm
   the "validation ≠ governance" wall.)

**C. Risk & authority**
5. Is `RiskBudget` (G6) a signed object external to the risk model (recommended), or is today's
   `qty`-derived tier from `decide_trade` sufficient for the firm scale?
6. Confirm: calibration/risk outputs are **proposal/evidence only**; the limit that binds is always
   a `governance` object. (No silent upgrade of a good Brier score to a capability.)

**D. Calibration**
7. Should `CalibrationProfile` (G4) be keyed per `(producer, proposition_template, regime, horizon)`
   — i.e. does regime/horizon slicing matter enough to be first-class, or is `(producer, template)`
   enough for v1?

**E. Role Card / runtime**
8. Ratify the runtime Role Card fields (§8): `epistemic_scope, authority_scope,
   proposition_domains, allowed_action_types, evidence_requirements, lineage_requirements,
   independence_constraints, forbidden_capabilities` — and confirm KPI/mandate/escalation-prose
   stay outside the runtime.

**F. Graph / orchestration**
9. Should the orchestration surface label message/edge types (G7: `BELIEF_FLOW` vs
   `AUTHORIZATION_FLOW` etc.) as a runtime enforcement layer on top of the module import walls, or
   is the module wall sufficient for the competition scope?

**G. Generalization**
10. Should `StrategySpec`/`SettleRecord` (G1/G5) be domain-general (`ArtifactSpec`/`OutcomeRecord`)
    from the start, or finance-specific first and generalized in 2C?

---

*No code written. Not committed. Round 2C (adaptation: regime/Concept drift/online learning/model
replacement/learned-vs-formal/D28 runtime integration/cross-domain) follows only after these gaps
are ratified.*
