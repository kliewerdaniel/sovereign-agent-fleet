# Sovereign Agent Fleet — Literal Rebuild Gap Report

**Build:** separate `fleet/api/` FastAPI service + second `ui/` Next.js 16 control surface.
**Scope decision:** `bridge/` and `web/` are HANDS-OFF (untouched). `fleet/api/` and `ui/` are new, additive.
**Thesis under test:** _Do not trust the model. Trust the execution protocol._ Authority (signing,
approval, secrets, KG) is local-first; only signed artifacts replicate.

---

## 1. What is REAL (binds to `fleet/`, no reimplementation)

| Concern | How it is real |
|---|---|
| Crypto / signing | All Ed25519 signing goes through the **existing** `fleet.crypto.foundation` + `fleet.layers.Approval.sign`. The UI never signs; `POST /approvals/{id}/decide` calls `Approval.sign` with the human's real cert/key and returns a genuine 128-char `human_sig`. |
| Policy engine | `required_authorization(verification, severity, action, workload_id)` in `fleet/layers/incident.py` drives every verdict. Verified live: HALLUCINATION→BLOCKED, VERIFIED+MEDIUM+app-db+isolate→HUMAN/needs_approval. |
| Hash chain | Reads the **real** signed `AuditTrail` (`fleet.crypto.chriscrypt.ledger`). `/chain/integrity` runs `ControlPlane.verify_audit()` — observed `valid: true`. |
| Incident pipeline | `/run/incident` drives the genuine Researcher→Analyst→Operator + `SimEnv` against the live control plane; produces real handoffs with real signatures. |
| Adversarial beats | `fleet/api/beats.py` runs the **real** control-plane code in an ISOLATED sandbox `ControlPlane` (mirrors `fleet/tests/test_adversarial_beats_phase5.py`). Beats do not mutate the live API instance. Beat 1 verified live: pass, 1 signed entry. |
| Revoke/rotate | `POST /agents/{id}/revoke-rotate` calls `registry.revoke` + `registry.rotate` on the live plane; returns post-rotation cert and `chain_valid`. |

---

## 2. What is NOT live / honest limitations

| Item | Status | Honesty note |
|---|---|---|
| GCP replication | **Stubbed to local mirror.** `GcpBridge(mode="local")`. Beats 5/6 assert against `bridge.mirror_docs()` (a local Firestore emulator shape), not a live GCP project. UI labels live paths honestly via `LiveBanner` + the `/demo` scope banner. |
| Adversarial demo | **Local sandbox, not production.** Beats run a fresh in-process fleet per call. This proves the protocol enforces each guarantee by construction; it is NOT a deployment. Banner states this explicitly. |
| `frontend integration/e2e (Playwright)` | **CLOSED.** `ui/e2e/fleet.spec.ts` (6 specs) drives the real UI against the live `:8788` control plane: overview+live banner, valid chain, HALLUCINATION→BLOCKED fail-closed, D17 approve→genuine 128-char human_sig, adversarial beat pass, registry+revoke-rotate. **6 passed.** Runs against `next build && next start` (dev server's Turbopack HMR 403s on static chunks to headless Chromium, blocking hydration). |
| `SimEnv` environment state | The live `run_incident` mutates an in-memory `SimEnv`; state resets per API-process lifetime and is not persisted to GCP. |
| Frontend signing/approval | The UI has zero authority: it only reads projections and calls write endpoints that delegate to the fleet. Confirmed by code review + the `/demo`/`/approvals` pages containing no key material. |

---

## 3. Genuine fleet bugs / gaps surfaced (deliverable per prompt)

### G3.1 — Remediation fork drops the durable `needs_approval` ledger entry
**Severity:** medium (breaks the approval-queue observability contract).
**Where:** `fleet/layers/runtime.py`, `Operator._act_remediation()`.
**Symptom:** When an action requires HUMAN authorization but carries no signed
`ApprovalRecord`, the remediation fork returned `needs_approval=True` **without appending
any durable ledger entry**. The generic `act()` path, by contrast, logs
`operator.needs_approval`. Result: the pending queue (`pending_approvals()`) and the D17
`decide()` could not see the held action → `decide` raised `KeyError` → 404 on the approval
console.
**Resolution (fixed at the fleet layer):** `fleet/layers/runtime.py:_act_remediation` now
logs a durable `operator.needs_approval` entry (same shape the generic `act()` path uses)
in the HUMAN-no-approval branch. The earlier API-layer patch in `fleet/api/runtime.py` has
been **removed** — the fix now lives in the real control plane, so `bridge/`, `fleet/api/`,
and any future surface all benefit. Verified: full `fleet/tests` suite **227 passed**,
`fleet/tests/test_fleet_api.py` **22 passed**, no regression.
**Recommendation:** none outstanding — root cause closed at the correct layer.

### G3.2 — `Approval.sign` blanks `approval_id` before signing (correctness subtlety)
**Where:** `fleet/layers/runtime.py:Approval.sign`, `fleet/api/beats.py:_beat4`.
**Symptom:** `Approval.sign` signs the body with `approval_id=""` blanked, then sets the
real `approval_id` on the returned object. Any re-verification that forgets to blank
`approval_id` will fail signature verification. `beats.py:_beat4` originally omitted the
`verify_body["approval_id"] = ""` line — fixed. This is fleet-intended behavior (the
signature binds everything except the server-minted id), but it is a sharp edge worth a
docstring/assert so callers don't trip on it.

### G3.3 — `agent_id` missing from `pending_approvals` for API-appended entry
**Where:** `fleet/api/app.py` `_proj_entries` only keeps `AuditEntry` fields; the
`operator.needs_approval` entry nests `who` inside `payload`, not top-level.
**Fix:** `fleet/api/runtime.py:pending_approvals` now reads `who` from both top-level
and `payload`. Cosmetic (console showed empty agent) — not a security issue.

### G3.4 — `LedgerPage.head` rejects `None`
Schema `LedgerPage.head: str` rejected `None` on small/empty ledgers → 500. Fixed by
making it `Optional[str]`. Cosmetic robustness.

---

## 4. Test status

| Suite | Result |
|---|---|
| `fleet/tests/test_fleet_api.py` (22 cases: shape, reject unsigned/invalid writes, SSE, beats, pending+decide) | **22 passed** |
| `ui/` TypeScript (`tsc --noEmit`) | **clean** |
| `ui/` production build (`next build`) | **green**, 8 routes |
| `ui/` route reachability (dev server) | **all 7 pages 200** |
| Backend↔UI data contract (curl against `:8788`) | **verified**: beats, run-incident verdicts, decide signature, chain integrity |
| **Playwright e2e (frontend behavior)** | **6 passed** (`ui/e2e/fleet.spec.ts`, against live `:8788`) |

---

## 5. Build-prompt constraint compliance

1. **Frontend has zero authority** — ✅ verified (no signing/approval key material in `ui/`).
2. **Uses REAL fleet code** — ✅ `fleet.layers`, `fleet.crypto` only; no reimplementation.
3. **Honest about live vs stubbed** — ✅ this report + `LiveBanner` + `/demo` scope banner.
4. **Full test pass** — ⚠️ API + build green; Playwright e2e OPEN (see §2).
5. **Flag fleet bugs** — ✅ §3 (G3.1 is the headline).
6. **Deliverable: working app + committed + tests passing + gap report** — app works, tests pass, gap report here; **commit/push pending user review** (standing no-push rule).
7. **Thesis: authority is local-first** — ✅ only signed artifacts; GCP is `local` mirror.
