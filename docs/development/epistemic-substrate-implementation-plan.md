# Round 3 — Implementation Planning: Epistemic Substrate

> **Status: IMPLEMENTED + M0 PROVEN. Frozen substrate UNLOCKED.** Originally "PLANNING ONLY —
> no code, no commit, no push." That freeze has been lifted: the substrate shipped (Phases 0–6
> complete), and M0 domain-generality is now *empirically proven* by two independent external
> consumers — `exchange/` (finance) and `incident/` (incident-response) — both driving the same
> frozen `fleet.epistemic.decide()` with **zero substrate edits** (commit `10faa25`; 83-test
> substrate suite unchanged, full suite 496). R1–R7 remain **settled and NOT reopened**. The
> quantitative finance firm was the **acceptance-test organization**, not the product. The
> epistemic substrate remains domain-independent — now guaranteed by the cross-domain proof, not
> merely asserted.
>
> Method: **PROMOTE → GENERALIZE → CONNECT** (not REPLACE → DUPLICATE → REWRITE). Every claim below
> is grounded in a repository inspection (paths cited). Existing 480-test baseline must stay green.

---

## 1. Current repository state (inspected, not assumed)

**Neutral / domain-independent primitives that already exist:**
- `fleet.crypto.foundation`: `canonical_bytes(obj)` (sort_keys, exclude signature/storage — **the**
  canonical encoding), `sha256(b)`, `AgentCert` (the existing authority primitive), `IdentityRoot`
  (cert issuance/signing).
- `fleet/layers/incident.py`: `Authorization(str, Enum)` = `AUTO / HUMAN / BLOCKED` — **already
  domain-independent**, reused by exchange governance.
- `fleet/layers/verification.py`: `evaluate_intel(...)` (backward evidence-ref traversal,
  hallucination flag, staleness), `VERIFIED/ASSERTED/HALLUCINATION`. `fleet/api/schema.py`:
  `VerificationLog` / `VerificationRow` (append-only ledger). This **is** the audit/reconstruction
  layer — no new one.
- `fleet/fin/domain.py`: `Mandate` (external risk limits), `RiskLayer.assess(proposal, account,
  market, mandate)` (**pure deterministic**), `TradeProposal`, `Account`, `MarketData`.
- `fleet/fin/exchange_sim.py`: `ExecutionReceipt` (signed; `prev_state_hash → new_state_hash`,
  `operator_sig`) + `ExchangeSim.apply` — the existing **deterministic state-transition proof**.

**Domain (financial) producers of neutral concepts — these stay domain-specific, do NOT move:**
- `exchange/quant/probability.py`: `ProbabilityEstimate` (frozen, `state()`+`compute_hash()`),
  `MarketProbability`, `EdgeEstimate`. This **is** a `Belief` producer (R1: domain produces belief).
- `exchange/quant/evidence.py`: `QuantEvidence` (signed envelope bound to `proposal_hash`, *ignored by
  gates*, M0-preserving). This **is** an `Evidence` carrier pattern to mirror.
- `exchange/quant/calibration.py`: `CalibrationRecord` (frozen, `cal_hash`), `brier_score`,
  `rolling_brier`, `reliability_bins`. Domain calibration → becomes input to a neutral
  `CalibrationProfile` (R6), but the record stays here.
- `exchange/governance.py`: `decide_trade(client_order_id, exchange_id, side, qty, limit_cents,
  venue, venue_live, intel)` → `TradeDecision(Authorization, TradeRisk, ...)`. **Takes NO probability
  / confidence.** `approve_trade(human_cert, ..., capability="exchange.trade_execute")` cryptographically
  binds human approval. This **is** the deterministic `AuthorizationDecision` for finance.
- `exchange/venues/base.py`: `NormalizedOrder`. `exchange/execution`: performs authorized transitions.

**Provenance convention (uniform, reuse — do NOT invent a second):**
`frozen dataclass → state() dict (excludes signature) → compute_hash() = sha256(canonical_bytes(state()))`.
Used by `ProbabilityEstimate`, `MarketProbability`, `EdgeEstimate`, `QuantEvidence`, `Mandate`,
`ExecutionReceipt`, `CalibrationRecord`. **`fleet/epistemic/` must adopt this exact convention.**

---

## 2. Existing primitives to reuse (do not recreate)

| Need | Reuse | Source |
|------|-------|--------|
| Canonical encoding + hashing | `canonical_bytes`, `sha256` | `fleet.crypto.foundation` |
| Identity + authority | `AgentCert`, `IdentityRoot` | `fleet.crypto.foundation` |
| Authorization verdict enum | `Authorization(AUTO/HUMAN/BLOCKED)` | `fleet/layers/incident.py` |
| Evidence-gate / backward traversal | `evaluate_intel`, `VerificationLog` | `fleet/layers/verification.py`, `fleet/api/schema.py` |
| Deterministic risk | `RiskLayer.assess`, `Mandate` | `fleet/fin/domain.py` |
| State-transition proof | `ExecutionReceipt` | `fleet/fin/exchange_sim.py` |
| Proposal/disposition | `decide_trade` → `TradeDecision` | `exchange/governance.py` |
| Financial belief/evidence/calibration | `ProbabilityEstimate`/`QuantEvidence`/`CalibrationRecord` | `exchange/quant/*` |
| Provenance shape | `state()`+`compute_hash()` | every frozen record above |

---

## 3. Target dependency graph (intended direction — never reversed)

```
DATA (observations/feeds)
   ↓
EVIDENCE              (exchange/quant, fleet/fin producers)
   ↓
COGNITION / QUANT     (exchange/quant produces Belief/Assessment/Recommendation)
   ↓
PROPOSAL              (PM/agent with proposal_scope)
   ↓
AUTHORIZATION REQUEST
   ↓
GOVERNANCE            (exchange/governance decide_trade — deterministic, NO prob)
   ↓
DETERMINISTIC DECISION (Authorization enum)
   ↓
EXECUTION             (exchange/execution, fleet/fin ExchangeSim)
   ↓
STATE                 (ExecutionReceipt)
   ↓
VERIFICATION          (fleet/layers/verification)
   ↓
OUTCOME / CALIBRATION (exchange/quant CalibrationRecord)
```

`fleet/epistemic/` sits **under COGNITION→PROPOSAL**: it defines the *neutral* object shapes
(`Belief`, `Evidence` base, `Artifact` ladder, `Proposition`, `Uncertainty`, contract dataclasses).
It depends only on `fleet.crypto.foundation` (canonical/sha256/AgentCert). It imports **nothing**
from `exchange`, `fleet/fin`, `governance`, `execution`, any LLM, any orchestrator, or any quant math.

---

## 4. L0 implementation plan — `fleet/epistemic/`

**Minimum coherent substrate. Small, neutral, dependency-clean.**

Proposed files (only what L0 needs; no ontology explosion):
- `fleet/epistemic/__init__.py` — exports.
- `fleet/epistemic/identity.py` — re-export `AgentCert` from `fleet.crypto.foundation` (do NOT
  redefine). Add a thin `AgentIdentity` alias only if a neutral name is desired; otherwise import.
- `fleet/epistemic/proposition.py` — `Proposition` (F1 structured: `domain`, `subject`,
  `predicate`, `params`) — frozen, hashed. (Promotes the 2A F1 design; this is the linchpin type.)
- `fleet/epistemic/artifact.py` — `Artifact` frozen base with `state()`+`compute_hash()` (reusing
  `canonical_bytes`/`sha256`), `evidence_refs: tuple[str,...]`, `producer_cert_id`, `ts`. All ladder
  types subclass it.
- `fleet/epistemic/uncertainty.py` — `Uncertainty` typed union: `Point`, `Interval`, `Distribution`
  (minimal: mean/std or samples), `Calibrated`, `Entropy`, `Risk`. **L0 ships only `Point`,
  `Interval`, `Entropy`**; `Distribution`/`Calibrated`/`Risk` are protocol extension points (R6:
  domain implements math, substrate only types the result). Epistemic vs aleatoric tag on each.
- `fleet/epistemic/evidence.py` — `Evidence(Artifact)` base (immutable, hashed, signed-envelope
  shape mirrored from `QuantEvidence` but content-neutral).
- `fleet/epistemic/belief.py` — `Belief(Artifact)` (probabilistic: `proposition`, `p_yes` or
  distribution ref, `uncertainty`, `model_id`, `method`). This is the neutral shape
  `ProbabilityEstimate` already instantiates; `exchange/quant` continues to *produce* financial beliefs.
- `fleet/epistemic/assessment.py` — `Assessment(Artifact)` (deterministic state-vs-policy eval;
  `kind`, `observed`, `threshold`, `verdict`). R2: distinct from Belief.
- `fleet/epistemic/recommendation.py` — `Recommendation(Artifact)` with **`authority="NONE"` frozen
  field** and a type system that makes implicit `Proposal` coercion impossible (R2 cast guard:
  constructing a `Proposal` requires an explicit `proposal_scope` proof, not a cast).
- `fleet/epistemic/proposal.py` — `Proposal(Artifact)` / `AuthorizationRequest` (carries
  `action_descriptor`, `target`, `requested_scope`); explicitly **no** `confidence`/`probability`/
  `model_score`/`calibration`/`recommendation` fields that could act as a directive.
- `fleet/epistemic/lineage.py` — `lineage_refs` helpers + a `verify_lineage(artifact, known: set[str])`
  that reuses `evaluate_intel`'s distinct-ref counting (R4: authenticity/provenance/freshness in core;
  completeness/coverage are monitoring — explicit comment).
- `fleet/epistemic/hashing.py` — re-export `canonical_bytes`, `sha256` (single import surface).

L0 explicitly does **NOT** contain: `AuthorizationDecision` (governance owns it — `Authorization`
enum + `decide_trade`), `Action`/`ExecutionReceipt` (fleet/fin), `CalibrationProfile` seal (L5),
`ValidationArtifact`/`RiskBudget`/`DisagreementRelation` (L3). Those hang off L0 later.

---

## 5. L1 contract implementation plan (R1)

Do **not** build one giant `AgentContract` class. Map to repo realities:
- `Identity` → **reuse `AgentCert`** (already has `agent_id`, `pubkey_pem`, `role`, `capabilities`,
  `issued_at`, `expires_at`, `cert_seq`, `root_sig`). No new identity type.
- `EpistemicScope` / `EvidenceScope` / `ProposalScope` → **new constrained value objects** (frozen
  dataclasses / `TypedDict` + validators), *referenced* by the agent, not embedded into `AgentCert`
  (keep cert minimal). Stored as `GovernancePolicy` (external, signed) — see L2.
- `CapabilityScope` → **alias/derived view of `AgentCert.capabilities`** (the existing list of
  capability strings). This is the *operational* dimension.
- `AuthorizationScope` → **new** constrained value object representing org authority
  (approve/veto/halt/grant/override/escalate) — **independent** from `capabilities`. Stored as an
  external signed `AuthorityGrant` (R3).
- `GovernanceConstraints` → **reference** to external `Mandate`/`RiskBudget`/policy (already exist in
  `fleet/fin` for finance; neutral shape defined in L0/L1, domain fills it).
- `CalibrationState` → **derived**, never stored on the agent (R6). Computed from `CalibrationRecord`s
  via the existing `brier_score`/`rolling_brier`; surfaced as a separate `CalibrationProfile` later (L5).

**Structural guarantee of R1:** `CapabilityScope` and `AuthorizationScope` are **separate types with
no shared mutation path** — capability comes from `AgentCert.capabilities` (signed by IdentityRoot);
authorization comes from an `AuthorityGrant` (signed by grantor). No code path combines them into one
enum/boolean. Any "add capability" must go through IdentityRoot; any "add authority" through the
grantor. **An implementation that merges them is wrong** — L2 tests enforce this.

---

## 6. L2 boundary enforcement + tests (the executable architecture)

Tests live in `fleet/epistemic/tests/` (new) and reuse the existing `test_boundary_quant.py` pattern
(AST import-wall scan). At minimum:

- **Import boundary:** `fleet/epistemic` cannot import `exchange`, `fleet/fin`, `governance`,
  `execution`, any LLM, any orchestrator. AST scan test (mirror `test_boundary_quant.py`).
- **Authority boundary:** a `Belief` cannot authorize; a `Recommendation` cannot authorize; a
  `Proposal` cannot authorize; `CalibrationState` cannot grant authority; `confidence`/`probability`
  fields cannot appear as authorization directives. Unit tests asserting `AuthorizationDecision` is
  produced only by governance, never constructible from a Belief/Recommendation.
- **Capability boundary:** `CapabilityScope` ≠ `AuthorizationScope` (type-level + test that adding a
  capability does not add authority and vice versa).
- **Stale authority (R3):** epoch test — agent holds epoch 10; epoch 11 active; epoch-10
  `AuthorizationRequest` → deterministic BLOCK. Mirror `intel==HALLUCINATION`→BLOCKED.
- **Risk boundary:** agent cannot modify its own `RiskBudget`/`Mandate` (test that mutation requires
  the grantor key, which the agent lacks).
- **Lineage (R4):** tampered `evidence_refs` → `verify_lineage` fails; missing required lineage →
  policy-degraded/rejected state. Completeness/coverage are **not** asserted at L0 (explicitly
  omitted, monitoring concern).
- **Independence (R3/G3):** a `ValidationArtifact` (L3) cannot inherit the claimant's snapshot/method
  hash where independence is required — test that shared-hash validation is flagged.
- **Determinism:** same `(identity, capability, mandate, policy, request, state, constraints)` → same
  `AuthorizationDecision` (deterministic decision fn test).
- **Quant isolation:** probabilistic modules (`exchange/quant`) cannot import/instantiate the
  authorization function — enforced by the import-wall + a test that `decide_trade` signature has no
  `probability`/`confidence` param (regression guard: reject `decide_trade(..., confidence)`).

These tests are the **executable expression of R1–R7**.

---

## 7. Migration / adapters (PROMOTE, do not move domain logic)

| Existing object | EOM concept | Action | Target | Compatibility | Tests |
|-----------------|------------|--------|--------|---------------|-------|
| `ProbabilityEstimate` | `Belief` | **KEEP (domain producer)**; optionally add `as_epistemic_belief()` adapter returning `fleet.epistemic.belief.Belief` | `exchange/quant` | must stay importable by `exchange/api.py` | existing `test_quant_q1.py` (green) |
| `QuantEvidence` | `Evidence` carrier | **KEEP**; adapter to `fleet.epistemic.evidence.Evidence` | `exchange/quant` | signed-envelope behavior unchanged (M0) | `test_quant_q6.py` |
| `CalibrationRecord` | calibration record | **KEEP**; feeds `CalibrationProfile` (L5) | `exchange/quant` | hash shape frozen | `test_quant_q1.py` |
| `QuantDecision` | (orchestration output) | **KEEP/ADAPTER** | `exchange/quant` | unchanged | `test_quant_q6.py` |
| `ProposalArtifact` (`fleet/cognition`) | `Proposal` | **ADAPTER** → `fleet.epistemic.proposal.Proposal` | `fleet/cognition` | governance_surface preserved | existing cognition tests |
| `ExecutionReceipt` | `Action` proof | **KEEP** (already neutral enough) | `fleet/fin` | signed state-transition | `fleet/fin` tests |
| `Mandate` | `GovernanceConstraints` | **KEEP**; neutral `GovernanceConstraints` references it | `fleet/fin` | unchanged | `fleet/fin` tests |
| `RiskLayer` | deterministic risk | **KEEP** | `fleet/fin` | unchanged | `fleet/fin` tests |
| `AgentCert` | `Identity`+`CapabilityScope` | **REUSE** (no copy) | `fleet.crypto.foundation` | unchanged | `foundation` tests |
| `VerificationLog`/`Row` | audit ledger | **REUSE** | `fleet/layers` | unchanged | verification tests |
| `Authorization` enum | verdict | **REUSE** | `fleet/layers/incident.py` | unchanged | incident tests |

**Rule:** domain objects remain domain-specific producers/consumers of the neutral substrate. No
quant math moves into `fleet/epistemic/`. The substrate defines *shapes*; `exchange/quant` and
`fleet/fin` *fill* them.

---

## 8. Test plan (summary)
- New: `fleet/epistemic/tests/test_boundary_epistemic.py` (import wall), `test_artifact_ladder.py`
  (Belief≠Assessment≠Recommendation≠Proposal; cast-guard), `test_contract_r1.py` (capability≠
  authorization), `test_lineage_r4.py`, `test_epoch_r3.py`, `test_determinism.py`.
- Regression: full suite must stay **480→ green** (pre-D31 baseline). Run with the isolated
  `.deploy-venv` (no PYTHONPATH leak): `env -i PATH="$PWD/.deploy-venv/bin:/usr/bin:/bin" HOME="$HOME"
  "$PWD/.deploy-venv/bin/python" -m pytest -q`.
- Locked-layer gate: `git status --porcelain | grep -E "fleet/fin/|exchange/governance.py"` → empty.

---

## 9. Minimal quantitative vertical slice (proves the thesis, tiny)
A deliberately small finance path through the new substrate:
```
Alt-data Observation → exchange/quant Evidence → ProbabilityEstimate (Belief)
   → PM Recommendation (authority=NONE) → PM Proposal (action_descriptor)
   → AuthorizationRequest → existing decide_trade (deterministic, NO prob)
   → ExecutionReceipt (state proof) → CalibrationRecord → CalibrationProfile(update)
```
This reuses *existing* `decide_trade`/`ExecutionReceipt`/`CalibrationRecord` — the slice adds only
neutral `Belief`/`Recommendation`/`Proposal` shapes + the contract, and proves: **"probabilistic
intelligence participates in a serious workflow without becoming the authority."** No trading system
is built.

---

## 10. Deferred by Design (explicitly NOT in first implementation)
- sophisticated belief aggregation / mathematical combination (G9 `EpistemicState` math)
- advanced Bayesian inference engine
- portfolio optimizer / quant engine
- online learning / regime detection
- automatic calibration weighting
- evidence completeness/coverage engine (R4 → monitoring)
- full organization simulator / multi-agent trading desk
- LLM-specific orchestration
- domain-specific risk math (Kelly, VaR, CVaR) inside `fleet/epistemic`
- `ValidationArtifact` / `IndependenceContract` (G2/G3) — L3
- `RiskBudget` promotion (G6) — L3
- `CalibrationProfile` seal (G4) — L5
- `SettleRecord` (G5) — L5
- typed edge labels (G7) — L5
All additive, none change the authority boundary.

---

## 11. Risks
- **R-risk-1 (enforcement, not boundary):** inheritance/delegation of capability must be *explicit
  grants*, not implicit — close in L1/L2 (R1).
- **R-risk-2 (enforcement):** memory/tool gating at gateway maps to `CapabilityScope` — implement at
  L2; out-of-scope for contract shape.
- **R-risk-3 (regression):** accidentally widening `decide_trade` signature — prevented by the
  determinism/regression test (§6).
- **R-risk-4 (import creep):** a neutral type subtly importing `exchange` — prevented by the AST
  import-wall test (§6).

---

## 12. Acceptance criteria
> **M0 PROVEN (post-freeze):** Two independent external consumers (`exchange/` finance,
> `incident/` incident-response) drive the identical frozen `fleet.epistemic.decide()` with zero
> substrate edits; the substrate returns identical verdicts under equal policy and flips
> `AUTO→HUMAN` together on policy change, regardless of domain. Frozen substrate suite (83 tests)
> unchanged; full suite 496. The freeze is lifted — see §1 banner and §16.
1. `fleet/epistemic/` imports **only** `fleet.crypto.foundation` (+ stdlib). AST test green.
2. Full repo suite green (no regression from 480 baseline); locked layers byte-untouched.
3. L0 ladder types exist; `Recommendation` cannot become `Proposal` without explicit `proposal_scope`.
4. R1–R7 each have ≥1 failing-if-violated test.
5. Vertical slice executes end-to-end reusing existing governance/execution; probabilistic output
   never reaches `decide_trade` as a directive.
6. The 30+ firm roles are representable via profiles/scopes/governance (no role-specific authority
   primitive) — demonstrated by a role→contract table in tests.

---

## 13. Proposed implementation order (derived from repo, not the prompt's example)
- **Phase 0 — probe:** add `fleet/epistemic/` package + `hashing.py` re-export; confirm import wall
  test. *(No behavior change.)*
- **Phase 1 — neutral primitives (L0):** `proposition.py`, `artifact.py`, `uncertainty.py`,
  `evidence.py`, `belief.py`, `assessment.py`, `recommendation.py`, `proposal.py`, `lineage.py`.
- **Phase 2 — contract (L1):** `scope.py` (EpistemicScope/EvidenceScope/ProposalScope/CapabilityScope/
  AuthorizationScope as constrained value objects), `AuthorityGrant` (signed, epoch-bound),
  `agent_contract.py` (composition of references, not a god-object).
- **Phase 3 — boundary tests (L2):** the §6 suite; gate on full regression + locked-layer check.
- **Phase 4 — adapters:** `as_epistemic_*` adapters for `ProbabilityEstimate`/`QuantEvidence`/
  `CalibrationRecord`/`ProposalArtifact`; zero changes to their source behavior.
- **Phase 5 — financial vertical slice:** wire the §9 path; reuse `decide_trade`/`ExecutionReceipt`.
- **Phase 6 — integration verification:** full suite + locked-layer gate + import-wall + determinism.

---

## 14. Files likely added
`fleet/epistemic/__init__.py`, `hashing.py`, `proposition.py`, `artifact.py`, `uncertainty.py`,
`evidence.py`, `belief.py`, `assessment.py`, `recommendation.py`, `proposal.py`, `lineage.py`,
`scope.py`, `authority_grant.py`, `agent_contract.py`, `tests/test_boundary_epistemic.py`,
`tests/test_artifact_ladder.py`, `tests/test_contract_r1.py`, `tests/test_lineage_r4.py`,
`tests/test_epoch_r3.py`, `tests/test_determinism.py`.

## 15. Files likely modified
None at L0/L1/L2 core. Adapters in Phase 4 are *additive* (new adapter modules or small
`as_epistemic_*` methods). `exchange/api.py` gains a thin advisory path only if the slice needs it
(Phase 5), mirroring the already-shipped Q6-live advisory pattern (kept isolated from gates).

## 16. Files that MUST NOT be modified by the substrate itself (now: additive consumers sanctioned)
Historically gated "locked" during the freeze. The substrate freeze is **lifted (M0 proven)**;
the following remain *out of scope for substrate edits* — per-domain adapters are additive, not
in-place modifications: `fleet/fin/` (entire — `Mandate`, `RiskLayer`, `TradeProposal`,
`ExecutionReceipt`, `ExchangeSim`), `exchange/governance.py` (`decide_trade` signature),
`fleet/crypto/foundation.py` (`AgentCert`, `canonical_bytes`, `sha256`), `fleet/layers/incident.py`
(`Authorization`), `fleet/layers/verification.py` (`evaluate_intel`). Verified untouched via the
`git status` grep gate *during the freeze*. The M0 proof adds **new** adapter packages
(`exchange/epistemic_adapter/`, `incident/epistemic_adapter/`) without touching the substrate.

---

## 17. Final gate — answers

1. **Can `fleet/epistemic` remain domain-neutral?** YES — Phase 0 import-wall test + only
   `fleet.crypto.foundation` dependency.
2. **Can existing financial governance remain authoritative?** YES — `decide_trade`/`RiskLayer`/
   `Mandate`/`ExecutionReceipt` are untouched and reused.
3. **Can quant math remain evidence-producing not authority-producing?** YES — `exchange/quant`
   produces `Belief`/`Evidence`; never imports authorization.
4. **Can capabilities and authorization remain orthogonal?** YES — separate types, separate signers
   (R1, L1, enforced by test).
5. **Can stale authority be deterministically rejected?** YES — R3 epoch check (L2 test).
6. **Can lineage be verified without trusting agent prose?** YES — hash chain + `evaluate_intel`.
7. **Can independent validation be represented without a special "validator agent" primitive?** YES —
   `ValidationArtifact` is a G2 artifact, not a role; independence is snapshot/method hashes.
8. **Can the same contract represent 30+ firm roles?** YES — roles = profiles/scopes/governance, not
   primitives (§4 firm table).
9. **Can it later support incident/security/research without redesign?** YES — `Authorization` enum,
   `Proposition.domain`, and the ladder are already domain-generic.
10. **Can all this be introduced without breaking current governance?** YES — additive L0/L1/L2,
    locked layers untouched, 480 baseline preserved.

**All YES → IMPLEMENTATION READY.**

**Smallest first implementation increment:** Phase 0 + Phase 1 (neutral `fleet/epistemic/` primitives
reusing `fleet.crypto.foundation`), then Phase 2 contract, then Phase 3 boundary tests gating on the
full 480-test regression + locked-layer check. No domain objects moved; no governance signature
changed.

*No code written. Not committed. Not pushed. This is the implementation plan immediately preceding
L0 construction.*
