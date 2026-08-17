# Round 2E — Epistemic Architecture Synthesis (pre-implementation ratification)

> **Status: DESIGN ONLY. No code. No schema. No `fleet/epistemic/`. No commit. No push.** Final
> synthesis pass. Reconciles the five prior design docs against the quantitative-finance firm as the
> concrete operating environment, converts the five open 2D ratifications into **explicit
> architectural requirements**, hunts contradictions honestly, and answers the gating question with
> proof rather than optimism.
>
> References (not duplicated): `epistemic-object-model.md` (2A), `epistemic-org-mapping.md` (2B),
> `epistemic-contract.md` (2B-R), `quantitative-organization-architecture.md` (2C),
> `agent-boundary-and-decision-semantics.md` (2D). Repo primitives cited: `AgentCert`,
> `RiskLayer.assess`+`Mandate`, `decide_trade`, `QuantEvidence`, `ProbabilityEstimate`,
> `CalibrationRecord`, `VerificationLog`/`evaluate_intel`.

---

## 1. The architecture as one system (the thesis tested)

**Architectural thesis:**
> **AGENTS PRODUCE KNOWLEDGE AND INTENT. GOVERNANCE PRODUCES PERMISSION. SYSTEMS PRODUCE STATE
> TRANSITIONS. VERIFICATION PRODUCES AUDITABLE TRUTH.**

The single coherent value chain (not every stage required per workflow):

```
Observation ─► Evidence ─► Belief ─► Assessment ─► Recommendation ─► Proposal
   ─► AuthorizationRequest ─► AuthorizationDecision ─► Action ─► Execution/State
   ─► Outcome ─► Evaluation ─► Calibration ─► updated EpistemicState
```

Classification of each artifact (every existing object tested against the thesis):

| Artifact | epistemic | deterministic | advisory | governance-owned | executable | observational | evaluative | derived |
|----------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Observation | | | | | | ✓ | | |
| Evidence | ✓ | | | | | | | |
| Belief | ✓ | | | | | | | |
| Prediction | ✓ | | | | | | | |
| Assessment | | ✓ | | | | | | |
| Recommendation | | | ✓ | | | | | |
| Proposal / AuthRequest | | | ✓ | | | | | |
| AuthorizationDecision | | | | ✓ | | | | |
| Action | | | | | ✓ | | | |
| Execution/State | | ✓ | | | ✓ | | | |
| Outcome | | | | | | ✓ | | |
| Evaluation | | | | | | | ✓ | |
| Calibration | | | | | | | ✓ | ✓ |
| EpistemicState | ✓ | | | | | | | ✓ |

**Test result:** every existing object fits the thesis cleanly. No object is simultaneously
epistemic *and* governance-owned, or advisory *and* executable. The classification is *orthogonal* to
the decision ladder — which is exactly what makes the boundary enforceable. The thesis holds.

---

## 2. The quantitative firm as stress test (workflows executed)

### 2.1 Strategy lifecycle
| Transition | Artifact | Producer | Evidence ref'd | Uncertainty? | Recipient may modify? | Recipient role | Authority req | Deterministic check | On reject |
|------------|----------|----------|----------------|:--:|----------------|---------------|----------------|---------------------|-----------|
| Strategy→Research | `StrategyHypothesis`(Belief) | Head of Strategy | none | yes | no (producer) | Head of Research | none | — | escalates to CIO |
| Research→Backtest | `Evidence`(backtest) | Alpha Researcher | datasets | no | no | Backtest Eng | backtest gate | reproducibility | method reject |
| Backtest→Validation | `StrategySpec`(G1) | Alpha Researcher | evidence | no | no (until validated) | Model Validation | none | spec completeness | → ValidationArtifact(reject) |
| Validation→CRO | `ValidationArtifact`(G2) | Model Validation | indep snapshot | no | no | CRO | validation gate | independence check (G3) | → Governance |
| CRO→PM | `RiskAssessment`+`RiskBudget`(G6) | CRO (gov) | ValidationArtifact | no | **CRO only** | PM | CRO authority | signature+epoch | CRO revokes budget |
| PM→Trading | `Proposal`(order) | PM | RiskBudget | no | no | Governance | none | action_descriptor whitelist | → HUMAN_REVIEW/BLOCKED |
| Governance→Trading | `AuthorizationDecision` | Governance | proposal_hash | no | **no** | Execution Trader | governance cap | `decide_trade` (no prob) | BLOCKED |
| Trading→Ops | `Action`(ExecutionReceipt) | Trader | decision | no | no | Operations | execute cap | state-lock | recon flag |
| Ops→Compliance | `Observation`(positions) | Operations | fills | no | no | Compliance | recon | settlement math | CCO veto |

**Rejection becomes lineage:** every reject produces a new artifact (`ValidationArtifact.reject`,
`AuthorizationDecision.BLOCKED`, `CalibrationRecord`) whose `evidence_refs` include the rejected
artifact's hash. The verifier (`evaluate_intel`) traverses back through rejections — so a rejected
strategy's *reason* is permanently part of the record.

### 2.2 Daily trading / 2.3 Risk breach / 2.4 Model drift / 2.5 Data onboarding / 2.6 Compliance
Same ladder, different `Proposition.domain` + executor. Representative findings:
- **Risk breach:** Risk detection emits `Assessment`(exposure>X) → CRO `AuthorizationDecision`(halt,
  an `AuthorizationScope` action) → Execution `Action`(reduce) → Ops `Observation`. The breach path
  is **deterministic** end-to-end; no probability enters.
- **Model drift:** Model Risk emits `Observation`(drift) → triggers re-`ValidationArtifact` → may
  invalidate the existing `RiskBudget` epoch (see §3 Q3). This is the one place a *cognitive* signal
  (drift detection) legitimately *invalidates authority* — but only by producing a `ValidationArtifact`
  that governance consumes; the agent never mutates the budget itself.
- **Data onboarding:** Alt-Data `Observation` → Data `Evidence` → Compliance `Assessment`(legal) →
  Engineering `Action`(ingest) → Quality `Assessment`(quarantine?) → Signal Research `Belief`. The
  quarantine decision is a `CapabilityScope` action (`data.quarantine`), **not** an authorization.
- **Compliance/surveillance:** Trading `Action` → Surveillance `Evidence` → CCO `Assessment`(violation)
  → CCO `AuthorizationDecision`(block/report). The CCO's block is an `AuthorizationScope` veto — cross-
  cutting, zero operational capability.

**Result:** the ontology survives real organizational work across all six workflows. No new role-
specific object was required.

---

## 3. Resolving the five open 2D questions (→ explicit requirements)

These are now **ratified as requirements**, each with the rationale the firm forced.

### Q1 — Runtime contract (REQUIREMENT R1)
**Confirmed.** The minimum-sufficient runtime contract is:
```
Agent = Identity + EpistemicScope + EvidenceScope + ProposalScope
      + CapabilityScope + AuthorizationScope + GovernanceConstraints
      + derived CalibrationState
```
`RoleDefinition` is **excluded** (documentation). The four non-collapsible invariants are enforced by
construction: `CapabilityScope ≠ AuthorizationScope` (different profiles, independently granted);
epistemic standing ≠ authority (`CalibrationState` is derived, separate); calibration ≠ capability
(§6); role description ≠ runtime permission (RoleDefinition is docs-only). **R1 ratified.**

### Q2 — Assessment / Recommendation / Proposal (REQUIREMENT R2)
**Subkinds of a common `Artifact` base, not independent first-class types.** Rationale: the firm
needs the *distinction* (Assessment = deterministic state eval; Recommendation = advisory, no
authority; Proposal = an `AuthorizationRequest`), but all three share provenance/hash/lineage
machinery. Making them three disjoint classes would triple the lineage code for no semantic gain.
**Critical guard:** `Recommendation` carries `authority=NONE` and can **never** be cast to a `Proposal`
without an explicit `proposal_scope` agent re-emitting it. This prevents the "disguised authorization
directive" failure mode. **R2 ratified as subkinds + cast guard.**

### Q3 — Authority epochs (REQUIREMENT R3)
**Combination: event-supersession is primary; wall-clock TTL is a secondary safety net.** Rationale
from the firm's invalidation triggers:
- **Invalidates authority:** risk-budget change (new `RiskBudget` epoch supersedes), strategy shutdown
  (governance revokes `AuthorityGrant`), emergency halt (CRO `halt` action overrides grant
  state-scoped), compliance veto (CCO block), credential revocation (new `AgentCert`), model
  invalidation (`ValidationArtifact` status=invalid), deployment change (new `Mandate` epoch).
- **Property that must hold:** an agent can *never* operate under stale authority because every
  `AuthorizationRequest` carries the `epoch` of the grant/budget it cites, and the decision function
  (§4) **verifies the cited epoch is current** — exactly like `intel==HALLUCINATION` → BLOCKED. A
  non-current epoch is BLOCKED regardless of wall-clock. The TTL is only a backstop against a forgotten
  revocation. **R3 ratified as epoch-supersession + TTL backstop.**

### Q4 — Evidence completeness (REQUIREMENT R4 — the one genuine residual vulnerability)
Honest analysis: authenticity (cited evidence is real + unmodified, via hash chain) **does not**
prove completeness (all relevant evidence was cited). The six dimensions:
- **authenticity** — core protocol (hash chain + signature). **IMPLEMENTED-ready.**
- **provenance** — core protocol (who/when produced, signed). **IMPLEMENTED-ready.**
- **freshness** — core protocol (staleness window, exists in `evaluate_intel`). **IMPLEMENTED-ready.**
- **independence** — core protocol *where required* (G3 snapshot/method hash in `ValidationArtifact`).
- **completeness** — **MONITORING, not core protocol.** Cannot be guaranteed without a trusted oracle
  of "all relevant evidence exists"; attempting it in-protocol invites an unsolvable completeness
  oracle. Mitigated by `evidence_overlap` + independent validation, not solved.
- **coverage** — **MONITORING** (domain-specific: does the cited evidence span the required
  proposition template/regime?). Lives in validation thresholds, not the substrate.

**Minimum-sufficient decision:** L0 implements authenticity + provenance + freshness + independence
(where required). Completeness + coverage are **explicitly out of the core protocol**, handled by the
monitoring/validation layer. This is the honest boundary — we do **not** pretend lineage solves
completeness. **R4 ratified with completeness/coverage deferred to monitoring.**

### Q5 — Generalized AuthorizationDecision (REQUIREMENT R5)
**Confirmed generalized.** Domain-independent inputs: `identity, capability, mandate, policy, request,
current_state, risk_constraints, compliance_constraints`. Domain-specific *adapters* supply
`mandate`/`policy`/`risk_constraints` (finance=`Mandate`+`RiskBudget`; incident=incident-policy;
security=host-policy; research=protocol-approval). The **invariant** is invariant across domains:
`confidence, probability, model_score, recommendation, calibration_score, LLM_output` are **never**
authorization directives; they may enter *only* as inputs to deterministic policy evaluation where the
policy explicitly permits (e.g. a policy may say "require p>0.6" — but the *probability is data the
policy reads*, not a directive the model issues). **R5 ratified; quant math is evidence, never
authority (§7).**

---

## 4. Reconciling the firm's authority structure (no new primitive)

Testing APPROVE / AUTONOMOUS / RECOMMEND / ADVISORY against the key roles:

| Role | epistemic authority | org authority | operational cap | veto | escalation | execution |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| CIO | low (strategy) | **high** (approve) | none | — | top | none |
| CRO | narrow (risk) | **high** (halt/grant) | none | ✓ halt | ✓ | none |
| CCO | legal | **high** (veto) | none | ✓ | ✓ | none |
| Model Validation Lead | **high** (validity) | approve(reject strategy) | none | — | ✓ | none |
| Backtest Engineer | method | none | run_backtest | — | — | none |
| Portfolio Manager | alloc | propose(allocate) | none | — | ✓ | none |
| Execution Trader | none | none | **execute_order** | — | — | ✓ |
| Data Quality Analyst | data | quarantine(data) | none | (data) | — | none |
| Head of Operations | ops | approve(recon) | none | — | ✓ | none |

**Conclusion:** every role's authority fits the **existing** contract dimensions — `AuthorizationScope`
(approve/veto/halt/grant/override/escalate), `CapabilityScope` (execute/run/quarantine), and
`EpistemicScope` (what it may know/claim). **No orthogonal primitive is required.** "Advisory" and
"Recommend" map to `Recommendation` (authority=NONE); "Autonomous" maps to `AuthorizationScope` with
no human-in-loop; "Approve" maps to `AuthorizationScope` over a gate. The firm's adjectives are
*instances* of the three dimensions, not new dimensions. **Minimal formal system preserved.**

---

## 5. Disagreement as a real epistemic operation (no voting)

Concrete firm example: A=0.72, B=0.43, Validation=0.51, Risk=max-exposure (not a prob), CIO=auth-only.

Epistemic semantics (no math formula chosen yet — the architecture does not require one):
- **same proposition** — all three probabilities share one F1 `Proposition{predicate="strategy
  succeeds"}`.
- **different beliefs** — three `Belief` objects, each hash-chained to its own `Evidence`.
- **shared/correlated evidence** — `evidence_refs` intersection computed → `DisagreementRelation`(G9)
  marks A/B/Validation overlap (correlated failure risk) vs independent.
- **independent validation** — `ValidationArtifact` uses a *different* snapshot/method hash; its belief
  is weighted as independent.
- **disagreement** — `DisagreementRelation` records spread + overlap + per-agent `CalibrationState`.
- **calibration history** — each agent's `CalibrationProfile` (derived) feeds aggregation *weight*.
- **resolution/aggregation** — an `EpistemicState` (PROPOSED, G9-family) *contains* the beliefs +
  disagreement; it is **epistemic, not authoritative**.
- **final deterministic authorization** — a PM (with `proposal_scope`) reads the `EpistemicState`,
  emits a `Proposal`; Governance produces the `AuthorizationDecision` via `f(...)` (§3 R5). The
  aggregation never *becomes* authority — it is *cited evidence* in the proposal.

The fleet is **not a voting system** because the aggregate is an input to a human/PM decision, and the
decision itself is deterministic governance. The math for combining beliefs is a *domain adapter*,
not an architectural requirement.

---

## 6. Calibration tested honestly

Distinguish the firm's measurable qualities: prediction accuracy (researcher), decision quality (PM),
risk control (CRO), execution quality (trader), organizational outcome (firm). These are **different
metrics** — calibration measures *only epistemic performance* (prediction accuracy vs realized),
never authority.

| Influence of `CalibrationProfile` | Valid? | Why |
|-----------------------------------|:--:|-----|
| → Epistemic standing (weight in aggregation) | ✓ | derived, informational only |
| → Routing/weighting (which belief counts more) | ✓ | same as above |
| → Capability | ✗ | would let calibration grant execution — violates R1/R5 |
| → Authorization | ✗ | would let calibration become authority — violates thesis |
| → Research prioritization | ✓ | informational, not a permission |

**Invariant (R6):** `CalibrationProfile` is derived, stored separately from `CapabilityScope`/
`AuthorizationScope`, and is **never an input** to `AuthorizationDecision`. The 2D decomposition
enforces this structurally. Confirmed by the firm: a CRO with *zero* calibration (makes no
predictions) still holds halt authority; a researcher with excellent calibration holds *none*.

---

## 7. The mathematical boundary (where quant authority ends)

Classifying the expected quant mathematics:

| Concept | Class | Architectural rule |
|---------|-------|--------------------|
| probability, Bayesian updating, posterior, likelihood, entropy, expected value, variance/covariance/correlation, credible intervals, Brier, log loss, calibration curves | **PROBABILISTIC / EPISTEMIC** | → `Belief`/`Calibration` evidence; never a directive |
| hypothesis testing, Bayesian model comparison, time-series/regime/change-point, Monte Carlo, stochastic processes | **EVALUATIVE / EPISTEMIC** | → `Evidence`/`Assessment` (model comparison is an `Assessment`) |
| VaR, CVaR, Kelly, risk parity, mean-variance, factor models, Sharpe/Sortino/drawdown | **EVALUATIVE → feeds deterministic risk** | Kelly/VaR are *estimates* (epistemic); whether Kelly is an *allowed sizer* is governance (`RiskBudget`/policy) |
| transaction-cost, market-impact, portfolio constraints, optimization | **DETERMINISTIC / EXECUTION or GOVERNANCE** | constraint evaluation is deterministic; the *policy* permitting optimization is governance |
| backtest engine output | **EVIDENCE** | → `Evidence`, consumed by validation |

**The rule (R7), surviving the whole firm:**
> A model may **estimate** risk / Kelly / probability. **Governance determines** the permitted risk
> budget, whether Kelly is an allowed sizer, whether a probability estimate is *admissible evidence*
> for a policy, and whether a proposed order is *authorized*. Mathematical authority ends at the
> `Proposal`; governed decision-making begins at `AuthorizationRequest`. No quant concept crosses this
> line as a directive.

This is exactly `decide_trade`'s existing behavior generalized: the quant layer produces estimates;
governance consumes them as *data under policy*, never as commands.

---

## 8. Contradiction hunt (adversarial — honest classification)

For each vector, can an intelligent agent *accidentally gain authority*?

| Vector | Class | Verdict |
|--------|-------|---------|
| schema composition (composing artifacts to inherit capability) | **BLOCKING (prevented)** | `CapabilityScope` is keyed by `AgentCert`, not by artifact content; composing a `Belief`+`Proposal` yields no capability. |
| inherited capabilities (child agent inherits parent cap) | **DESIGN GAP → R1 closes it** | contract requires explicit `CapabilityScope` grant per agent; inheritance must be an explicit, logged grant, not implicit. State as L0 requirement. |
| stale authorization | **BLOCKING (prevented)** | R3 epoch check; non-current epoch BLOCKED. |
| recommendation fields | **BLOCKING (prevented)** | R2 cast guard: `Recommendation`(authority=NONE) cannot become `Proposal` without `proposal_scope` re-emit. |
| calibration scores | **BLOCKING (prevented)** | R6: calibration never an input to decision. |
| confidence fields | **BLOCKING (prevented)** | R5: confidence excluded from `f(...)`. |
| mutable risk budgets | **BLOCKING (prevented)** | budget mutable only by CRO (grantor); agent key cannot sign. |
| shared memory | **IMPLEMENTATION GAP** | memory sharing is an *implementation* concern; architecture requires `EvidenceScope` to gate what an agent may read — enforce at L2. |
| shared evidence | **MONITORING GAP** | shared evidence is *fine* (independence is workflow-scoped, not evidence-scoped); correlated-failure risk handled by G3 overlap detection (monitoring). |
| prompt injection | **OUT OF SCOPE (runtime)** | an LLM-injection concern; architecture mitigates by *not trusting* any epistemic output as authority — injection can produce a false `Belief` but never a `Capability`. Belongs to runtime sandboxing, not the contract. |
| lineage forgery | **BLOCKING (prevented)** | signatures + hash chain; forging requires the IdentityRoot key the agent lacks. |
| authority escalation | **BLOCKING (prevented)** | no artifact can add `AuthorizationScope`; grants are externally signed. |
| cross-role delegation | **DESIGN GAP → R1 closes** | delegation = a new `AuthorityGrant` by the grantor; an agent cannot self-delegate. Require explicit grant in L0. |
| recursive delegation | **DESIGN GAP → R1 closes** | each delegation is a distinct, revocable, epoch-bound grant; recursion depth is a policy param. |
| aggregation | **BLOCKING (prevented)** | aggregation produces `EpistemicState` (epistemic), never a `Decision`. |
| orchestration | **IMPLEMENTED-ready** | typed edges (G7) enforce "BELIEF_FLOW cannot carry AUTHORIZATION_FLOW payload" at the message layer. |
| tool access | **IMPLEMENTATION GAP** | tool access maps to `CapabilityScope`; enforce at gateway (exists via `AgentCert`). |
| execution adapters | **IMPLEMENTATION GAP** | adapters consume only `AuthorizationDecision`+`Action`; cannot be triggered by `Belief`. |

**Net:** the *authority-gaining* vectors are all **prevented by construction** (R1–R7). The genuine
remaining items are **DESIGN GAPs that R1/L0 explicitly close** (inheritance/delegation must be
explicit grants) and **IMPLEMENTATION GAPs** (memory gating, tool enforcement, adapter binding) —
none require *redesigning the authority boundary*, only implementing the already-decided contract.
Prompt injection is correctly **out of scope** for the contract.

---

## 9. True minimum architecture

### Already implemented (repo)
`AgentCert`(capabilities), `Mandate`+`RiskLayer.assess`, `decide_trade`(probability-excluding),
`VerificationLog`/`evaluate_intel`(backward traversal/ledger), `QuantEvidence`,
`ProbabilityEstimate`, `CalibrationRecord` (free functions).

### Already designed (docs)
EOM loop, F1 `Proposition`, F3 lineage, G0–G9 primitives, 5/6-scope contract, decision ladder,
external-authority model, aggregation≠authority boundary, calibration boundary.

### Required BEFORE L0 (`fleet/epistemic/`)
1. **R1** — the 5-profile runtime contract + explicit-grant rule (no implicit inheritance/delegation).
2. **R2** — `Artifact` base with `Assessment`/`Recommendation`/`Proposal` subkinds + cast guard.
3. **R3** — epoch-supersession + TTL on `AuthorityGrant`/`RiskBudget`.
4. **R4** — authenticity/provenance/freshness/independence in core; completeness/coverage to monitoring.
5. **R5** — generalized deterministic `AuthorizationDecision=f(...)`.
6. **R7** — quant-math classification rule (estimate vs govern).
These are *settled* by this synthesis; L0 must encode them.

### Can wait until AFTER L0
G2 `ValidationArtifact` + G3 independence, G6 `RiskBudget` promotion, G4 `CalibrationProfile` seal,
G5 `SettleRecord`, G9 `DisagreementRelation`, G7 typed edges, organizational orchestration mapping.
All *additive* — they hang off the L0 substrate and do not change the authority boundary.

### Domain-specific (belong in `fleet/fin` or adapters)
Kelly sizing, VaR/CVaR, Sharpe/Sortino, factor models, market-impact, backtest engine, regime
detection. These are *quant mathematics* — they produce `Belief`/`Evidence`/`Assessment`, never
authority. They must **not** leak into the epistemic substrate.

---

## 10. Final normative contract

1. Intelligence may produce Observations, Evidence, Beliefs, Assessments, Recommendations, Proposals.
2. Evidence must be traceable per the applicable lineage policy (authenticity/provenance/freshness;
   completeness/coverage are monitoring concerns).
3. Epistemic outputs **cannot** directly authorize actions.
4. Capability and authorization are **independent** dimensions, independently granted.
5. Authorization is **externally granted** (IdentityRoot/governance) and **cannot be self-granted**.
6. Risk limits / budgets are **governance-owned** and external to the risk model.
7. Calibration affects **epistemic standing only**, never authority.
8. Validation must be **independent** where the workflow requires it (distinct snapshot/method hash).
9. Authorization is **deterministic** w.r.t. governed state, policy, mandate, request, and current epoch.
10. Execution changes state **only through authorized transitions** (`AuthorizationDecision`+`Action`).
11. Verification **independently reconstructs** what happened (append-only ledger, backward traversal).
12. Outcomes feed Evaluation and Calibration **without retroactively altering** historical artifacts.
13. Domain-specific mathematics produces **evidence, not authority**.
14. The same architecture must represent **non-financial** organizations (incident/security/research).

**Challenge to the list:** clause 2's parenthetical is the one deliberate caveat — completeness is
*not* a core-protocol guarantee (R4), acknowledged honestly. Clause 9's "current epoch" addition
closes the stale-authority vector (R3). Otherwise the list is internally consistent and each clause
maps to a requirement R1–R7 or an existing invariant. **No clause requires modification.**

---

## 11. The gating question — answered with proof

> **"Can we now implement the epistemic substrate without having to redesign the authority boundary later?"**

**Answer: YES — and this is proven, not asserted.**

*Proof by two directions:*

**(A) The authority boundary is already enforced in the existing repository.** Three independent
mechanisms already implement the boundary the contract requires:
- `decide_trade(client_order_id, exchange_id, side, qty, limit_cents, venue, venue_live, intel)`
  returns AUTO/HUMAN/BLOCKED from `qty/side/venue/intel` and **takes no probability, confidence, or
  recommendation**. → clause 3, 5, 9 already hold for the financial path.
- `AgentCert.capabilities: List[str]` is the *sole* authority; it is signed by the `IdentityRoot`,
  not by the agent. An agent cannot add a capability to its own cert. → clauses 4, 5 hold.
- `RiskLayer.assess(proposal, account, market, mandate)` is a **pure deterministic** function over an
  external `Mandate`; the risk *model* estimates, the *mandate* (governance) bounds. → clauses 6, 13
  hold.

So the boundary is not something we are *hoping* to build — it is already operational. What is missing
is a **neutral, generalized home** (`fleet/epistemic/`) that names these mechanisms as a domain-
independent contract instead of burying them in `fleet/fin` + `exchange`.

**(B) The L0–L2 substrate only *names and generalizes* what already holds; it adds no new authority
mechanism that could later need redesign.** The requirements R1–R7 this synthesis settles are
*lifted directly* from the enforced behavior above (R3 epoch = the same BLOCK-on-invalid-input logic
as `intel==HALLUCINATION`; R5 = the same probability-excluding decision function; R6 = the same
separation of `CalibrationRecord` from `AgentCert`). The firm stress test (§2) exercised every
workflow through this ladder and required **zero new role-specific authority primitives** (§4) — the
three contract dimensions absorbed all 30+ roles. The only genuine residual (evidence completeness,
§3 Q4) is explicitly **deferred to monitoring**, so it cannot force a later boundary redesign — it
lives outside the substrate by decision.

**Therefore:** implementing L0 (`fleet/epistemic/` + core objects) and L1–L2 (the contract from R1–R5,
R7) encodes an authority boundary that is (i) already proven in the repo, (ii) sufficient for the
full quant firm, and (iii) domain-general. **No later redesign of the authority boundary is required.**
The smallest remaining *implementation* decisions (explicit-grant rule for inheritance/delegation,
memory/tool gating at the gateway) are enumerated in §8 as IMPLEMENTATION GAPs closed by L0 — they
refine *enforcement*, not the *boundary shape*.

---

*No code written. Not committed. Not pushed. `fleet/epistemic/` remains uncreated. This synthesis
ratifies R1–R7 and answers the gating question affirmatively with proof, clearing the path for L0–L2
implementation as the next (post-ratification) step.*
