# Demos — what to watch / run first

This repo has three main demonstrations. Watch them in this order for the competition story.

## 0. Combined flagship film — *watch first*

**Video:** [`demo/sovereign_agent_fleet_combined_1080p.mp4`](../demo/sovereign_agent_fleet_combined_1080p.mp4)
(~4:30, 1080p). Title slate → Part 1 (adversarial governability) → Part 2 (exchange quant
pipeline) → outro slate. Built locally from the two segments below with `demo/build_combined.py`
— no re-render, no cloud, identical narration to the source films.

> **Local-first, always.** Both halves run with `FLEET_MODE=local`. The exchange film's "live"
> beats show a *real* Kalshi market-data capture (genuine ticks, no fabricated output) in an
> opt-in sim/live toggle; the governance half never needs a cloud. Nothing in either film
> depends on a remote service to execute.

## 1. Adversarial governability demo (core "aha")

**Video:** [`demo/demo_1080p.mp4`](../demo/demo_1080p.mp4)
(2:43, narrated with a local TTS voice, rebuilt from the honest 8-beat render).

Source segment for the combined film. Proves the thesis in 8 beats: a model proposes;
governance decides; a forged identity is rejected; a missing capability is DENIED; a
HALLUCINATION is blocked; post-hoc tampering is detected; revoke+rotate keeps the chain intact.
Every beat is a passing test (`fleet/tests/test_adversarial_beats_phase5.py`).

> **Model output ≠ authority.** A model may be correct and still be unauthorized. A model may
> be confident and still be denied.

## 2. Exchange quant pipeline (flagship financial demonstration)

**Video:** [`demo/exchange_demo/exchange_demo_1080p.mp4`](../demo/exchange_demo/exchange_demo_1080p.mp4)
(~1:28, assembled from real `exchange/` runs). Source segment for the combined film.

The end-to-end arc:
```
market data → research/quant agents (probability, edge, Kelly, regime, Bayesian)
  → proposal → D16 evidence gate → capability → risk matrix
  → authorization (AUTO / HUMAN / BLOCKED) → D17 human approval if HUMAN
  → venue executes against the EXACT evaluated state (S1≠S2 defense)
  → signed ExecutionReceipt → ledger → independent verifier recomputes
```

**Live script:** `demo/quant_demo.py` (`python demo/quant_demo.py` from repo root with
`.deploy-venv`). It exercises the real `exchange.api` REST surface and proves the M0 invariant:
the authorization verdict is **identical** with or without the signed `QuantEvidence`
envelope attached — because the quant layer is advisory evidence, never an input to the gate.

## 3. ZK attestation (advanced "wow") — *secondary*

`exchange/quant/zk.py` (D24): proves a learned prior lies in a public range **without revealing
the prior**. Best shown after the core story, as the "here's how far the evidence/verification
layer goes" capstone. Tests: `exchange/tests/test_quant_d24.py`.

## Incident-triage demo (sibling reference workload)

`demo_app.py` (Streamlit): the D26 incident-remediation use case — the model proves a workload
is compromised, yet policy still BLOCKS isolating a PROTECTED asset. The same governance
substrate, a different domain. Run: `pip install -r requirements-ui.txt && streamlit run demo_app.py`.

## Demo matrix

| Demo | What it proves | Implementation | Tests | UI | Judge value |
|------|---------------|----------------|-------|----|-------------|
| Adversarial 8-beat | model ≠ authority; denial is enforced | `fleet/tests/test_adversarial_beats_phase5.py` | 9 passing | `ui/` + video | **core** |
| Exchange quant pipeline | propose→evidence→authorize→state-locked execute→verify | `exchange/api.py` + `exchange/quant` | 170 exchange tests (incl. 10 D24 ZK) | REST+SSE (no UI) + `quant_demo.py` + video | **flagship** |
| ZK attestation | prove prior ∈ range without revealing it | `exchange/quant/zk.py` | 10 passing | n/a (unit) | advanced |
| Incident triage | evidence ≠ authority (cross-domain) | `fleet/tests/test_incident_*.py` | 14 passing (8 e2e + 6 policy) | `demo_app.py` | reference |
| Financial e2e (paper) | governed-execution pattern, minimal noise | `fleet/tests/test_financial_e2e.py` | 17 + 14 adversarial | n/a | reference |

## Where to go next

- Run the suite: [`../development/`](../development/)
- Understand the architecture: [`../architecture/`](../architecture/)
- The "aha" combined story: proposal + cognitive evidence → deterministic governance → accept/deny
  → independent verification, then the adversarial denial case.
