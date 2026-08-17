# Sovereign Agent Fleet — Documentation

> **A sovereign cognitive control plane for governing probabilistic agents and
> consequential actions.**
>
> Cognition is probabilistic. Authority is deterministic. The model proposes;
> the protocol decides; cryptography verifies; the ledger remembers.

This repository contains a general-purpose, local-first governance substrate
(`fleet/`) plus a flagship financial reference workload (`exchange/` — a sovereign
prediction-market venue with a quantitative cognition layer). The architecture is
**domain-general**: finance is the strongest environment we have for demonstrating
it, not the reason it exists.

## Where to start (judge path)

Read these in order; each is short:

1. **[`overview/`](overview/)** — what this is, why it exists, and the core thesis in 30 seconds. **Start here.**
2. **[`architecture/`](architecture/)** — the layered control plane, the data/authority flow, and the diagram.
3. **[`cognition/`](cognition/)** — D28: the conceptual bridge from governance to quantitative decision-making (the model stays proposal-only).
4. **[`governance/`](governance/)** — identity, policy, capability, approval, consensus, the incident + financial decision matrices.
5. **[`security/`](security/)** — the adversarial test plan, the ZK attestation (D24), consensus, selective-disclosure.
6. **[`demos/`](demos/)** — what to watch / run first, and what each demo proves.
7. **[`development/`](development/)** — how to run the tests, the quick start, the import-wall boundary guarantees.
8. **[`roadmap/`](roadmap/)** — what's implemented vs. future research; the next-stage questions.

## Living design archive

[`research/`](research/) holds the full decision log (D1–D30) and the original
planning package. It is the deep record — exhaustive, not curated. For the
narrative, prefer the layer docs above.

## Top-level entry points in the repo

| Path | Role |
|------|------|
| `README.md` (repo root) | Primary landing page. |
| `fleet/` | General-purpose governance substrate: crypto, identity, policy, gateway, approval, consensus, incident, cognition, audit ledger, GCP mirror, REST+UI control plane. |
| `exchange/` | **Flagship financial workload** — sovereign prediction-market venue (matching engine, books, settlement, feeds, routing, venues) + `quant/` quantitative cognition layer (probability, edge, Kelly, Bayesian, regime, streaming, ZK attestation). Reuses `fleet` as a library. |
| `fleet/fin/` | **Reference financial workload** (D27) — the earlier paper-trading exemplar that established the governed-execution pattern. Kept intentionally; see `architecture/exchange-vs-fin.md`. |
| `ui/` | **Canonical control-surface UI** (Next.js) over `fleet/api`. Always current. |
| `web/` + `bridge/` | **Legacy / hands-off** control surface from Phases 0–6. Intact but not maintained; do not build on it. |
| `demo_app.py` | Streamlit incident-triage viewer (D26 demo only). |
| `demo/` | Assembled demo videos + capture scripts (incident 8-beat, exchange quant). |
| `docs/assets/` | Architecture diagram (`architecture.svg` / `.png`). |

## Two rules this repo never breaks

- **The model is not the authority.** No security invariant depends on model
  behavior (meta-invariant **M0**). Quant/Kelly/Bayesian signals are *evidence*,
  never authorization inputs.
- **Governance is local-first.** Keys, signing, and policy stay local; only
  signed, verifiable artifacts leave the boundary.
