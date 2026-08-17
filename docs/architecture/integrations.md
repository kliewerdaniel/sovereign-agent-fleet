# Integrations — how the pieces fit together

The repo has several surfaces. This documents which is canonical and which is legacy/secondary.

## Control surfaces (UIs)

| Surface | Backend | UI | Ports | Status | Role |
|---------|---------|----|-------|--------|------|
| **`fleet/api/` + `ui/`** | `fleet.api.app` (FastAPI over live `ControlPlane`) | `ui/` Next.js 16 (7 routes) | API `:8788`, UI `:3002` | **canonical / current** | The competition control surface. |
| `web/` + `bridge/` | `bridge/app.py` (FastAPI) | `web/` Next.js 16 (12 routes) | `:8787` / `:3001` | **legacy / hands-off** | Phases 0–6 surface. Intact but not maintained. Do not build on it. |
| `demo_app.py` | Streamlit | — | `:8501` | incident-demo-only | D26 incident-triage viewer. |

**Canonical path for a judge:** `fleet/api/` + `ui/`. The `web/`+`bridge/` surface is kept for
historical completeness and may be removed in a later cleanup — not during competition prep.

## Package dependency direction

```
exchange/  ──imports──▶  fleet/   (as a LIBRARY: crypto, layers, runtime)
ui/        ──calls────▶  fleet/api/  (REST + SSE; never signs/approves)
web/       ──calls────▶  bridge/  ──uses──▶ fleet/  (legacy mirror)
demo_app.py ──drives──▶  fleet/  (incident runtime)
```

Key invariant: **no UI or domain package re-implements crypto, policy, or approval.** They
consume `fleet` as a library. The `exchange/` and `fleet/fin/` packages both sit *above*
`fleet`'s governance layer and reuse it.

## External adapters (optional, gated)

- **GCP** (`fleet/gcp/`): Firestore/Pub-Sub mirror + Cloud Run approval console.
  **Default `local`** (a Firestore-shaped local mirror); flips to live only with credentials.
  The cloud instance verifies human-signed approvals; it never holds authority.
- **Kalshi** (`exchange/venues/kalshi.py`, `exchange/feeds.py`, `exchange/ticker_stream.py`):
  real v2 read-only market data + RSA-PSS signed requests. **Fail-closed**: live orders
  require explicit `allow_live_orders=True`; live feed requires `live_feed=True`/env. Sim is
  the default.

## How to run the canonical stack

See [`../development/`](../development/). Short version:

```bash
# API + UI (canonical)
.deploy-venv/bin/python -m uvicorn fleet.api.app:app --port 8788
cd ui && npm install && npm run dev      # http://127.0.0.1:3002

# Exchange venue (no UI; REST+SSE contract)
.deploy-venv/bin/python -m uvicorn exchange.api:app --port 8790
```
