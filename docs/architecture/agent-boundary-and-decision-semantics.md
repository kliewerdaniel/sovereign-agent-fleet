# Round 2D — Ratify the Agent Boundary and Decision Semantics

> **Status: DESIGN ONLY. No code. No schema. No migration. No commit.** Final architecture pass
> before `fleet/epistemic/` is justified. Resolves the *semantics* of the agent boundary and the
> decision pipeline so `Assessment / Recommendation / Proposal / Authorization / Capability` form a
> precise progression, not four loosely-related nouns. Grounded in the actual financial
> implementation (`decide_trade`, `RiskLayer.assess`, `Mandate`, `AgentCert.capabilities`) so the
> cognition→governance boundary is defined in artifact/authority terms, not philosophy.
>
> Constraints honored throughout: no runtime code, no behavior change, no commit. Every conclusion
> tagged **IMPLEMENTED / DESIGNED / PROPOSED / OPEN**. Ambiguities are surfaced, not silently resolved.

---

## 1. Executive conclusion

**The agent boundary survives and is now precise.** The six-profile decomposition
(`Identity / Role / EpistemicProfile / CapabilityProfile / AuthorizationProfile / GovernancePolicy`
+ derived `CalibrationProfile`) is the **minimum sufficient** model — no profile can be deleted, and
only one re-grouping is needed: `RoleDefinition` is *documentation* (not a runtime profile), and the
authority split from 2C (org-authorization vs operational-capability) is confirmed as the correct
form of `AuthorizationProfile` + `CapabilityProfile`.

**The decision semantic ladder is resolved as a strict progression** where each stage is a *different
artifact kind with a different producer and a different authority requirement*. The hard boundary —
**where cognition ends and governance begins** — is the transition `Proposal → AuthorizationRequest
→ AuthorizationDecision`, and it is enforced *mechanically*: `AuthorizationDecision` is a pure
deterministic function `f(identity, capability, mandate, policy, request, current_state,
risk_constraints, compliance_constraints)` that **cannot consume** confidence/probability/model_score/
recommendation as a directive. This is already true in `fleet/fin` (`decide_trade` takes no
probability); 2D generalizes it.

**Justification for implementation:** the quant firm is fully expressible through
> Agents produce knowledge and intent. Governance produces permission. Systems produce state
> transitions. Verification produces truth about what actually happened.

Therefore `fleet/epistemic/` is now justified as the neutral substrate — *after* the Q1–Q4
ratifications below.

---

## 2. Agent boundary (stress-test of the six-profile decomposition)

The required distinct dimensions and their classification:

| Dimension | Epistemic? | Org? | Ops? | Gov-owned? | Agent-mutable? | Other-mutable? | Proving artifact |
|-----------|-----------|------|------|-----------|----------------|---------------|-----------------|
| **What I can know** (EpistemicProfile) | yes | no | no | no | no (granted by policy) | GovernancePolicy | `CalibrationProfile` ref |
| **What I can infer** (BeliefScope ⊆ EpistemicProfile) | yes | no | no | no | no | GovernancePolicy | `Belief` record |
| **What I can recommend** (Recommendation ⊆ ProposalScope) | partial | no | no | no | no | GovernancePolicy | `Recommendation` artifact |
| **What I can propose** (ProposalScope) | no | no | no | no | no | GovernancePolicy | `Proposal`/`AuthorizationRequest` |
| **What I can approve** (AuthorizationProfile) | no | **yes** | no | **yes** | **NO** | grantor only | signed `AuthorityGrant` |
| **What I can execute** (CapabilityProfile) | no | no | **yes** | **yes** | **NO** | grantor only | `AgentCert.capabilities` |

**Finding:** the decomposition is minimum-sufficient. Two corrections to the 2C sketch:
- `RoleDefinition` is **NOT** a runtime profile — it is documentation (category D), already established in 2B-R §5. So the runtime contract has **five** profiles + one derived: `Identity`, `EpistemicProfile`, `CapabilityProfile`, `AuthorizationProfile`, `GovernancePolicy`, derived `CalibrationProfile`.
- `AuthorizationProfile` = **organizational authority** (approve/veto/halt/grant/override); `CapabilityProfile` = **operational capability** (execute). Confirmed orthogonal (2C §3).

When a profile expires/changes: it is **external governed state** — the agent does not mutate it; the grantor re-issues a cert or grant. The artifact proving current value is the **signed** `AgentCert` / `AuthorityGrant` / `RiskBudget`, each with `issued_at`/`expires_at`/`epoch`. (See §7.)

---

## 3. Decision semantic ladder

Each rung is a **distinct artifact kind**. Not every workflow uses every rung (incident response may
skip Prediction; research may skip Action). Semantic difference per rung:

| Rung | Producer | Probabilistic? | Authority required | Example |
|------|----------|----------------|--------------------|---------|
| **Observation** | sensor/feed/service | no | none | "quote = 50.1" |
| **Evidence** | any epistemic agent | no (derived) | none | "signal S fires" |
| **Belief** | epistemic agent | **yes** | none | "P(X rises)=0.72" |
| **Prediction** | epistemic agent | yes (future) | none | "X will occur by H" |
| **Assessment** | any agent (deterministic eval) | **no** | none | "exposure 14.2% > mandate 10%" |
| **Recommendation** | any agent | no (advisory) | **none** | "reduce exposure to 10%" |
| **Proposal** | agent w/ `proposal_scope` | no | none (it *requests*) | "sell 4,000 units X" |
| **Authorization Request** | agent w/ `proposal_scope` | no | none (it *asks*) | "authorize under mandate M" |
| **Authorization Decision** | **governance** | **no** | **governance cap** | "AUTHORIZED / BLOCKED / HUMAN_REVIEW" |
| **Action** | agent w/ executing capability | no | `capability` + `decision` | executed order |

**Where cognition ends and governance begins — defined precisely:**
> The boundary is the **Proposal → AuthorizationRequest → AuthorizationDecision** transition.
> Everything left of it is **produced by an epistemic/intent agent** and carries **no authority**.
> `AuthorizationDecision` is produced by **governance**, consumes the request + external mandated
> state, and emits a **permission**. Cognition *ends* at the moment an artifact becomes an
> `AuthorizationRequest` — from there it is a **deterministic governance input**, never an agent
> output that can self-authorize.

Grounded proof from the repo: `decide_trade(client_order_id, exchange_id, side, qty, limit_cents,
venue, venue_live, intel)` returns `AUTO/HUMAN/BLOCKED` purely from `qty/side/venue/intel`. It takes
**no** `p_yes`, no confidence, no recommendation. `intel=="HALLUCINATION"` → BLOCKED. This *is* the
cognition/governance boundary, already implemented; 2D generalizes it to the full ladder.

---

## 4. Recommendation vs Proposal — rigorous test (generalizes beyond finance)

The firm exposed: Assessment ("exceeds limit") ≠ Recommendation ("should reduce") ≠ Proposal
("reduce X from 14% to 10%") ≠ Authorization ("authorized under R-17").

**Cross-domain proof the semantics are fundamental, not financial:**

| Rung | Incident Response | Scientific Research |
|------|-------------------|---------------------|
| Assessment | DB latency > SLO | experiment contradicts hypothesis |
| Recommendation | investigate cluster | run replication |
| Proposal | restart cluster-3 | run protocol P |
| Authorization | approved under incident policy | research protocol approved |
| Action | restart cluster-3 | execute experiment |

Identical ladder, different `Proposition.domain`. **Confirms the abstraction is fundamental.** The
operational distinction:
- **Recommendation** = advisory artifact, `authority=NONE`; it *may be ignored*. It is a `Proposal`
  subkind with no `AuthorizationRequest` attached.
- **Proposal** = an `AuthorizationRequest` (it *asks* for permission). It *must* traverse governance.
The firm proves these are **not** the same object — collapsing them would let a recommendation
quietly become an authorization.

---

## 5. Capability vs Authorization — foundational invariant

Concrete test from the prompt:

| Role | Capability (technically doable) | Authorization (permitted now) |
|------|--------------------------------|-------------------------------|
| Execution Trader | `submit_order` | only within approved venue/size/asset/risk |
| CRO | `issue_halt` | may halt within firm-wide emergency policy |
| CCO | `issue_compliance_block` | may veto under compliance policy |
| Quant Researcher | `run_backtest` | **cannot** deploy capital |

**Foundational invariant (PROPOSED, grounded in existing `AgentCert`):**
> **Capability answers "can the system technically do this?"** (operational, `CapabilityProfile`).
> **Authorization answers "is this entity permitted to do this now?"** (governance,
> `AuthorizationProfile` over an external mandate).
> An agent **never** converts a capability into an authorization, nor an authorization into a
> capability. They are independently granted by governance.

This is already structurally true: `AgentCert.capabilities` (capability) is separate from the
`decide_trade` disposition (authorization); a researcher's cert simply omits `exchange.trade_execute`.

---

## 6. Authority is external to the agent (cannot self-grant)

**Invariant (PROPOSED):** an agent must not define, expand, or modify its own authority. Where each
lives:

| Artifact | Lives in | Owner | Mutable by agent? |
|----------|----------|-------|-------------------|
| capability grants | `AgentCert.capabilities` | IdentityRoot / grantor | **NO** |
| authorization grants | `AuthorityGrant` (signed) | grantor (CRO/CCO/Governance) | **NO** |
| risk budgets | `RiskBudget` (G6, signed) | CRO via governance | **NO** (grantor only) |
| mandates | `Mandate` (fleet/fin, exists) | governance | **NO** |
| governance policies | `GovernancePolicy` | governance | **NO** |
| role assignments | `RoleDefinition`/cert `role` | IdentityRoot | **NO** |
| validation status | `ValidationArtifact` (G2) | validator | **NO** (claimant cannot edit) |
| compliance status | `AuthorizationDecision`(block) | CCO | **NO** |

The state transition `Agent → "I now have permission to trade"` is **impossible by construction**:
permission derives from a *signed external grant* the agent does not possess the key to issue. The
key that signs `AgentCert`/`AuthorityGrant`/`RiskBudget` is the **IdentityRoot** (governance), not
the agent's own key.

---

## 7. Authority lifecycle (dynamic, not permanent)

The firm forces authority to be **time/state-dependent**, not a permanent agent property.

```
Strategy approved 09:00  → AuthorityGrant(epoch=E1, valid [09:00,∞))
Risk budget revoked 11:42 → RiskBudget superseded (epoch=E2)
Model drift 12:05         → ValidationArtifact(status=drift) → re-validation trigger
Compliance block 12:06    → AuthorizationDecision(BLOCKED) overrides grant
```

Represented as:
- **effective time / expiration** — `issued_at`/`expires_at` on every grant/cert/budget.
- **revocation / supersession** — new epoch with `supersedes=<prior>`; old epoch invalidated.
- **authority epochs** — a decision is valid only if its referenced grant/budget epoch is current.
- **emergency halt** — `issue_halt` (CRO) is an `AuthorizationProfile` action that *overrides* a
  grant without revoking the cert (ephemeral, state-scoped).
- **stale authorization** — a request referencing an expired/revoked grant is **BLOCKED** by the
  deterministic decision function (like `intel==HALLUCINATION` → BLOCKED).

**Proof against workflows:** the 2C lifecycle table (§4) already showed `RiskBudget` is CRO-only-
mutable, `CalibrationRecord`/`Outcome` immutable, `AuthorizationDecision` governed. Authority is a
**decision over externally-governed state at a point in time**, not a property of the agent. **Q:
does an epoch need a wall-clock TTL or only event-driven supersession? OPEN — see §15 Q3.**

---

## 8. Governance as a deterministic function

Generalized abstraction (grounded in `decide_trade` + `RiskLayer.assess` + `Mandate` +
`AgentCert.capabilities`):

```
AuthorizationDecision = f(
    identity,          # AgentCert (who)
    capability,         # cert.capabilities ⊇ requested action?
    mandate,            # external Mandate (allowed_assets/sides/max_position_pct)
    policy,             # GovernancePolicy (constraints)
    request,            # AuthorizationRequest (what, bounded by proposal_scope)
    current_state,      # account/position/exposure (observed, not believed)
    risk_constraints,   # RiskBudget (external, signed)
    compliance_constraints  # CCO block / surveillance flags
)
```

**What it MAY consume as evidence:** quantitative *Assessment* (e.g. `RiskLayer.assess` output) is
an input to the risk-constraint check — but only as a **deterministic evaluation of observed state**,
never as a probability directive. Example: `RiskLayer.assess(proposal, account, market, mandate)`
computes `position_pct_after` deterministically; `decide_trade` compares qty/side against tier
thresholds. The *number* flows through the *deterministic* path; the *probability* does not enter.

**What it MUST NEVER consume as a directive:**
`confidence, probability, model_score, LLM_instruction, recommendation, calibration`. These are
epistemic standing — they affect *aggregation weight*, never *authorization*. **This is the
mechanical instantiation of "cognition ends at the request."**

---

## 9. Epistemic aggregation boundary (aggregation ≠ authority)

Competing inputs: Researcher A 0.72, B 0.61, C 0.41, Validator "model unreliable", Risk "exposure
too high". The control plane constructs an **`EpistemicState`** (PROPOSED, G9-family):

```
EpistemicState {
    propositions, beliefs[], evidence[], evidence_overlap, independence,
    calibration[], disagreements[], validation_status, unresolved_uncertainty
}
```
This is **epistemic** — produced by aggregation over hash-linked beliefs, *consumes no authority*.
It becomes a `Recommendation`/`Proposal` only when an agent with `proposal_scope` *reads* the state
and emits intent. **The aggregation mechanism has no `AuthorizationProfile`** — it cannot produce a
`Decision`. Crucial invariant:
> **Aggregation produces epistemic state; governance produces authorization.** An `EpistemicState`
> is evidence an agent may cite in a Proposal; it is never itself a permission.

---

## 10. The generalized architecture (confirmed sequence)

```
Individual Beliefs
   → Epistemic Aggregation
   → Epistemic State
   → Assessment (deterministic eval)
   → Recommendation (advisory)
   → Proposal (AuthorizationRequest)
   → Governance (deterministic f)
   → Authorization Decision
```
**This sequence is correct.** The boundary belongs exactly at `Proposal → Governance`: left of it is
epistemic/intent (probabilistic allowed), right of it is deterministic governance (probabilistic
forbidden as directive). No rung should be removed; `Prediction`/`Hypothesis` are optional prefixes
for forecasting/research workflows. **No correction needed** — only the *enforcement* (typed edges,
G7) remains to be built.

---

## 11. Adversarial / gaming analysis (honest)

Assume a strategically-motivated agent trying to get its Proposal approved. What it can manipulate:
confidence, evidence selection/ordering, recommendation wording, probability/uncertainty estimates,
proposal size, claimed urgency, calibration reporting.

**What the architecture prevents (by construction):**
- **Self-granting authority** — impossible (§6). No belief/proposal can add a capability.
- **Probability-as-directive** — impossible (§8). `decision` excludes probability.
- **Silent authority expansion via calibration** — impossible (§12). Calibration is derived,
  separate from `CapabilityProfile`/`AuthorizationProfile`.
- **Forged lineage** — `Evidence`/`Belief` are hash-chained + signed; the verifier (`evaluate_intel`)
  counts *distinct* refs and flags hallucination. Replaying a tampered chain fails the hash.
- **Capability isolation** — cognition cannot import governance (import walls), so it cannot call the
  decision function directly.
- **Independent validation gaming** — `ValidationArtifact` requires a *different* data snapshot /
  method hash (§7 of 2C); same-source reproduction is detectable.

**What remains VULNERABLE (honest — not solved by this architecture):**
- **Evidence selection / framing** — an agent choosing *which* observations to surface (cherry-
  picking) is not prevented; lineage proves *what is cited is authentic*, not that *all relevant
  evidence was cited*. Mitigation: `evidence_overlap` + independent validation, but **no guaranteed
  completeness check exists**. (OPEN — see §15 Q4.)
- **Calibration gaming / misreporting** — an agent can *under-report* uncertainty to look more
  confident; calibration *measures* it over time but does not *prevent* it at emit time.
- **Proposal-size creep** — an agent can request within limits a size that, aggregated across many
  proposals, exceeds a budget; the *per-request* decision is sound, the *cross-request* sum is not
  automatically constrained unless `RiskBudget` enforces a running total (external, governance-owned —
  feasible but not yet built).
- **Recommendation wording** — pure persuasion; has no authority effect by construction (§4), so low
  risk, but can influence a *human* approver in HUMAN_REVIEW mode. The architecture governs the
  machine path; human-in-the-loop persuasion is out of scope.

**Conclusion:** the architecture structurally prevents *authority* gaming (the important class). It
does **not** solve *evidence-completeness* or *calibration-honesty* incentives — those need
monitoring + independent validation, which are present but not complete. Stated honestly, not papered
over.

---

## 12. Calibration boundary (formal invariant)

`CalibrationProfile` affects: epistemic weighting, aggregation, research prioritization, validation
thresholds. It **never** affects: capability grants, authorization grants, risk-budget ownership,
compliance authority, execution permission.

**Formal invariant (PROPOSED):**
> `CalibrationProfile` is **derived state** (computed from `CalibrationRecord`s), stored **separately**
> from `CapabilityProfile` and `AuthorizationProfile`, and is **never an input** to the
> `AuthorizationDecision` function. Calibration ⇒ epistemic influence; it ⇏ authority.

This is structurally guaranteed by the §2 decomposition: the three live in different profiles and the
decision function (§8) does not read the calibration profile. **No new mechanism needed — the split
enforces it.**

---

## 13. Final Agent Contract (minimum sufficient)

```
Agent = Identity
      + EpistemicScope        (what it may know / infer / believe)
      + EvidenceScope         (what evidence it may consume/produce + lineage reqs)
      + ProposalScope         (what actions it may request/recommend)
      + CapabilityScope       (what it can technically execute)
      + AuthorizationScope    (org authority: approve/veto/halt/grant/override)
      + GovernanceConstraints (external: mandates, policies, budgets, grants)
      + CalibrationState      (DERIVED, never stored on agent)
```
**Challenge result:** `RoleDefinition` is **removed** from the runtime contract (documentation only).
`BeliefScope` is folded into `EpistemicScope` (belief is a kind of epistemic output). `EvidenceScope`
is added explicitly because the firm showed lineage requirements are first-class (F3). Everything
else from the six-profile sketch is retained. This is the **minimum sufficient ontology** — no
profile can be deleted without losing a distinct, non-collapsible dimension.

---

## 14. Boundary Matrix

| Concept | Producer | Consumer | Mutable? | Probabilistic? | Gov-owned? | Can grant authority? |
|---------|----------|----------|----------|----------------|-----------|----------------------|
| Observation | sensor/feed | epistemic agents | no (append) | no | no | no |
| Evidence | epistemic agent | agents + governance(evidence) | no (append) | no | no | no |
| Belief | epistemic agent | agents + aggregation | no | **yes** | no | no |
| Prediction | epistemic agent | agents + calibration | no | yes | no | no |
| Assessment | any agent | agents + governance | no | **no** | no | no |
| Recommendation | any agent | agents (advisory) | no | no | no | **no** |
| Proposal | agent w/ proposal_scope | governance | no | no | no | **no** |
| Authorization Request | agent w/ proposal_scope | governance | no | no | no | no |
| Authorization Decision | **governance** | executor | no | no | **yes** | produces permission |
| Capability | **IdentityRoot/grantor** | gateway | **NO (agent)** | no | **yes** | no (is a capability) |
| Risk Budget | **CRO/governance** | decision fn | **NO (agent)** | no | **yes** | constrains, not grants |
| Calibration | **derived** | aggregation | no | derived | no | **no** |
| Outcome | market/system | calibration | no | no | no | no |

Matrix exposes **no contradiction**: the only "yes" in Gov-owned / grant-authority columns are
`Authorization Decision` (produces permission) and `Capability`/`Risk Budget` (gov-owned, agent-
immutable). Every epistemic artifact is agent-produced, non-probabilistic-at-governance, and
**cannot grant authority**. The boundary is clean.

---

## 15. Implementation dependency graph + ratification questions

**Dependency graph (unchanged L0–L6 from 2C, now ratified-for-build pending Q1–Q4):**
```
L0  fleet/epistemic/ (G0) + core objects
L1  Epistemic Contract — 5→6 scopes: split authority into AuthorizationScope + CapabilityScope
L2  Agent identity: Identity + EpistemicScope + EvidenceScope + ProposalScope
       + CapabilityScope + AuthorizationScope + GovernanceConstraints + derived CalibrationState
L3  { ValidationArtifact + IndependenceContract (G2,G3) }  ‖  { RiskBudget (G6) }
L4  Role Card decomposition → external GovernancePolicy (RoleDefinition = docs only)
L5  { CalibrationProfile seal (G4) } ‖ { SettlementRecord (G5) } ‖ { DisagreementRelation (G9) } ‖ { typed edges (G7) }
L6  Organizational orchestration (firm roles → contracts)
```

**Ratification questions (OPEN — do not implement until answered):**

- **Q1 (load-bearing).** Confirm the **six-profile runtime contract** (§2/§13) with `AuthorizationScope`
  (org authority) split from `CapabilityScope` (operational). *Recommended yes.*
- **Q2.** Confirm `Assessment` + `Recommendation` are **subkinds** (not first-class types). *Recommended
  subkinds* (2C Q2).
- **Q3.** Authority **epoch**: wall-clock TTL vs event-driven supersession only? *Open* — affects
  `AuthorityGrant`/`RiskBudget` schema.
- **Q4.** Evidence **completeness**: do we attempt a *completeness* check (all-relevant-evidence
  cited) or only *authenticity* (cited evidence is real, via hash chain)? *Recommended authenticity
  only at L0; completeness is a monitoring concern (§11 vulnerable items).* **This is the one real
  residual vulnerability** — worth your explicit call.
- **Q5.** Is the generalized `AuthorizationDecision = f(...)` (§8) the correct *interface* for all
  domains (incident/security/research), or does each domain need its own decision function shape?
  *Recommended one function, domain-specific `mandate`/`policy` params.*

---

## TAGGED SUMMARY

- **IMPLEMENTED:** `AgentCert.capabilities` (capability), `Mandate`+`RiskLayer.assess` (deterministic
  risk), `decide_trade` (probability-excluding decision), `VerificationLog`/`evaluate_intel`
  (backward traversal/ledger), `QuantEvidence`/`ProbabilityEstimate`/`CalibrationRecord`.
- **DESIGNED:** EOM loop, F1 `Proposition`, F3 lineage, G0–G9 primitives, the 6-scope/half-dozen-
  profile contract, the decision ladder semantics, the external-authority model, the
  aggregation≠authority boundary.
- **PROPOSED:** split `authority_scope`→`AuthorizationScope`+`CapabilityScope`; Assessment/Recommendation
  as subkinds; formal calibration-boundary invariant; generalized deterministic `AuthorizationDecision=f(...)`.
- **OPEN:** Q1–Q5 (Q4 = evidence completeness is the one genuine residual vulnerability).

*No code written. Not committed. The firm is fully expressible through "agents produce knowledge and
intent; governance produces permission; systems produce state transitions; verification produces
truth." `fleet/epistemic/` is now justified as the neutral substrate — pending Q1–Q5 ratification,
after which L0–L2 may be implemented and boundary-tested.*
