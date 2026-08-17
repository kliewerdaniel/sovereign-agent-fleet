# Development — run, test, build

## Quick start

```bash
# 1. environment (Python 3.11+). Use the deploy venv; .venv is also fine.
python -m venv .deploy-venv && source .deploy-venv/bin/activate
pip install -r requirements.txt          # base
pip install -r requirements-gcp.txt       # only if exercising the GCP mirror

# 2. run the full suite
python -m pytest -q
# → 384 passed (fleet + exchange)

# 3. run a focused area
python -m pytest fleet/tests/test_adversarial_beats_phase5.py -q   # core aha
python -m pytest exchange/tests/test_quant_d24.py -q              # ZK
python -m pytest exchange/tests/test_boundary_quant.py -q         # import-wall
```

> **Note on env isolation.** Some of this repo's test/run paths are sensitive to leaked
> `PYTHONPATH`/`VIRTUAL_ENV` from the host shell. If a collection looks wrong, run with a clean
> env: `env -i PATH="$PWD/.deploy-venv/bin:/usr/bin:/bin" HOME="$HOME" "$PWD/.deploy-venv/bin/python" -m pytest -q`.

## Canonical control surface (`fleet/api/` + `ui/`)

```bash
# API (FastAPI over the live ControlPlane)
.deploy-venv/bin/python -m uvicorn fleet.api.app:app --host 127.0.0.1 --port 8788

# UI (Next.js 16, from ui/)
cd ui && npm install && npm run build && npm run start   # http://127.0.0.1:3002
# or dev: npm run dev

# Frontend e2e (Playwright) — drives the real UI against the live :8788 API
cd ui && npx playwright test        # 6 specs, all passing
```

## Exchange venue (`exchange/` — no dedicated UI)

```bash
.deploy-venv/bin/python -m uvicorn exchange.api:app --host 127.0.0.1 --port 8790
# REST + SSE contract; venues are STUBS by default (fail-closed).
# Live Kalshi requires explicit opt-in (allow_live_orders / KALSHI_LIVE_FEED) — never default-on.
```

## The demo scripts

```bash
python demo/quant_demo.py          # flagship financial arc, real exchange.api, proves M0
pip install -r requirements-ui.txt && streamlit run demo_app.py   # incident-triage viewer
```

## Epistemic substrate planning

- [`epistemic-substrate-implementation-plan.md`](epistemic-substrate-implementation-plan.md) — **Round 3 implementation plan** (PLANNING ONLY, uncommitted, no code): L0 `fleet/epistemic/` neutral primitives, L1 R1 contract, L2 boundary tests, adapters (PROMOTE don't move), the tiny financial vertical slice, "Deferred by Design", and the 10-point final gate — all 10 answer YES → **IMPLEMENTATION READY**.
- [`round4-readiness-acceptance-harness.md`](round4-readiness-acceptance-harness.md) — **Round 4 implementation-readiness pass** (PLANNING ONLY, uncommitted, no code): reconstructs the ratified architecture, reconciles it against the real repo (per-symbol reuse/promote/adapt/untouched table), gives the exact flat acyclic L0→L2 module graph, instantiates the 5-profile contract for 21 firm roles (proves capability/authority/epistemic-standing are orthogonal), runs workflows A–E + 10 adversarial attacks through the ladder, classifies 26 quant-math concepts as epistemic vs governance, the ruthless minimum-v1 table, the revised Phase 0→6 order, invariants I1–I20, and ends **IMPLEMENTATION READY** with the first hard gate.

## Test organization

| Area | Location | Count (approx) |
|------|----------|----------------|
| Core governance + adversarial | `fleet/tests/` | 73 files |
| Exchange venue + quant | `exchange/tests/` | 59 files |
| Import-wall guarantees | `fleet/tests/test_boundary.py`, `exchange/tests/test_boundary_quant.py` | 2 |

## Boundary guarantees (verified, not aspirational)

- `fleet/cognition/**` may not import `gateway`/`policy`/`runtime.act_trade`/`fin.domain.assess`/`incident.required_authorization`/`verify`.
- `exchange/quant/**` may not import `exchange.governance`/`fleet.fin`/`fleet.cognition`.

These are build-failing tests, not conventions.

## Deep references

- [`research/14-testing-strategy.md`](../research/14-testing-strategy.md)
- [`research/15-implementation-roadmap.md`](../research/15-implementation-roadmap.md)
- [`research/D27-financial-workload-architecture-lock.md`](../research/D27-financial-workload-architecture-lock.md) (I1–I17 invariant catalog)
