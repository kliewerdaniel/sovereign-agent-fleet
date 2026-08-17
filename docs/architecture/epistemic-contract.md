# Round 2B-R — Epistemic Contract & Architectural Ratification

> **Status: DESIGN ONLY. No code. No commit.** This resolves the coupled decisions exposed by
> `epistemic-org-mapping.md` — independence (A2), risk authority (C5), and Role Card runtime
> semantics (E) — into a single coherent **Epistemic Contract** that defines what an "agent" is
> inside Sovereign Agent Fleet. It answers: *what an agent knows / may claim / may propose / may
> authorize / may actually do* — as five **separate** concepts.
>
> Constraints honored: no runtime code, no behavior change, no commit. Grounded in the actual repo
> (`AgentCert`, `RiskLayer.assess`/`Mandate`, `decide_trade`, `QuantEvidence`, `CalibrationRecord`)
> and the two prior design docs.

---

## 1. Current architectural grounding

Legend: **IMPLEMENTED** (in repo), **DESIGNED** (Round 2A/2B doc), **PROPOSED** (this doc),
**MISSING** (not yet anywhere).

| # | Concept | Status | Evidence in repo |
|---|---------|--------|------------------|
| 1 | EOM closed loop | DESIGNED | `epistemic-object-model.md` |
| 2 | Role Card (org) | IMPLEMENTED (org doc) | supplied firm design |
| 3 | Agent identity | **IMPLEMENTED** | `AgentCert{agent_id,pubkey_pem,role,capabilities,issued_at,expires_at,cert_seq,root_sig}` (`fleet/crypto/foundation.py:67`) |
| 4 | Evidence | **IMPLEMENTED** (financial) | `QuantEvidence` (`exchange/quant/evidence.py:41`) — hash-bound, carries only constituent hashes, ignored by gates |
| 5 | Belief | **IMPLEMENTED** (financial) | `ProbabilityEstimate` (`exchange/quant/probability.py:43`) — frozen, hashable, but **unstructured subject** (pre-F1) |
| 6 | Proposition | DESIGNED | F1 structured `Proposition{domain,subject,predicate,params}` |
| 7 | Proposal | **IMPLEMENTED** (split) | `ProposalArtifact{governance_surface, enrichment}` (`fleet/cognition/evaluation.py:92`) |
| 8 | Validation | MISSING | no `ValidationArtifact`; `Backtest Engineer`/`Model Validation Lead` are prose roles only |
| 9 | Risk assessment | **IMPLEMENTED** | `RiskLayer.assess(...)` pure deterministic (`fleet/fin/domain.py:229`) |
| 10 | Authorization | **IMPLEMENTED** | `decide_trade(...)` pure `f(qty,side,venue,intel)`, **no probability** (`exchange/governance.py:106`) |
| 11 | Action | **IMPLEMENTED** | `ExecutionReceipt` pattern (signed, state-locked) |
| 12 | Outcome | **IMPLEMENTED** (financial) | `CalibrationRecord` (immutable `predicted_prob`+`outcome`) |
| 13 | Calibration | **IMPLEMENTED** (functions) | `brier_score`/`rolling_brier`/`reliability_bins` — **free functions, not sealed** |
| 14 | Lineage | DESIGNED | hash references in EOM; not yet enforced on financial path (F3) |
| 15 | Capability/authority | **IMPLEMENTED** | `AgentCert.capabilities: List[str]` + gateway enforcement |

**Conclusion:** the *authority wall* is already real (identity capability-scoped; risk assessment
pure + external `Mandate`; authorization excludes probability). What is **MISSING** is the
**agent-level contract** that applies this wall uniformly across research/validation/PM/CRO/etc.,
plus the independence + validation + risk-budget objects the org needs. None of those require
changing the wall — they require *naming and generalizing* it.

---

## 2. The Epistemic Contract (definition)

Every agent is bound by a contract with **five independent scopes**. Authority scope is the *only*
one that grants power; the other four describe what the agent may cognize. They are never collapsed.

```
EpistemicContract(agent_id):
  epistemic_scope   → proposition_domains it MAY emit Beliefs about
  evidence_scope    → evidence it may CONSUME / PRODUCE + lineage requirements
  belief_scope      → belief kinds/uncertainty types it may produce (⊆ epistemic_scope)
  proposal_scope    → action_descriptor kinds it may PROPOSE (never authorize)
  authority_scope   → capability strings its AgentCert carries  ← THE ONLY REAL POWER
```

**"allowed to reason about" ≠ "allowed to authorize."** A Model Validator has deep
`model_validity` epistemic scope but **no** `exchange.trade_execute` authority. A CRO has
`risk_halt` authority but a narrow `risk_exposure` epistemic scope. This split is the entire point.

- **Evidence scope:** an agent may consume evidence whose `evidence_refs` satisfy its
  `lineage_requirements`. On the financial path (F3) incomplete lineage → the *evidence gate* (D16
  HALLUCINATION-equivalent) **BLOCKS** the downstream request. Elsewhere incomplete lineage
  → downgrade to `ASSERTED` trust tier (logged, never silently trusted).
- **Belief scope:** a Belief outside `epistemic_scope` is **not** auto-blocked (that would chill
  legitimate cross-domain signals). It is emitted **tagged `out_of_specialization`**, and
  `EpistemicAggregation` down-weights it. (Open fork — see §13 Q2.)
- **Proposal scope:** an Alpha Researcher may propose *"strategy S should be considered for
  validation"* (action_descriptor `submit_for_validation`). It may **not** propose *"allocate
  $X"* (`request_capital`) — that is PM `proposal_scope`. The boundary from epistemic output to
  operational proposal is exactly the `Proposal.action_descriptor` whitelist.
- **Authority scope:** the `capabilities` list on `AgentCert`. **Nothing else** confers authority.
  Calibration, role title, and belief quality grant epistemic weight, never capability.

---

## 3. Independence model (A2) — and why it couples to risk + Role Card

**Finding:** independence is **not** a property of an agent's *architecture*. Two researchers on
the same foundation model are independent *iff* they use non-shared data + non-shared context — and
two agents on *different* models are **not** independent if they share data + reasoning trace. The
org's separation (Research ⊥ Validation, Trading ⊥ Operations, Risk ⊥ PM) is therefore a property
of **workflows and artifacts, not agents**.

So `IndependenceConstraint` belongs on the **validation workflow / `ValidationArtifact`**, not on
the agent:

```
IndependentValidation requires:
  claimant_data_snapshot_id  ≠ validator_data_snapshot_id
  claimant_methodology_version ≠ validator_methodology_version
  validator_context did NOT inherit claimant reasoning trace
```

Verifiability: compare the **hashes** of snapshot / method / context. "Different prompt" is **not**
independence. "Different foundation model" is **not** required. Independence is **workflow- and
artifact-scoped** — recorded in `ValidationArtifact`, checkable by the verifier from hashes alone.

This is why A2 couples to E (Role Card): the Role Card's `independence_constraints` field is a
*workflow requirement* (GovernancePolicy), not an agent attribute. And it couples to C5: the
validator that reproduces a strategy uses a *separate* `RiskBudget`/`data_snapshot` than the
researcher — the same external-authority principle.

---

## 4. Risk / authority model (C5)

The repo already separates these; we promote `Mandate` to a first-class signed object.

```
BELIEF          "P(adverse) ≈ 4.7%"                         (probabilistic, cognition)
EVIDENCE        "historical/model support for that estimate" (Evidence)
RISK ASSESSMENT "given state S, exposure ≈ X"               (deterministic: RiskLayer.assess)
RISK POLICY     "exposure may not exceed Y"                 (deterministic limit)
RISK BUDGET     "strategy S granted Z"                      (signed grant, external)
AUTHORIZATION   "this action permitted"                     (decide_trade)
```

**`RiskBudget` (PROPOSED, promotes existing `Mandate`):**
```
RiskBudget {
  strategy_spec_hash: str        # binds to the validated StrategySpec (G1)
  granted_by: str                # CRO cert agent_id (governance-owned)
  limits: {...}                  # max_position_pct, allowed_assets/sides (today's Mandate fields)
  epoch: int                     # decision epoch
  signature: str                 # CRO-signed
}
```
Properties: **governance-owned** (created by CIO/CRO via governance, not by the risk model),
**signed**, **state-bound** (to `strategy_spec_hash`), **immutable for the epoch**, **separate
from the model** that produces risk *estimates*. **A model can never modify its own RiskBudget.**

Invariant realized: *A MODEL MAY ESTIMATE RISK. A GOVERNED AUTHORITY SETS RISK LIMITS.* This is
already true in `fleet/fin`; `RiskBudget` makes it explicit and general.

---

## 5. Role Card decomposition (E)

The supplied Role Card conflates **five** concepts. Decompose:

| Separated concept | Contains | Classification of its fields |
|-------------------|----------|------------------------------|
| **`RoleDefinition`** | mandate, KPIs, escalation *prose*, department | **D** (human-readable documentation) |
| **`AgentIdentity`** | agent_id, pubkey_pem, cert_seq, root_sig, issued_at/expires_at | **A** (runtime security primitive) |
| **`EpistemicProfile`** | proposition_domains, evidence_scope, belief_scope, calibration_profile ref | **B** (epistemic metadata) |
| **`CapabilityProfile`** | capabilities, allowed_action_types, forbidden_capabilities, risk_limits, approval_dependencies | **A** (runtime security primitive) |
| **`GovernancePolicy`** | independence_constraints, escalation_conditions, lineage_requirements | **C** (governance configuration) |
| **`CalibrationProfile`** | reliability/resolution/Brier per (producer,template,regime) | **E** (derived state — computed, not stored on agent) |

Field-by-field classification (per the prompt's A–E):

| Field | Class | Note |
|-------|-------|------|
| role_id / department | D | documentation |
| mandate | D | documentation |
| epistemic_scope | B | → EpistemicProfile |
| authority_scope | A | → CapabilityProfile (capabilities) |
| proposition_domains | B | → EpistemicProfile |
| allowed_action_types | A | → CapabilityProfile |
| evidence_requirements / lineage_requirements | C | → GovernancePolicy |
| independence_constraints | C | → GovernancePolicy (workflow) |
| forbidden_capabilities | A | → CapabilityProfile |
| escalation_conditions | C | → GovernancePolicy |
| risk_limits | A | → CapabilityProfile (RiskBudget ref) |
| approval_dependencies | C | → GovernancePolicy |
| calibration_profile | E | derived from CalibrationRecord |

So the Role Card is **not one schema** — it is `AgentIdentity + EpistemicProfile + CapabilityProfile`
(the runtime-enforced contract) plus external `GovernancePolicy` plus documentation `RoleDefinition`
plus derived `CalibrationProfile`. This decomposition is what makes the "authority ≠ a score" test
(§6) structurally enforceable: capability lives only in `CapabilityProfile`; calibration lives in a
*separate derived* profile and can never leak into it.

---

## 6. Authority must not be a score (the defining test)

Scenario: Agent A (calibration 94%) wants $500k exposure; Agent B (calibration 71%) wants $50k.
**A does NOT automatically get more authority.** Why:

- Authority = `capabilities` on `AgentCert` + `RiskBudget` signed by CRO. Neither is a function of
  `CalibrationProfile`. The gateway checks `capability ∈ cert.capabilities`; it never reads a
  calibration number to grant capability.
- Calibration is **epistemic standing** (affects belief *weight* in aggregation), not a capability.
- Therefore: Agent A (excellent calibration, **no** `trade_execute` capability) may have high
  epistemic influence — its Beliefs are weighted heavily — yet execute **nothing**. Agent B
  (mediocre calibration, `trade_execute` capability, strict $50k `RiskBudget`) executes within
  authority. The system permits both simultaneously. This is enforced by the decomposition in §5:
  `CalibrationProfile` (E) is physically separate from `CapabilityProfile` (A) and cannot write to it.

---

## 7. Competing beliefs & disagreement as first-class information

No voting. The five agents on one F1 `Proposition` produce five `Belief`s. Disagreement is a
**derived first-class relation**, not a scalar:

```
AgreementRelation | DisagreementRelation {
  proposition: Proposition
  constituent_belief_refs: list[hash]
  evidence_overlap: set intersection of evidence_refs        # A & C share E1,E2 → low independence
  independence: derived from snapshot/method/context hashes  # §3
  model_correlation: cluster by model_id
  temporal_disagreement / regime_disagreement / uncertainty_disagreement / methodological_disagreement: stats
  disagreement_magnitude: spread of estimates
}
```

- This is an **Evaluation/Epistemic relation** (consumed by `EpistemicAggregation`, not a Belief).
- A and C sharing E1,E2 are detected as **one effective opinion**, not two — preventing spurious
  "disagreement" from repeated sourcing.
- Disagreement itself is *informative*: high spread can raise the trust tier to `ASSERTED` or
  trigger a `ValidationArtifact`, never auto-resolve.

---

## 8. Validation as an adversarial epistemic process

`ValidationFinding` and `ValidationArtifact` become **first-class** (G2):

```
Research Claim (Belief/StrategySpec)
   → Independent Reconstruction (validator, separate context)
   → Independent Evidence (its own snapshot/method)
   → ValidationFinding { what tested, evidence used, environment, data_snapshot, model_version, result }
   → Agreement / Conditional / Rejection
   → ValidationArtifact { claimant, validator, independence_proof, finding, remaining_uncertainty, status }
```

The verifier must reconstruct: WHAT claimed, WHO, WHAT tested, WHAT evidence, WHICH environment,
WHICH snapshot, WHICH model version, WHAT found, WHAT uncertain, WHY accepted/rejected. **Validation
evidence ≠ authorization** — `ValidationArtifact` feeds `RiskAssessment` as evidence; it never
directly produces `AuthorizationDecision`.

---

## 9. Minimum Agent abstraction

An "agent" is **broader than an LLM**. Minimum conceptual object:

```
Agent = AgentIdentity + Role + EpistemicProfile + CapabilityProfile
        + (external) GovernancePolicy + (derived) CalibrationProfile
```

| Component | Status |
|-----------|--------|
| Identity (cert) | **REQUIRED** |
| Role + EpistemicProfile | **REQUIRED** (what it may know/claim) |
| CapabilityProfile | **REQUIRED** (what it may do) |
| Memory / Model | **OPTIONAL / INTERNAL** (implementation detail) |
| GovernancePolicy | **EXTERNAL** (config, not on agent) |
| CalibrationProfile | **DERIVED** (from Outcomes) |

A deterministic statistical process, a human, a market-data feed, a validator, and a governance
engine are all "agents" by holding an identity + the relevant profiles. The LLM is one
*implementation* of an epistemic producer — not a requirement.

---

## 10. Human / model / service symmetry

All fit the **same lifecycle**; they differ only in which profiles they hold:

| Entity | Produces | Profiles held |
|--------|----------|---------------|
| Market Data Feed | `Observation` | Identity + minimal EpistemicProfile (raw data only) |
| Statistical Model | `Belief` | Identity + narrow epistemic_scope |
| LLM Research Agent | `Belief` | Identity + broad epistemic_scope |
| Human Researcher | `Belief` | Identity + epistemic_scope (+ human cert) |
| Validator Agent | `Validation Evidence` | Identity + `model_validity` scope + independence workflow |
| Governance Engine | `AuthorizationDecision` | Identity + `capabilities` = authorize |
| Backtest Engine | `Evidence` (methodology) | Identity + deterministic |

No separate epistemic architecture per entity type. Symmetry holds → finance is just one
`proposition_domains` set; incident/security/research are others.

---

## 11. Complete quantitative-finance lifecycle (canonical example)

For each transition: OBJECT · PRODUCER · CONSUMER · AUTHORITY · EVIDENCE · LINEAGE · DETERMINISM ·
UNCERTAINTY · CALIBRATION.

| # | Transition | Object | Producer | Consumer | Authority | Evidence | Lineage | Determ. | Uncertainty | Calib. |
|---|-----------|--------|----------|----------|-----------|----------|---------|---------|-------------|--------|
| 1 | discover strategy | `StrategySpec`(hypothesis) | Alpha Researcher | Backtest Eng | none (RECOMMEND) | datasets | partial | no | p_yes, epistemic | — |
| 2 | backtest | `Evidence`(backtest) | Backtest Eng | Model Validation | Backtest gate (APPROVE-method) | StrategySpec | spec→result | yes(method) | method risk | — |
| 3 | independent validate | `ValidationArtifact` | Model Validation | Risk | validation gate (APPROVE) | independent snapshot | sep. snapshot | yes | remaining uncert. | — |
| 4 | risk evaluate | `RiskAssessment` | RiskLayer | CRO/PM | CRO (AUTONOMOUS halt) | ValidationArtifact | va→risk | **yes** | exposure est. | — |
| 5 | allocate capital | `Proposal`(target) | Portfolio Mgr | Governance | CRO `RiskBudget` | RiskAssessment | risk→prop | yes(budget) | alloc uncrert. | — |
| 6 | authorize | `AuthorizationRequest`→`Decision` | Governance | Trading | Governance (AUTO/HUMAN/BLOCKED) | proposal_hash | prop→decision | **yes** | **none consumed** | — |
| 7 | execute | `Action`(`ExecutionReceipt`) | Execution Trader | Operations | trade_execute cap | decision | decision→receipt | yes(state-lock) | — | — |
| 8 | record | `Observation`(positions) | Operations | Risk | recon sign-off | fills | receipt→obs | yes | — | — |
| 9 | outcome | `SettleRecord`/`Outcome` | Market/Settle | Calibration | none | receipt+market | obs→outcome | yes | — | — |
| 10 | evaluate | `CalibrationRecord` | Calibration | CalibProfile | none | Prediction×Outcome | immutable | yes | — | **written** |
| 11 | drift monitor | `Observation`(drift) | Model Risk Val | Model Validation | re-validation trigger | live vs spec | ongoing | yes | — | feeds profile |

Note the **determinism column**: only cognition steps (1,2,3 partial,10) are probabilistic; the
authority path (4,5,6,7,8,9,11) is **entirely deterministic** and never consumes a probability.
This is M0, made explicit per-transition.

---

## 12. Missing architectural primitives (consolidated)

| ID | Primitive | Status | Depends on |
|----|-----------|--------|-----------|
| G0 | `fleet/epistemic/` package (neutral home) | PROPOSED | — |
| G1 | `StrategySpec` | PROPOSED | G0 |
| G2 | `ValidationArtifact` + `ValidationFinding` | PROPOSED | G0, G1 |
| G3 | `IndependenceConstraint` (or infer from snapshot hashes) | PROPOSED | G2 |
| G4 | `CalibrationProfile` (seal existing functions) | PROPOSED | G0 |
| G5 | `SettleRecord`/`OutcomeRecord` | PROPOSED | G0 |
| G6 | `RiskBudget` (promote `Mandate`) | PROPOSED | G0, existing RiskLayer |
| G7 | Typed message/edge labels in orchestration | PROPOSED | G0 |
| G8 | `EpistemicProfile` / `CapabilityProfile` decomposition | PROPOSED | G0, existing AgentCert |
| G9 | `Agreement`/`DisagreementRelation` | PROPOSED | G0 |
| — | F1 `Proposition` (structured) | DESIGNED (2A) | G0 |
| — | F3 lineage enforcement | DESIGNED (2A) | G0 |

Additive only — none alter the closed loop or M0.

---

## 13. Dependency graph for future implementation (sequence, not convenience)

```
Layer 0:  fleet/epistemic/ package + core objects (Obs, Evidence, Belief, Proposition,
          Proposal, AuthRequest, AuthDecision, Action, Outcome, CalibrationRecord)
          ── everything depends on this; fragments already exist, need promotion
               │
Layer 1:  Epistemic Contract (5-scope split: epistemic/evidence/belief/proposal/authority)
               │
Layer 2:  Agent identity decomposition → AgentIdentity + EpistemicProfile + CapabilityProfile
          (extends existing AgentCert; no new authority model)
               │
Layer 3:  { Independence model + ValidationArtifact/Finding (G2,G3)        }
          { RiskBudget promotion of Mandate (G6)                            }   ← parallel, both
               │                                                              depend on L1–L2
Layer 4:  Role Card decomposition → RoleDefinition + GovernancePolicy (G8)  ← depends on L2–L3
               │
Layer 5:  { CalibrationProfile seal (G4)  }                                 ← parallel
          { Epistemic graph typed edges (G7) }
          { Agreement/DisagreementRelation (G9) }
               │
Layer 6:  Organizational orchestration (maps firm roles to contracts)       ← depends on all
```

**Do not implement before L0–L2 are ratified** — they are the contract skeleton the rest hangs on.

## 14. Highest-impact ratification questions (SEQUENCED, not isolated)

These are ordered by dependency. **Q1–Q2 must be answered before Q3–Q6 are meaningful**, because
Q3–Q6 all hang off the contract skeleton — exactly the coupling you flagged.

**Q1 (foundation — contract skeleton).** Ratify the **5-scope Epistemic Contract**
(epistemic / evidence / belief / proposal / authority) as the definition of an agent. → if no, the
whole 2B-R model collapses; if yes, proceed.
→ **Recommendation: ratify.** This is the natural generalization of the already-implemented
`AgentCert.capabilities` + `Mandate` + `decide_trade` wall.

**Q2 (coupled to Q1 — out-of-scope handling).** A Belief outside `epistemic_scope`:
- (a) **BLOCKED** (rejected at emit), or
- (b) **DEGRADED + flagged `out_of_specialization`**, down-weighted in aggregation (recommended)?
→ Recommendation: (b) — blocking chills legitimate weak-signal cross-domain inputs.

**Q3 (independence — couples to Q1).** Confirm independence is **workflow/artifact-scoped**
(snapshot + method + context hash comparison in `ValidationArtifact`), **not** agent-architecture-
scoped. "Different prompt" ≠ independent; "different model" ≠ required. → Recommendation: yes.

**Q4 (risk authority — couples to Q1).** Promote `Mandate` → signed **`RiskBudget`** (governance-
owned, CRO-signed, immutable per epoch, separate from the risk model). Confirm a model **cannot**
modify its own budget. → Recommendation: yes (already true in `fleet/fin`; make explicit + general).

**Q5 (Role Card — couples to Q1,Q3,Q4).** Decompose the Role Card into the 6 profiles (§5); confirm
`RoleDefinition`/mandate/KPIs/escalation-prose are **category D** (documentation, outside runtime),
and `CalibrationProfile` is **derived (E)**, never stored on the agent. → Recommendation: yes.

**Q6 (disagreement — couples to Q1).** Make `Agreement`/`DisagreementRelation` first-class (G9);
low-independence overlap (A&C sharing E1,E2) counts as **one** opinion, down-weighted not excluded.
→ Recommendation: yes.

**Q7 (minimum agent — couples to Q1).** Confirm "agent" = `Identity + Role + EpistemicProfile +
CapabilityProfile` (broader than LLM; a feed/model/human/validator all qualify by holding the
relevant profiles). → Recommendation: yes.

**Q8 (implementation gate).** After Q1–Q7: proceed to implement **L0→L2 only** first (package +
contract + identity decomposition), deferring L3–L6 to a follow-up. → Recommendation: yes — do not
build validation/risk/calibration frameworks until the contract skeleton is ratified and tested.

---

*No code written. Not committed. Round 2C (adaptation) follows only after Q1–Q7 ratify the
contract and L0–L2 are implemented + boundary-tested.*
