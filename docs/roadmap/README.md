# Roadmap — implemented vs. next-stage research

## Implemented (all merged to `main`, 496 tests)

- **Governance substrate** (`fleet/`): crypto root-of-trust, signed hash-chain ledger, registry,
  policy engine, capability gateway, evidence gate, D17 human approval, consensus, Model Armor,
  incident matrix, runtime, GCP mirror.
- **Cognition scaffolding** (D28, `fleet/cognition/`): compiler/evaluation/persona/calibration,
  import-walled; the conceptual bridge to governance.
- **Reference financial workload** (D27, `fleet/fin/`): RiskLayer, `TradeAuthorization`,
  `ExchangeSim`, standalone `verify.py`.
- **Flagship financial workload** (D29/D30, `exchange/`): sovereign prediction-market venue
  (matching engine, books, shadow ledger, smart routing, Kalshi adapter + live v2 feed/WSS),
  plus `exchange/quant/` (probability, edge, Kelly, Bayesian, regime, streaming, learning loop).
- **Real ZK attestation** (D24, `exchange/quant/zk.py`): genuine Σ-protocol range proof +
  Ed25519 binding.
- **Control surfaces**: canonical `ui/` (Next.js) over `fleet/api`; legacy `web/`+`bridge/`
  (hands-off); `demo_app.py` incident viewer.
- **Demos**: adversarial 8-beat video, exchange quant pipeline video + `quant_demo.py`, ZK tests.

## Explicitly out of scope / deferred (honest)

- Real brokerage / capital / settlement (simulation only — always).
- TPM / enclave hardware roots.
- Operator sandbox (D25, deferred with reason — the gateway + A1/A2 boundary already holds).
- Premature generic "consequential-action framework" abstraction (prove with two workloads first).

## The next-stage question set (open)

The trajectory **D27 → D28 → D29/D30** looks less like a feature list and more like an evolution:
**governed action → governed cognition → governed quantitative decision-making**. The questions
that start the next major version are deliberately left open (see the roadmap discussion in the
repo). They include:

- What exactly constitutes an **agent belief**? An **evidence** record? How do we represent
  **uncertainty**?
- How does a quantitative signal become an actionable **proposal**? Where does **risk** computation
  live?
- Which mathematical operations must be **deterministic**? Which may be **probabilistic**?
- How does the control plane **compare competing agents/signals**? How do we prevent an agent from
  **gaming its own confidence**?
- How do we distinguish **prediction accuracy** from **decision quality**?
- How does the control plane reason about **changing environments**?
- What should be **learned** vs **formally specified**?
- Where does D28 cognition actually **enter the runtime**?
- How does the architecture **generalize beyond finance**?

## Key documents

- [`research/15-implementation-roadmap.md`](../research/15-implementation-roadmap.md)
- [`research/16-risk-register.md`](../research/16-risk-register.md)
- [`research/17-judging-submission-strategy.md`](../research/17-judging-submission-strategy.md)
- [`research/18-executive-summary.md`](../research/18-executive-summary.md)
- [`research/19-MASTER-SUBMISSION.md`](../research/19-MASTER-SUBMISSION.md)
