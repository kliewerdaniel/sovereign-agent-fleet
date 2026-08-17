# Cognition — D28, the conceptual bridge

`fleet/cognition/` is **the bridge** between the deterministic governance substrate and the
quantitative / exchange system. It is where probabilistic reasoning lives — and where the
rule "the model is not the authority" is made structural.

## The thesis

> The control plane is the **constitutional layer**: it answers *"given a proposed action, does
> this entity have the authority to perform it, and can we later prove what happened?"* It is
> intentionally blind to whether the proposal was clever, creative, or correct.

The cognitive layer — whether a general brain (`fleet/cognition/`: persona-MoE, retrieval,
Popper falsification, PQ/NM evaluation, calibration) or the quantitative layer
(`exchange/quant/`: probability, Bayesian updating, Kelly, regime detection, edge estimation)
— is **upstream of governance** and is structurally incapable of becoming authority.

```text
  Cognition (D28 + exchange/quant)          Governance (fleet/layers)        Environment
  ──────────────────────────────           ─────────────────────────        ────────────
  observe / reason / propose               authenticate / authorize         validate / execute
  enrich with evidence + uncertainty       (pure functions, no model)       (state-locked)
  PERSONAS = lenses, not votes             CONSENSUS = escalation-only       VERIFIER = recompute
  EVALUATION = signals, not flags
            │ PROPOSAL + EVIDENCE                    │ AUTHORIZATION                   │ RECEIPT
```

## The formal invariant (M0)

> The cognition layer may influence *what is proposed* and *how evidence is presented*, but it
> cannot influence *authorization outcomes* except through deterministic policy-visible fields
> already defined by governance.

Precise reading:
- *Run A = Run B*: removing cognition enrichment from an already-formed governance proposal does
  **not** change the authorization verdict.
- It does **NOT** mean: removing cognition produces identical proposals. Cognition improves
  what gets proposed; it never changes whether a proposal is authorized.

## Structural guarantee

`fleet/cognition/**` may import only `fleet.crypto` (sign/verify/audit) and
`fleet.layers.handoff` (emit signed evidence). It must **never** import `gateway`, `policy`,
`runtime.act_trade`, `fin.domain.assess`, `incident.required_authorization`, or `verify`.
`fleet/tests/test_boundary.py` fails the build if it does. `exchange/quant/**` has an analogous
wall (`exchange/tests/test_boundary_quant.py`) forbidding `exchange.governance`, `fleet.fin`,
`fleet.cognition`.

## Layered cognition pipeline (implemented as scaffolding)

```
World → Observation → Scientific Knowledge Compiler (L0)
      → Dynamic Persona MoE GraphRAG (L1)
      → Evaluation (L2: PQ + NM + Popper + uncertainty)
      → ProposalArtifact { governance_surface (gates read this) | enrichment (ignored by gates) }
```

The split inside `ProposalArtifact` is the key rule:
- **Governance surface** answers *"what action is being requested?"*
- **Enrichment envelope** answers *"why might this action make sense?"*

Merging them ("because the model thinks this is correct, execute") is the architecture this
system is built to prevent.

## The quantitative layer is cognitive too

`exchange/quant/` is **not** authority. Kelly sizing, Bayesian updating, regime detection, and
edge estimation produce *beliefs* and *uncertainty* — they are attached to a proposal as
advisory enrichment (`quant` field on `OrderResponse`). They never enter `decide_trade`; a
verdict is computed first, then quant is attached. See
[`../architecture/exchange-vs-fin.md`](../architecture/exchange-vs-fin.md).

## Key documents

- [`research/D28-sovereign-cognitive-architecture.md`](../research/D28-sovereign-cognitive-architecture.md) — full spec.
- `fleet/cognition/` — compiler, evaluation, persona, calibration.
- `exchange/quant/` — probability, Bayesian, Kelly, regime, streaming, ZK (`D24`).
