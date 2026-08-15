# D28 — Sovereign Cognitive Architecture: Layered Cognition over Deterministic Governance

> **Status:** PLANNING LOCKED — **AND IMPLEMENTED**. This document consolidates
> the architecture-review rounds that converged several independent research
> threads (Scientific Knowledge Compiler, Dynamic Persona MoE GraphRAG, Popper
> falsification, Page-Quality / Needs-Met evaluation, RLHF-style calibration)
> into a single specification that preserves the core Sovereign Agent Fleet
> property: **deterministic governance around probabilistic intelligence.**
>
> It introduces **no new authorization logic.** Every security gate already in
> the fleet (`gateway`, `policy`, `evaluate_intel`, `assess`,
> `required_trade_authorization`, `incident.required_authorization`, the
> verifier) is unchanged in its *decision logic*. The `fleet/cognition/` package
> (compiler, evaluation, persona-MoE, calibration) is **implemented** upstream
> of governance and is structurally incapable of becoming authority; its
> import boundary is enforced by a CI test.

---

## 1. Central thesis

The Sovereign Agent Fleet is the **constitutional layer** — it answers *"given a
proposed action, does this entity have the authority to perform it, and can we
later prove what happened?"* It is intentionally blind to whether the proposal
was clever, creative, or correct. The gateway, policy engine, environment,
cryptography, and verifier exist *because* intelligence is unreliable.

The six research threads are **not competing architectures** and must not be
collapsed into one "decision engine." They are different layers of a larger
system — all of them **intelligence / evidence-formation** concerns that live
upstream of the gateway. The gateway stays exactly as it is.

The framing is an **epistemic operating system**, not "a smarter agent":

| Component | Becomes |
|---|---|
| Sovereign Agent Fleet | Governance / constitutional layer (unchanged) |
| Scientific Knowledge Compiler | Knowledge formation (L0) |
| Dynamic Persona MoE GraphRAG | Multi-perspective reasoning (L1) |
| Popper / PQ / NM | Epistemic evaluation (L2) |
| RLHF-style calibration | Adaptive improvement, cognition-only (L3) |
| Human operators | Final escalation when uncertainty exceeds automated confidence |

---

## 2. The formal invariant (M0, stated as a checked fact)

> **The cognition layer may influence proposal generation and evidence
> presentation, but it cannot influence authorization outcomes except through
> deterministic policy-visible fields already defined by governance.**

Precise reading:

- *Run A = Run B* means: **removing cognition enrichment from an already-formed
  governance proposal does not change authorization.**
- It does **NOT** mean: removing cognition produces identical proposals.
  Cognition absolutely improves what gets proposed (richer evidence, competing
  hypotheses, documented falsification attempts).

This is the M0 property, made empirical rather than asserted.

---

## 3. Locked decisions (D-A … D-H)

| # | Decision | Exact meaning |
|---|---|---|
| **D-A** | Evaluation invisible to authorization | PQ/NM/Popper/uncertainty/persona analysis are **not arguments** to `evaluate_intel`, `assess`, `required_authorization`, `required_trade_authorization`, `verify_control_plane`, or any gate. They are properties of *reasoning*, not *authority*. |
| **D-B** | Evaluation only raises scrutiny | May push *up* the human-review path (existing ASSERTED→HUMAN route). Never emits BLOCKED, never auto-GRANTs, never lowers a threshold. |
| **D-C** | Personas are lenses, not voters | Persona agreement is never an authorization input. Real consensus requires distinct backends (`consensus.py` guarantee). Default: enrichment only. |
| **D-D** | Cognition outputs are logged artifacts, not verifiable facts | Verifier proves **binding + integrity** (authentic, signed-by-claimed-producer, citations-exist, hashes-match, bound-to-proposal, unmodified). It does **NOT** prove semantic correctness of the graph/claims/interpretation. **Citation resolution is verifiable; claim truth is not.** |
| **D-E** | Calibration signed + reviewable | `AlignmentEvent` to the ledger; `fleet/cognition` only; may touch retrieval/prompt/routing. |
| **D-F** | Provenance recorded, compiler not re-run | SKC lineage signed into artifact; verification never executes the compiler. |
| **D-G** | Persona *graph* is constitutional | Membership (esp. skeptic/falsifier/risk) fixed, governance-approved. Only *routing weights* tunable. Retiring an adversarial persona requires human sign-off. |
| **D-H** | Escalation is deterministic | Cognition emits **signals** (observed conditions), never instructions. The deterministic adapter maps signals → escalation. The model may *request*; it may not *decide*. |

### 3.1 Three ratified refinements (clarifying the above)

1. **`EvaluationArtifact` carries signals, not `requires_human_review`.** A field
   like `requires_human_review=True` would let the cognition layer issue an
   instruction to the authority layer — wrong semantic ownership. Cognition says
   *"I found these conditions"*; the governance adapter says *"given these
   conditions, policy requires escalation."* Mirrors the financial system:
   the Brain recommends; the RiskLayer decides the disposition.
2. **Citation resolution is verifiable; claim truth is not.** The verifier proves
   the artifact existed, was signed by the claimed producer, its source
   references existed, hashes match, it was bound to the proposal, and was
   unmodified. It does **not** prove the graph was semantically correct or the
   interpretation true. Hierarchy:
   - Cryptography proves: *"this artifact is authentic."*
   - Provenance proves: *"this artifact came from these sources."*
   - Evaluation proves: *"this artifact was challenged using these methods."*
   - Human/scientific judgment determines: *"is this actually correct?"*
   Popper is a documented *attempt at falsification*, not a truth oracle.
3. **Run A = Run B extends to both workloads.** The property is
   architecture-wide, not financial-only. The incident path
   (`incident.required_authorization`) is an equally pure function; the same
   assertion applies. This changes the claim from *"the financial system has
   this property"* to *"the architecture has this property."*

---

## 4. Structural guarantee: the package boundary (enforced, not aspirational)

```
fleet/cognition/   →  imports ONLY:  fleet.crypto (sign/verify/audit)
                                    + fleet.layers.handoff (emit signed Handoffs, read ledger)
        ▲
        │  cognition produces signed evidence; never sees a decision
        ▼
fleet/layers/  (gateway, policy, runtime.act_trade, fin/*, incident.*, verify)
        →  NEVER imported by cognition
```

**Enforcement:** `tests/test_boundary.py` fails the build if any
`fleet/cognition/**` module imports `gateway`, `policy`, `runtime.act_trade`,
`fin.domain.assess`, `incident.required_authorization`, or `verify`. This makes
D-A and D-G *structural facts* rather than aspirational docstrings. It mirrors
the informal discipline `brain.py` already obeys.

---

## 5. The layered pipeline

```
World
 |
 v
Observation Layer  -> SourcedEvidence
 |
 v
Scientific Knowledge Compiler (L0)  -> CompiledKnowledge + provenance/entity/contradiction graphs
 |
 v
Dynamic Persona MoE GraphRAG (L1)  -> competing interpretations, retrieval perspectives, hypotheses
 |
 v
Evaluation Layer (L2)  -> PQ + NM + Popper falsification + uncertainty
 |
 v
ProposalArtifact  ->  governance_surface  |  enrichment_envelope
                          |                      |
                          v                      v
                   Gateway / Policy       Evaluation / Cognition (ignored by gates)
                          |
                          v
                   Execution Environment (ExchangeSim / SimEnv)
                          |
                          v
                   Verifier  (proves binding+integrity of enrichment; Run A = Run B)
```

`SourcedEvidence` is an **observation** (*"this source exists, contains X"*).
`CompiledKnowledge` is a **transformation** (*"these entities appear related"*).
They deserve separate boundaries — SKC is interpretation, even when partially
deterministic.

The split inside `ProposalArtifact` is the key rule:

- **Governance surface** answers: *"what action is being requested?"*
- **Enrichment envelope** answers: *"why might this action make sense?"*

A dangerous architecture merges them (*"because the model thinks this is
correct, execute"*). This architecture keeps them separate: *"the model
generated a proposal + all its reasoning/disagreement/uncertainty; now
independently determine whether the requested action is authorized."* This is a
zero-trust cognition model.

---

## 6. Interface contracts (the only new surfaces)

### 6.1 `CompiledKnowledge` — new `Handoff` payload type

```
CompiledKnowledge {
  compile_id, compiler_cert_id,
  entities[], relationships[],
  claims: [{ claim, source_refs }],          # cite SourcedEvidence / other CompiledKnowledge
  contradictions: [{ claim_a, claim_b, evidence_refs }],
  provenance: [{ source_id, source_hash, retrieved_at }]
}
# forbidden (D8 discipline): no authorization/approval/capability/disposition tokens
```

Enters as *evidence*; cited by Analyst/Strategist; governance verifies the
**citation resolves** only.

### 6.2 `EvaluationArtifact` — signals, never flags

```
EvaluationArtifact {
  producer_cert_id,
  uncertainty: float,
  popper: { falsifiers[], passed: int, failed: int },
  evidence_quality: { authenticity, originality, expertise, freshness, spam },   # PQ
  needs_met: { intent, constraints_satisfied, gaps[] },                          # NM
  persona_analyses: [{ role, stance, claim_refs[] }],   # lenses, not votes
  contradiction_count: int
}
# NO requires_human_review field. Escalation computed deterministically (6.4).
```

Hashed + bound into `operator.final`; verifier checks binding + signature (D-D),
never content.

### 6.3 `ProposalArtifact` — the split made explicit

```
ProposalArtifact {
  governance_surface: TradeProposal | QualifiedIntel,   # ONLY thing gates read
  enrichment: EvaluationArtifact,                       # logged, ignored by gates
  enrichment_hash: str                                  # bound into audit record
}
```

### 6.4 Deterministic L4→L5 adapter — the only seam cognition touches flow

```python
def to_gateway_intent(proposal: ProposalArtifact) -> tuple[object, bool]:
    intel = proposal.governance_surface
    e = proposal.enrichment
    # D-B + D-H: escalation is a PURE FUNCTION of signals (policy owns the transition)
    force_asserted = (
        e.popper.failed > 0
        or e.uncertainty > UNCERTAINTY_THRESHOLD
        or e.contradiction_count > CONTRADICTION_THRESHOLD
    )
    return intel, force_asserted    # Operator routes ASSERTED -> human approval (unchanged path)
```

### 6.5 `AlignmentEvent` — signed calibration artifact (D-E/D-G)

```
AlignmentEvent {
  event_id, ts, observed_outcome, proposal_ref, evidence_used[],
  popper_failures[], pq_nm_ratings[],
  proposed_cognition_update: { reweight[], reprompt[], retire_persona? },
  human_approved: bool | None     # retire_persona requires True (D-G)
}
# kind: "calibration.*"; consumed ONLY by fleet/cognition; never by fleet/layers.
```

### 6.6 Verifier extension — Run A = Run B (both workloads)

```python
def verify_record(rec, operator_cert, human_cert, now):
    recomputed = required_trade_authorization(
        assess(proposal, account, market, mandate, ta.ts), consensus)
    assert recomputed.value == rec["disposition"]
    # M0 PROOF: strip enrichment, recompute, assert IDENTICAL outcome
    recomputed_stripped = required_trade_authorization(assess(...), consensus)
    assert recomputed_stripped.value == rec["disposition"]          # Run A == Run B
    # enrichment verified for BINDING + INTEGRITY only (present, unaltered, signed)
    assert _enrichment_bound_and_intact(rec)
```

The identical assertion applies to the incident path
(`incident.required_authorization`). The property is architecture-wide.

---

## 7. The M0 proof (formal)

```
Run A:  Proposal + RiskLayer/IncidentPolicy + Mandate/Evidence + EnvironmentState
        = AUTHORIZED

Run B:  Proposal + RiskLayer/IncidentPolicy + Mandate/Evidence + EnvironmentState
        + SKC + GraphRAG + Personas + Popper + PQ/NM
        = AUTHORIZED
                                                 ↑ must be IDENTICAL
```

The verifier executes both runs and asserts equality. The answer to *"how do
you know the model didn't talk itself into permission?"* becomes: *"we prove
authorization is unchanged when the reasoning layer is removed."*

---

## 8. Implementation roadmap (dependency order)

| Phase | Scope | Load-bearing? |
|---|---|---|
| **1** | `fleet/cognition/` package + import-boundary CI test | **Yes** — every later phase depends on it |
| **2** | `CompiledKnowledge` (signed, provenance-linked) | No (evidence producer, never gate-consumed) |
| **3** | `EvaluationArtifact` (Popper×1, PQ×1, NM×1; signals only) | Medium |
| **4** | Bind artifacts into audit; verifier Run A=Run B (both workloads) | **Yes** — proves the thesis |
| **5** | Dynamic Persona MoE GraphRAG | High temptation — keep lenses-only |
| **6** | Calibration loop (`AlignmentEvent`) | High temptation — D-G must hold |

Phases 1–4 are the foundation. Phases 5–6 only add richness and must not touch
the boundary.

---

## 9. Over-engineering warnings (carried from review)

- **Do not bundle L2 into one mandatory stage.** Evaluation is *optional
  enrichment* that only *adds flags*; making it a required pass tempts giving it
  blocking power (back to D-B violation).
- **Do not start with GraphRAG/MoE.** Embeddings + graph + multi-persona is the
  largest, riskiest, least-M0-relevant build. It adds richness, not correctness.
- **"Epistemic operating system" is a narrative, not a deliverable.** The actual
  artifact is a set of interfaces + logged wiring. Resist building a new runtime.
- **Calibration store is the long pole.** v1 = append-only signed log + human
  review queue, not an active optimizer. Active optimization is later; D-G says
  retiring a critic needs human sign-off.
