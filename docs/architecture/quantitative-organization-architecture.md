# Round 2C — Quantitative Organization as Epistemic Stress Test

> **Status: DESIGN ONLY. No code. No commit. No schema migration.** This round treats the
> supplied Quantitative Finance Firm (10 departments, 30+ roles) as the **concrete operating
> environment** against which the emerging epistemic architecture is stress-tested. The EOM
> (`epistemic-object-model.md`) and the Epistemic Contract (`epistemic-contract.md`) remain the
> *abstraction*; the firm is the *environment*. Goal: discover what the firm **forces us to change**
> in the architecture **before** `fleet/epistemic/` is implemented — not re-map roles.
>
> Constraints honored: no runtime code, no behavior change, no commit. Every conclusion tagged
> **IMPLEMENTED / DESIGNED / SUPPORTED / PROPOSED / OPEN QUESTION**. Unresolved questions are left
> open, not silently decided.

---

## 1. Executive architectural conclusion

**The EOM + 5-scope Epistemic Contract survive the firm — with two principled gaps the earlier
rounds under-named.** The architecture is *sufficient* to represent all 10 departments as a typed
epistemic/control graph. But the firm exposes that the 5-scope contract's `authority_scope` **bundles
two independent dimensions** — *organizational authority* (veto / override / govern — cross-cutting
oversight) vs *operational capability* (perform a specific action) — and that the vocabulary
**under-names** two recurring artifact kinds the firm produces constantly: **Assessment**
(deterministic state-vs-policy evaluation) and **Recommendation** (advisory, carries no authority).

Neither change requires altering the closed loop, M0, or any import wall. Both are *vocabulary*
refinements, not new machinery. The firm does **not** force a trading-specific framework; it
confirms the architecture is domain-general.

---

## 2. Organizational epistemic graph (reasoned, not tabulated-and-forgotten)

Rather than a flat role→object table, the firm is a **typed graph**: agents are nodes holding an
Epistemic Contract; edges carry specific artifact types (§9). What the firm forces is that **every
role must be decomposable into the same six contract sub-objects** from 2B-R §5:

`AgentIdentity · EpistemicProfile · CapabilityProfile · GovernancePolicy · RoleDefinition · CalibrationProfile`

For representative roles, the *forced* distinctions (the ones a naive mapping would blur):

- **Model Validation Lead** — EpistemicProfile = `{model_validity, statistical_validity,
  methodological_validity}`; CapabilityProfile = **organizational authority** = `validate.reject` /
  `validate.pass` (a gate), but **no operational capability** and **no authority over the research
  artifacts** it reviews (it may not modify `StrategySpec`). Who may challenge its output? The
  Head of Research (escalation to CIO). It *consumes* `StrategySpec` + independent `Evidence`;
  *produces* `ValidationArtifact`.
- **CRO** — CapabilityProfile = **organizational authority** = `risk.halt` (AUTONOMOUS emergency
  halt) + `risk.budget.grant`; EpistemicProfile = narrow `{risk_exposure, liquidity, drawdown,
  stress}`. The CRO may **not** manufacture the quantitative evidence supporting a halt — it *consumes*
  `RiskAssessment` produced by the deterministic `RiskLayer`, it does not author it.
- **Data Quality Analyst** — CapabilityProfile = `data.quarantine` (organizational authority over a
  dataset) but **no** `exchange.trade_execute`. Consumes `Observation`(ingested data); produces
  `Observation`(quarantine flag) → blocks downstream `Evidence` on the financial path (F3).
- **Execution Trader** — CapabilityProfile = **operational capability** = `execute_order` (within
  pre-approved algo + size limits); **no organizational authority** (cannot halt, cannot allocate).
  Consumes `AuthorizationDecision`; produces `ExecutionReceipt`.
- **CCO** — CapabilityProfile = **organizational authority** = `compliance.veto` (can block any
  strategy/source for legal reasons regardless of quantitative merit); EpistemicProfile = legal/
  regulatory domain; **no trading capability**. Consumes `StrategySpec` + `Evidence`(trade logs);
  produces `AuthorizationDecision`(block) / `Action`(filing).

**Forced finding #1:** the capability that lets a role *override another* (Validation reject, CRO
halt, CCO veto, DQ quarantine) is a different thing from the capability that lets a role *perform an
action* (Trader execute, Ops settle, Eng deploy). The firm makes them co-exist in the *same* role
sometimes (CRO has both halt + budget-grant) and split in others (Trader has execute but no
override). The 5-scope `authority_scope` cannot express this split → **§7**.

---

## 3. Agent boundary model — three dimensions, not two

The firm forces a **three-dimensional** split (prompt §2):

| Dimension | What it is | Where it lives in the contract |
|-----------|-----------|-------------------------------|
| **Epistemic Standing** | calibration, evidence quality, domain specialization, methodological validity | **DERIVED** — `CalibrationProfile` (2B-R §5, class E). *Never a contract field.* |
| **Organizational Authority** | veto, halt, approve, override, budget-grant, govern | **PROPOSED** split → `AuthorizationProfile` (cross-cutting oversight capabilities) |
| **Operational Capability** | perform a specific action (execute, settle, deploy, quarantine) | **PROPOSED** split → `CapabilityProfile` (action execution) |

**Test of the 5-scope contract:** it currently has `epistemic_scope` (covers Standing-ish) and
`authority_scope` (bundles *both* Organizational Authority and Operational Capability). The firm
proves those are **independent** — a Compliance Officer has maximal Organizational Authority (veto)
and zero Operational Capability; an Execution Trader has maximal Operational Capability and zero
Organizational Authority. So the *smallest principled extension* is:

> **Split `authority_scope` into `authorization_profile` (organizational authority: veto / halt /
> approve / override / budget-grant) and `capability_profile` (operational: action_descriptor
> execution).** Epistemic Standing remains derived, never stored on the agent.

This does **not** add arbitrary fields — it splits one conflated field into the two dimensions the
firm shows are genuinely orthogonal. (Ratification **Q1**.)

---

## 4. Full artifact lifecycle (per-transition discipline)

The firm's core lifecycle, each transition answered. The key test: does the EOM represent this
*without collapsing distinct concepts into generic "messages"?* — Yes, because each transition
crosses a **different typed object** with different producers/modifiers/rejecters:

| # | Transition | Object crossing | Producer | May modify | May reject | Authority required | Deterministic check |
|---|-----------|----------------|----------|-----------|-----------|--------------------|---------------------|
| 1 | Idea→Hypothesis | `StrategyHypothesis` (Belief-ish) | Alpha Researcher | producer | Head of Research | none (RECOMMEND) | — |
| 2 | Hypothesis→Evidence | `Evidence` (backtest/signal) | Researcher/Backtest Eng | producer | Backtest Eng (method) | Backtest gate | method reproducibility |
| 3 | Signal→StrategySpec | `StrategySpec` (G1) | Alpha Researcher | producer (until validated) | Model Validation | none | spec completeness |
| 4 | Spec→Validation | `ValidationArtifact` (G2) | Model Validation | validator | CRO (on dispute) | validation gate | independence check (§7) |
| 5 | Validation→Risk Assess | `RiskAssessment` | RiskLayer (deterministic) | **none** (pure fn) | CRO | none | pure fn over Mandate |
| 6 | Risk→Risk Budget | `RiskBudget` (G6, signed) | CRO (governance) | **CRO only** | CIO | CRO authority | signature + epoch bind |
| 7 | Budget→Allocation | `Proposal`(target) | Portfolio Mgr | producer | CRO (budget) | CRO budget | within budget |
| 8 | Allocation→Exec Proposal | `Proposal`(order) | Portfolio Mgr | producer | Governance | none | action_descriptor whitelist |
| 9 | Proposal→Auth | `AuthorizationRequest`→`Decision` | Governance | **none** (governed) | Governance | Governance cap | `decide_trade` (no prob) |
| 10 | Auth→Trade | `Action`(`ExecutionReceipt`) | Execution Trader | executor | none | `execute_order` cap | state-lock |
| 11 | Trade→Ops | `Observation`(positions) | Operations | Ops (recon) | Head of Ops | recon sign-off | reconciliation |
| 12 | Ops→Outcome | `SettleRecord`/`Outcome` (G5) | Market/Settle | **none** (observed) | none | none | settlement math |
| 13 | Outcome→Eval | `CalibrationRecord` | Calibration | **none** | none | none | immutable |
| 14 | Eval→Calib | `CalibrationProfile` (G4) | derived | **none** | none | none | rolling stats |
| 15 | →Re-validation | `Observation`(drift) | Model Risk Val | producer | Model Validation | re-validation trigger | drift threshold |

The "who may modify" column shows the architecture already enforces **immutability at the right
places**: `RiskAssessment`, `RiskBudget` (except by its grantor), `CalibrationRecord`, `Outcome`
are not modifiable by their consumers. This is M0 expressed per-transition. **No generic "message"
type is needed** — the typed object chain is sufficient.

---

## 5. Organizational claims model — the under-named progression

The firm proves the prompt's intuition: these are **distinct objects**, and the EOM must name them:

```
Observation        (raw: "quote = 50.1")
Evidence           (derived: "signal S fires")
Belief             (probabilistic future: "P(X rises >5%) = 0.71")
Assessment         ★ (deterministic state-vs-policy: "exposure EXCEEDS concentration threshold")
Recommendation     ★ (advisory: "reduce X by 20%")
Proposal           (authorization request: "request capital Z for strategy S")
Decision           (AuthorizationDecision: AUTO/HUMAN/BLOCKED)
```

The two ★ are what the earlier rounds **under-named**:

- **Assessment** is *not* a Belief. The Market Risk Analyst's "exposure exceeds threshold" is a
  **deterministic evaluation** of observed state against a policy — it carries no probability, no
  future orientation. It is a `RiskAssessment`-shaped artifact (the firm produces these constantly:
  risk monitoring, surveillance, data-quality, drift). The EOM can represent it as a subkind of
  `Evidence`/`Belief` with `kind=assessment`, but the *vocabulary should name it*.
- **Recommendation** is *not* a Proposal. "Reduce X by 20%" is **advisory** — it carries **no
  authorization request**. It is a `Proposal` subkind with `authority=NONE`. A Proposal, by contrast,
  is an `AuthorizationRequest`. The firm constantly emits Recommendations that become Proposals only
  after a human/PM decision.

**Conclusion:** no new *objects*; **name two subkinds** (`Assessment`, `Recommendation`) so the
firm's daily artifacts aren't forced into Belief/Proposal. (Ratification **Q2** — subkind vs
first-class.)

---

## 6. Competing-belief model (firm examples)

**Example A — Research disagreement.** A/B/C on `P(X rises >5% in 10d)` = 0.71/0.54/0.32,
overlapping evidence. Model: three `Belief`s sharing one F1 `Proposition`; `evidence_refs`
intersection computed → overlap metric; `DisagreementRelation` (G9) records spread + overlap + per-
agent `CalibrationProfile`. Aggregation reads calibration weights + overlap (shared evidence = not
independent). **No voting.** The aggregate is an `EpistemicAggregation` that *preserves* the
constituent beliefs (2B §4). The firm forces: aggregation must produce an **epistemic state**, not a
number — so downstream `Proposal` cites the aggregate *and* its disagreement stats.

**Example B — Research vs Validation.** Research "passes" vs Validation "fails (survivorship)".
Neither overwrites the other. The `ValidationArtifact` (G2) holds **both claims**, each with its own
`Evidence`/`method`/`data_snapshot`, the `IndependenceContract` (§7), the `DisagreementRelation`, and
a `resolution` field — but the *resolution is a Governance Decision*, not a validation output. New
artifact required: **G2 `ValidationArtifact`** (already in 2B-R). No further new type.

**Example C — Quant vs Risk.** "Expected return high" (Belief over `expected_return`) vs "max
exposure low" (Assessment over `permitted_exposure`). **Different propositions.** The EOM's
structured `Proposition{domain,predicate}` keeps them distinct automatically — they never collide
because their `predicate` differs. The firm confirms the F1 key is doing real work: the architecture
*already* prevents conflating these.

---

## 7. Risk as a first-class boundary (firm-forced split)

```
Risk Estimation   (probabilistic Belief: "E[vol] = X")         → cognition/quant
Risk Assessment   (deterministic: RiskLayer.assess)            → IMPLEMENTED (fleet/fin)
Risk Policy       (limit: "exposure ≤ Y")                      → GovernancePolicy (C)
Risk Budget       (signed grant: "strategy S granted Z")       → G6 (PROPOSED)
Risk Authority    (CRO may halt / grant)                       → authorization_profile
Risk Action       (Execution reduces position)                → Action/ExecutionReceipt
```

**Invariant (realized, not aspirational):** *a model can estimate risk but cannot define its own
permissible risk.* Enforced because `RiskBudget`/`RiskPolicy`/`CapabilityProfile` are **all external
signed objects** the producing agent cannot write. The agent cannot modify: its own `RiskBudget`, its
own `capability_profile`, its own `authorization_profile`, its own `GovernancePolicy`, its own
`ValidationArtifact` status. **This is exactly the three-dimension split of §3** — the same
extension that fixes the authority conflation also fixes "model can't redefine its own risk."

---

## 8. Independent validation (what actually matters)

Verifiable independence needs only the **checkable** subset — the rest are implementation details
that *affect* these, not independent requirements:

| Dimension | Matters because | Checkable as |
|-----------|-----------------|--------------|
| data snapshot | prevents shared-data correlation | `data_snapshot_id` hash |
| evidence lineage | prevents shared-source correlation | `evidence_refs` intersection |
| methodology | prevents same-method bias | `methodology_version` |
| withheld data | prevents in-sample overfit | held-out slice id |
| evaluation procedure | prevents metric gaming | `eval_procedure_id` |

**Does NOT independently matter:** codebase identity, model architecture, prompt text, random seed,
context window — *except* insofar as they change the five above. So `IndependenceContract` is
**minimal**: it records `{claimant_snapshot, validator_snapshot, claimant_method, validator_method,
evidence_overlap}` and the verifier compares hashes. "Different prompt" is **not** independence;
"different model" is **not** required. This matches 2B-R §3. **No new artifact beyond G2/G3.**

---

## 9. Typed organizational graph (edges, not agents)

The firm is `Agent → typed-edge → Agent`. Edge types (the prompt's list) each carry: permitted
artifact type, trust semantics, authority semantics, lineage requirement, mutability, rejection-
creates-loop, epistemic-dependency. **SUPPORTED by current architecture**: the backward
reconstruction the prompt wants ("why did this trade happen?") is *already implemented* in
`fleet/layers/verification.evaluate_intel` — it traverses `evidence_refs`, counts distinct refs,
flags hallucination, checks staleness, and `VerificationLog`/`VerificationRow` is the append-only
ledger. So the **verifier is done**; what's missing is **labeling the orchestration edges** (G7) so
the runtime enforces "a `BELIEF_FLOW` may never carry an `AUTHORIZATION_FLOW` payload" at the
message layer, not just the module layer. **PROPOSED: G7** (typed edge labels in orchestration).

Sample edges from the firm:
```
Data Engineer ──DATA_FLOW──► Alpha Researcher
Alpha Researcher ──BELIEF_FLOW──► Model Validation
Model Validation ──VALIDATION_FLOW──► Risk
Risk ──RISK_ASSESSMENT──► Portfolio
Portfolio ──PROPOSAL_FLOW──► Governance
Governance ──AUTHORIZATION_FLOW──► Trading
Trading ──EXECUTION_FLOW──► Operations
Operations ──OBSERVATION_FLOW──► Risk
Compliance ──OVERSIGHT_FLOW──► (everyone; standing read + veto)
Risk ──CHALLENGE_FLOW──► Model Validation   (drift re-validation loop)
```

---

## 10. Full quantitative-firm workflow mapping (generality check)

Each department mapped to the same substrate (confirms no trading-specific framework is needed):

| Dept | Substrate mapping | New primitive? |
|------|-------------------|----------------|
| Research | Obs→Evid→Belief→Prediction→StrategySpec | G1 |
| Validation | Claim→Indep Evidence→Challenge→ValidationArtifact | G2,G3 |
| Risk | Obs→RiskAssessment→Policy-compare→Breach | (uses existing RiskLayer) |
| Portfolio | Validated→Allocation Proposal→Risk-constrained | (Proposal) |
| Trading | Allocation→Exec Proposal→Auth→Order | (existing) |
| Operations | Exec→Settlement→Reconciliation→Authoritative State | G5 |
| Compliance | Activity→Surveillance Evid→Compliance Assessment→Block/Report | (Assessment subkind) |
| Technology | Sys Obs→Incident Evid→Diagnosis→Remediation Proposal→Auth Action | (same substrate; `domain` differs) |
| Data Eng | Vendor Obs→Clean Obs→Lineage | (Observation) |
| Executive | Strategy Proposal→Governance Decision | (Proposal/Decision) |

**Conclusion:** the *same* object chain serves all 10 departments. Only `Proposition.domain` and
`ActionDescriptor` differ. Finance is the richest environment; incident/security/research are the
same graph with different domains. **Architecture is domain-general — confirmed.**

---

## 11. Missing-primitives analysis (minimum sufficient ontology)

| Primitive | Exists? | EOM sufficient? | New required? | Why |
|-----------|---------|-----------------|---------------|-----|
| Proposition | DESIGNED (F1) | yes | — | structured key |
| Observation | DESIGNED | yes | — | |
| Evidence | IMPLEMENTED (QuantEvidence) | yes | — | |
| Belief | IMPLEMENTED (ProbabilityEstimate, pre-F1) | yes after F1 | — | |
| Prediction/Hypothesis | DESIGNED | yes | — | |
| **Assessment** | — | **no (unnamed)** | name as subkind | deterministic state-vs-policy; firm produces constantly |
| **Recommendation** | — | **no (unnamed)** | name as subkind | advisory, no authority; distinct from Proposal |
| Proposal | IMPLEMENTED | yes | — | |
| ValidationArtifact | PROPOSED (G2) | needs object | yes (G2) | holds both claims + independence |
| IndependenceContract | PROPOSED (G3) | needs object | yes (G3) | minimal hash-compare |
| DisagreementRelation | PROPOSED (G9) | needs object | yes (G9) | shared-evidence detection |
| RiskAssessment | IMPLEMENTED (RiskLayer) | yes | — | |
| RiskBudget | PROPOSED (G6) | needs object | yes (G6) | promote Mandate to signed |
| AuthorizationRequest/Decision | IMPLEMENTED (decide_trade) | yes | — | |
| ExecutionReceipt | IMPLEMENTED | yes | — | |
| SettlementRecord/Outcome | PROPOSED (G5) | needs object | yes (G5) | feeds calibration |
| CalibrationRecord | IMPLEMENTED | yes | — | |
| CalibrationProfile | PROPOSED (G4) | needs seal | yes (G4) | currently free functions |
| **AuditRecord** | **IMPLEMENTED** (VerificationLog/Row + evaluate_intel) | **yes** | **NO** | do NOT create new — reuse ledger |
| Escalation | DESIGNED (edge type) | yes | — | |
| `fleet/epistemic/` package | PROPOSED (G0) | needs home | yes (G0) | neutral vocab home |

**Minimum sufficient ontology:** the EOM already covers ~60% (Observation/Evidence/Belief/Proposal/
Auth/Action/Outcome/Calibration/Verification all exist or are designed). The firm adds only:
**G0 (package), G1–G6, G9 (already identified in 2B-R), the Assessment/Recommendation subkinds, and
the authority split (§3).** It does **not** require dozens of role-specific objects — the
abstraction holds.

---

## 12. Generalization analysis

The firm forces the architecture to confront: uncertainty, probabilistic reasoning, competing
models, independent validation, risk, capital allocation, execution, adversarial incentives,
calibration, changing environments, auditability, deterministic authority. Every one maps onto an
existing or already-identified primitive. **Test passed for finance.** The same substrate then
serves:
- **Incident response** — `Proposition.domain="incident_compromised"`, Assessment="severity
  exceeds SLA", Recommendation="isolate host", Proposal="request containment", Auth, Action.
- **Security ops** — same, `domain="host_breached"`.
- **Scientific research** — `domain="hypothesis_true"`, Belief=result probability, Validation=
  replication, Calibration=reproducibility rate.
- **Robotics / ops / forecasting** — identical graph, different `domain`/`ActionDescriptor`.

No separate governance architecture per domain. **Confirmed domain-general.**

---

## 13. Revised definition of an agent

**Challenged and confirmed:** *"An agent is an entity capable of producing or transforming typed
artifacts under an explicit epistemic and authority contract."* The firm confirms this is broader
than an LLM: a Market Data Feed (Identity + narrow EpistemicProfile, produces Observation), a
Backtest Engine (produces Evidence, deterministic), a Risk Calculator (produces Assessment,
deterministic), a human reviewer (Identity + cert, produces Belief), an Execution Algorithm
(Identity + `execute_order` capability, produces Action), a Governance Engine (Identity +
`authorize` capability, produces Decision) — all fit **one** abstraction. The LLM is one
*implementation* of an epistemic producer. **No better definition suggested by the repo.**

---

## 14. Organizational operating system (substrate + firm placement)

```
Identity ──► Epistemic Contract (5→6 scopes, §3) ──► Evidence+Lineage ──► Belief/Prediction
   ──► Assessment/Recommendation ──► Validation (G2/G3) ──► Disagreement (G9)
   ──► Aggregation ──► Proposal ──► Governance (Auth) ──► Authorization ──► Execution
   ──► Verification (ledger) ──► Outcome ──► Calibration ──► Adaptation
```

Firm departments placed: Research/Validation/Risk/PM/Trading/Ops/Compliance/Data/Exec/Tech each
*occupy a band* of this substrate (e.g. Research = Evidence→Belief→StrategySpec; Compliance =
Oversight across the whole chain). The firm is the **reference implementation** that proves the
substrate; it is not the product. The product is the governed epistemic operating system.

---

## 15. Proposed dependency graph for implementation

```
L0  fleet/epistemic/ (G0) + core objects (Obs, Evidence, Belief, Proposition,
    Proposal, AuthRequest, AuthDecision, Action, Outcome, CalibrationRecord)
        │
L1  Epistemic Contract — 5 scopes (2B-R) → EXTEND to 6: split authority into
    authorization_profile + capability_profile (§3)  [ratify Q1]
        │
L2  Agent identity decomposition: Identity + EpistemicProfile
    + CapabilityProfile + AuthorizationProfile + GovernancePolicy + RoleDefinition
    + derived CalibrationProfile           [depends on L1]
        │
L3  { ValidationArtifact + IndependenceContract (G2,G3) }     ← parallel
    { RiskBudget promotion of Mandate (G6) }                  │
        │                                                      │
L4  Role Card decomposition → external GovernancePolicy       [depends L2–L3]
        │
L5  { CalibrationProfile seal (G4) }  { SettlementRecord (G5) }
    { DisagreementRelation (G9) }  { typed edge labels (G7) }  ← parallel
        │
L6  Organizational orchestration (map firm roles to contracts)
```

**Do not implement before L0–L2 are ratified + boundary-tested** (unchanged from 2B-R).

---

## 16. Architectural decisions requiring ratification

These are the **open** decisions the firm forced. Each is a real fork; I have not resolved them.

- **Q1 (load-bearing).** Split `authority_scope` into `authorization_profile` (organizational
  authority: veto/halt/approve/override/budget-grant) + `capability_profile` (operational: action
  execution)? *Recommended yes* — the firm shows they are orthogonal (CCO has authority, no
  capability; Trader has capability, no authority). **This is the single most important ratification.**

- **Q2.** Are `Assessment` (deterministic state-vs-policy) and `Recommendation` (advisory, no
  authority) **subkinds** of existing objects (Evidence/Belief and Proposal respectively), or
  **first-class** types? *Recommended subkinds* — avoids ontology explosion; the firm needs the
  *vocabulary*, not new machinery.

- **Q3.** Is `AuditRecord` a new primitive? **No** — it already exists as `VerificationLog`/
  `VerificationRow` + `evaluate_intel` backward traversal. **Do not create one.** (Stated to prevent
  over-building.)

- **Q4.** Does `RiskBudget` (G6) get created by CRO via governance, or by a deterministic policy
  engine? *Recommended CRO-signed governance grant* (human/role in authority, not a model). Already
  implied by §7 invariant.

- **Q5.** Should `DisagreementRelation` (G9) be produced eagerly (on every competing-belief set) or
  lazily (on aggregation request)? *Recommended lazy* — cheaper, and disagreement is only consumed
  at aggregation time.

- **Q6 (generalization gate).** After L0–L2, do we validate the substrate against a *second* domain
  (incident response) before building L3–L6, or proceed finance-only first? *Open* — affects
  whether we discover domain-specific gaps early.

---

## TAGGED SUMMARY

- **IMPLEMENTED:** `AgentCert` (capabilities), `QuantEvidence`, `ProbabilityEstimate`,
  `RiskLayer.assess`+`Mandate`, `decide_trade` (no prob), `ExecutionReceipt` pattern,
  `CalibrationRecord`, `VerificationLog`/`Row`+`evaluate_intel` (backward traversal/ledger).
- **DESIGNED:** EOM loop, F1 structured `Proposition`, F3 lineage, `ValidationArtifact` (G2),
  `StrategySpec` (G1), `SettleRecord` (G5), `CalibrationProfile` (G4), `DisagreementRelation` (G9),
  `IndependenceContract` (G3), typed edges (G7), `fleet/epistemic/` home (G0).
- **SUPPORTED BY CURRENT ARCHITECTURE:** the five-dimension agent split (Standing/Org-Authority/
  Op-Capability), backward "why did this trade happen?" traversal, domain-generality (finance =
  one `domain`), the "model can't redefine its own risk" invariant (external signed objects).
- **PROPOSED:** split `authority_scope` → `authorization_profile` + `capability_profile` (Q1); name
  `Assessment` + `Recommendation` subkinds (Q2); `RiskBudget` CRO-signed (Q4).
- **OPEN QUESTION:** Q1, Q2, Q4, Q5, Q6 (ratification required before L0–L2 implementation).

*No code written. Not committed. The firm remains the concrete environment; the epistemic
architecture remains the abstraction. Round 2C complete as a design-only stress test.*
