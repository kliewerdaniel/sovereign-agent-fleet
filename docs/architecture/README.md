# Architecture — The Sovereign Cognitive Control Plane

The system separates **cognition** (probabilistic, may be wrong or compromised) from
**governance** (deterministic, model-agnostic) from **execution** (stateful, untrusting)
from **verification** (independent, public-key-only). The cognitive backend is replaceable;
governance is authoritative.

```text
                 SOVEREIGN COGNITIVE CONTROL PLANE

                         ┌───────────────┐
                         │   Cognition   │  observe, reason, propose, disagree
                         │               │  D28 personas / retrieval / reasoning
                         │               │  exchange/quant: probability, Bayesian,
                         │               │    Kelly, regime, edge  → EVIDENCE only
                         └───────┬───────┘
                                 │  PROPOSAL / EVIDENCE
                         ┌───────▼───────┐
                         │   Governance  │  identity, policy, capability,
                         │               │  approval, consensus — pure functions
                         └───────┬───────┘
                                 │  AUTHORITY (signed authorization)
                         ┌───────▼───────┐
                         │    Domain     │  exchange/ venue + quant pipeline,
                         │               │  fleet/fin paper venue, incident SimEnv
                         └───────┬───────┘
                                 │  ACTION (state-locked execution)
                         ┌───────▼───────┐
                         │ Verification  │  crypto, ledger, attestation,
                         │               │  independent recomputation
                         └───────────────┘
```

**The quant layer is an evidence layer, not an authority.** Kelly, Bayesian updating,
regime detection, and edge estimation tell the system *what it believes* and *how strongly* —
they never decide what it is *permitted* to do. Risk/authorization is a deterministic
function in the governance layer; quant output is attached as advisory enrichment only.

## Key documents

- [`control-plane.md`](control-plane.md) — the layered flow, components, and trust model.
- [`exchange-vs-fin.md`](exchange-vs-fin.md) — `exchange/` (flagship) vs `fleet/fin/` (reference) relationship.
- [`epistemic-object-model.md`](epistemic-object-model.md) — **Round 2A design** (DESIGN ONLY, uncommitted): the shared Epistemic Object Model — Observation→Evidence→Belief→Proposal→Authorization→Action→Outcome→Calibration as a hash-linked, verifiable vocabulary; the next foundation for 2B/2C.
- [`epistemic-org-mapping.md`](epistemic-org-mapping.md) — **Round 2B design** (DESIGN ONLY, uncommitted): the quantitative-finance firm used as a stress-test of the EOM — role→object mapping, competing beliefs, calibration, strategy lifecycle, risk/authority boundary, agent graph, and the 7 missing primitives (G1–G7) the org exposes.
- [`epistemic-contract.md`](epistemic-contract.md) — **Round 2B-R design** (DESIGN ONLY, uncommitted): the Epistemic Contract — what an agent *knows / may claim / may propose / may authorize / may do* as five separate scopes. Resolves the coupled A2 (independence) + C5 (risk authority) + E (Role Card runtime) decisions into one coherent agent definition; the sequenced ratification questions Q1–Q8.
- [`quantitative-organization-architecture.md`](quantitative-organization-architecture.md) — **Round 2C design** (DESIGN ONLY, uncommitted): the 30+ role quant firm used as the *concrete operating environment* stress-testing the EOM + contract. Survivability verdict, the two forced gaps (org-authority vs operational-capability split; under-named `Assessment`/`Recommendation`), and the minimum-sufficient-ontology table.
- [`agent-boundary-and-decision-semantics.md`](agent-boundary-and-decision-semantics.md) — **Round 2D design** (DESIGN ONLY, uncommitted): the last-mile ratification. Agent boundary (5 runtime profiles + derived calibration), the decision semantic ladder, cognition→governance boundary defined in artifact/authority terms, capability≠authorization invariant, external-authority model, adversarial/gaming analysis, and the Boundary Matrix. `fleet/epistemic/` is now justified pending Q1–Q5 ratification.
- [`epistemic-architecture-synthesis.md`](epistemic-architecture-synthesis.md) — **Round 2E synthesis** (DESIGN ONLY, uncommitted): final pre-implementation pass. Reconciles all five docs against the firm's six workflows, converts the five open 2D ratifications into explicit requirements **R1–R7**, hunts contradictions honestly (authority-gaining vectors all prevented-by-construction; completeness deferred to monitoring), and **proves** `fleet/epistemic/` can be built without later redesigning the authority boundary.
- [`integrations.md`](integrations.md) — how `fleet/`, `exchange/`, `ui/`, `web/`, `demo_app.py` fit together.
- Deep reference: [`docs/assets/architecture.svg`](../assets/architecture.svg), [`research/03-architecture.md`](../research/03-architecture.md), [`research/D27-financial-workload-architecture-lock.md`](../research/D27-financial-workload-architecture-lock.md) (three-layer trust model), [`research/D28-sovereign-cognitive-architecture.md`](../research/D28-sovereign-cognitive-architecture.md).

## The meta-invariant (M0)

> No security invariant depends on model behavior. The model may lie, hallucinate, or
> deliberately propose the worst possible action — the authority boundary holds regardless.

This is not asserted; it is enforced by import walls and proven by a verifier that recomputes
the disposition with all cognition stripped (Run A = Run B).

## The flagship financial path (concrete)

```text
Market Data (feed adapter)
    ↓
Research / Quant agents  →  probability, edge, Kelly, regime, Bayesian  (EVIDENCE)
    ↓
Proposal  →  D16 evidence gate  →  Capability (gateway)  →  Risk matrix
    ↓
Authorization (AUTO / HUMAN / BLOCKED)  →  D17 human-signed approval if HUMAN
    ↓
Venue executes against the EXACT evaluated portfolio state (S1≠S2 defense)
    ↓
Signed ExecutionReceipt  →  Audit ledger  →  Independent verifier recomputes
```

Implemented in `exchange/` (venue + `quant/`) reusing `fleet` as a library, plus a
standalone verifier (`fleet/fin/verify.py` for the paper-trading workload).
