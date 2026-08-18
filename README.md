# Sovereign Agent Fleet

> **A sovereign cognitive control plane for governing probabilistic agents and
> consequential actions.**
>
> Cognition is probabilistic. Authority is deterministic.
> The model proposes. The protocol decides. Cryptography verifies. The ledger remembers.

Sovereign Agent Fleet is **not another multi-agent framework.** Frameworks orchestrate
agents. This governs them — and the governance is independent of *which* brain produced a
proposal (local LLM, cloud model, or a pure deterministic strategy).

Finance is the **flagship exemplar** of this architecture, not its reason for existing. Few
domains expose the full arc so cleanly: probabilistic reasoning, mathematical inference, risk,
consequential actions, deterministic authorization, and independent verification — all under
one roof. The architecture underneath is **domain-general**.

---

## 1. The problem

Modern agentic systems combine powerful probabilistic reasoning with increasingly
consequential actions.

The model can reason. **But reasoning is not authority.**

A confident model is not an authorized one. A correct model is not a permitted one. An
identity can be compromised and still be prevented from escalating authority. Evidence can
establish truth without granting permission.

## 2. The thesis

Sovereign Agent Fleet separates:

- **cognition** — probabilistic, may be wrong, may be compromised, proposes only;
- **governance** — deterministic, model-agnostic, decides authorization;
- **execution** — stateful, untrusting, validates before it acts;
- **verification** — independent, public-key-only, proves what happened.

> **Meta-invariant M0:** *No security invariant depends on model behavior.* The model may lie,
> hallucinate, or deliberately propose the worst possible action — the authority boundary holds
> regardless. This is enforced by import walls and proven by a verifier that recomputes the
> disposition with all cognition stripped (Run A = Run B).

## 3. Architecture

```text
                 SOVEREIGN COGNITIVE CONTROL PLANE

                         ┌───────────────┐
                         │   Cognition   │  observe, reason, propose
                         │               │  D28 personas/retrieval/reasoning
                         │               │  exchange/quant: probability,
                         │               │   Bayesian, Kelly, regime, edge
                         │               │   → EVIDENCE only, never authority
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

**The quant layer is an evidence layer, not an authority.** Kelly sizing, Bayesian updating,
regime detection, and edge estimation tell the system *what it believes* and *how strongly* — they
never decide *what it is permitted to do*. Risk/authorization is a deterministic function in the
governance layer; quant output is attached as advisory enrichment only (see
[`docs/cognition/`](docs/cognition/) and [`docs/architecture/exchange-vs-fin.md`](docs/architecture/exchange-vs-fin.md)).

## 4. The demonstration

The combined "aha": an agent proposes a consequential financial action → the quantitative/cognitive
layer produces the reasoning and evidence → deterministic governance evaluates authority and risk →
the action is **accepted or rejected** → an independent verifier proves what happened. Then the
adversarial case: a highly capable, confident model **still cannot bypass governance**.

That is the conceptual heart — `MODEL OUTPUT ≠ AUTHORITY`.

Watch:
- **Adversarial 8-beat governability demo** (core): [`demo/sovereign_agent_fleet_demo.mp4`](demo/sovereign_agent_fleet_demo.mp4) — a model proposes; governance decides; a forged identity is rejected; a HALLUCINATION is blocked; tampering is detected; revoke+rotate keeps the chain intact.
- **Exchange quant pipeline** (flagship): [`demo/exchange_demo/exchange_demo_1080p.mp4`](demo/exchange_demo/exchange_demo_1080p.mp4) — propose → evidence → authorize → state-locked execute → verify. Live script: `python demo/quant_demo.py`.
- **ZK attestation** (advanced): `exchange/quant/zk.py` (D24) proves a learned prior lies in a public range *without revealing it*.

See [`docs/demos/`](docs/demos/) for the full matrix.

## 5. Security / governance model

- **Root of trust:** Argon2id-strengthened master → root Ed25519 key; every agent identity is a
  root-signed certificate. A forged/unsigned cert is rejected.
- **Tamper-evidence:** the audit ledger is an Ed25519-signed hash chain with a signed checkpoint;
  any modification, reordering, or truncation is detected at verify time (fail-closed).
- **Deterministic authority:** policy + capability + signing live in the control plane, never in the
  model. The model proposes; the protocol decides.
- **Human-in-the-loop (D17):** consequential actions require a human-signed `ApprovalRecord` bound
  to the *exact* action + capability + artifact hash. Forged/rebound/reused approvals are rejected.
- **Default-deny:** an exhaustive property test asserts every unknown `(role, capability)` pair is
  DENIED — no silent allow.
- **Consensus can only escalate:** two distinct brains must agree to VERIFY; disagreement cannot
  turn a policy violation into an authorized action.
- **Live key rotation:** an agent's key can be revoked and re-issued while the chain stays continuous.
- **Independent verification:** a verifier reconstructs inputs and recomputes the disposition with
  only public keys — proving what happened without holding authority.

Full adversarial coverage is in [`docs/security/`](docs/security/). Every property above is a
passing test.

## 6. Repository layout

| Path | Role |
|------|------|
| `fleet/` | **General-purpose governance substrate** — crypto, identity, policy, gateway, approval, consensus, incident, cognition, audit ledger, GCP mirror, REST+UI control plane. |
| `exchange/` | **Flagship financial workload** — sovereign prediction-market venue (matching engine, books, settlement, feeds, routing, venues) + `quant/` quantitative cognition layer. Reuses `fleet` as a library. |
| `fleet/fin/` | **Reference financial workload** (D27) — the earlier paper-trading exemplar that established the governed-execution pattern. Kept intentionally; see [`docs/architecture/exchange-vs-fin.md`](docs/architecture/exchange-vs-fin.md). |
| `incident/` | **Second external consumer — M0 domain-generality proof** — a non-finance (incident-response) workload whose `epistemic_adapter/` consumes the *same* frozen `fleet.epistemic.decide()` as `exchange/`, with **zero substrate edits**. Proves the substrate cannot distinguish which domain feeds it. |
| `supply/` | **Third external consumer (M0)** — operations/logistics (supply-chain replenishment) workload. Same frozen `decide()`, same contract, a completely different domain *shape* than finance or security. |
| `hypothesis/` | **Fourth external consumer (M0)** — scientific research / hypothesis reasoning. The exact domain the substrate's own `Proposition` docstring names as the canonical non-finance example; exercises the linchpin `Proposition` type hardest. |
| `mirror/` | **Fifth external consumer (M0)** — agent self-observability / introspection. Exercises the full L0 ladder (`Proposition` → `Assessment` → `Recommendation` → `Proposal` bounded by `ProposalScope` → `AuthorizationRequest`) through the same frozen `decide()`. The L0 promotion gate is enforced fail-closed at this bilingual boundary because the frozen substrate is intentionally domain-neutral. |
| `ui/` | **Canonical control-surface UI** (Next.js) over `fleet/api`. Always current. |
| `web/` + `bridge/` | **Legacy / hands-off** control surface (Phases 0–6). Intact but not maintained. |
| `demo_app.py` | Streamlit incident-triage viewer (D26 demo only). |
| `demo/` | Assembled demo videos + capture scripts. |
| `docs/` | Layered documentation (start at [`docs/overview/`](docs/overview/) or [`docs/README.md`](docs/README.md)). The full decision log lives in [`docs/research/`](docs/research/). |

## 7. Quick start

```bash
# 1. environment (Python 3.11+)
python -m venv .deploy-venv && source .deploy-venv/bin/activate
pip install -r requirements.txt

# 2. full test suite — 546 passing
python -m pytest -q

# 3. canonical control surface (fleet/api + ui/)
python -m uvicorn fleet.api.app:app --host 127.0.0.1 --port 8788
cd ui && npm install && npm run dev      # http://127.0.0.1:3002

# 4. flagship financial demo (real exchange.api, proves M0)
python demo/quant_demo.py
```

Live Kalshi market data / order routing is **opt-in and fail-closed** — the default runtime is
fully simulated and runs end-to-end with no cloud credentials. GCP replication defaults to a
local Firestore-shaped mirror; flip to live only with credentials present.

## 8. What's implemented (all merged, 546 tests)

- **Governance substrate** (`fleet/`): crypto, signed ledger, registry, policy, gateway, evidence
  gate, D17 approval, consensus, Model Armor, incident matrix, runtime, GCP mirror.
- **Cognition scaffolding** (D28): `fleet/cognition/` — the conceptual bridge; import-walled.
- **Reference financial workload** (D27): `fleet/fin/` — RiskLayer, `TradeAuthorization`,
  `ExchangeSim`, standalone `verify.py`.
- **Flagship financial workload** (D29/D30): `exchange/` — sovereign venue + `exchange/quant/`
  (probability, edge, Kelly, Bayesian, regime, streaming, learning loop).
- **Real ZK attestation** (D24): `exchange/quant/zk.py` — genuine Σ-protocol range proof + Ed25519 binding.
- **Domain registry (M0 consolidation)**: `domain_registry/` — a fifth bilingual harness node (not a domain, not part of the substrate) that owns the M0 cross-domain generality claim ONCE. It holds a single `REGISTERED_CAPABILITIES` table (the five external consumers as `(label, capability)` pairs) and a single parameterized generality suite: same-policy→same-verdict across all five, policy-flip AUTO→HUMAN together, no shared per-domain state, bounded scope (out-of-scope capability BLOCKED), and AST-confirmed `fleet.epistemic` import wall. Adding a domain is now a one-line table edit plus the recipe in `docs/development/adding-an-epistemic-domain.md`. The four domain suites' duplicated C-section was removed and replaced by this registry suite.
- **Control surfaces**: canonical `ui/` (Next.js) over `fleet/api`; legacy `web/`+`bridge/`; `demo_app.py`.

## 9. Research / technical deep dives

- [`docs/architecture/`](docs/architecture/) — the control plane, trust model, integrations.
- [`docs/cognition/`](docs/cognition/) — D28, the bridge from governance to quantitative decision-making.
- [`docs/governance/`](docs/governance/) — identity, policy, capability, approval, consensus.
- [`docs/security/`](docs/security/) — adversarial plan, ZK (D24), consensus, crypto design.
- [`docs/roadmap/`](docs/roadmap/) — implemented vs. next-stage research, and the open question set.
- [`docs/research/`](docs/research/) — full D1–D30 decision log and original planning package.

## 10. Roadmap & competition positioning

The trajectory **D27 → D28 → D29/D30** reads as an evolution, not a feature list:
**governed action → governed cognition → governed quantitative decision-making.** The next major
version asks how belief, evidence, and uncertainty should be represented so the control plane can
govern *quantitative* proposals as rigorously as it governs *action* — while the model never
becomes the authority. The open questions are catalogued in
[`docs/roadmap/`](docs/roadmap/).

This project targets the **All Things Agentic Hackathon** (track: *Fortified Enterprise Fleet*;
secondary: *Best Architectural Design*). The framing optimizes for architectural clarity and a
judge understanding the thesis in the first few minutes. If the target changes, the presentation
adapts to the rubric.

## 11. License

MIT — Copyright (c) 2026 Daniel Kliewer. `fleet/crypto/chriscrypt/` is vendored from
ChrisCryptSN (MIT); its original LICENSE is preserved in that directory.
