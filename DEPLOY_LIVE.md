# Live GCP Deployment — Sovereign Agent Fleet (D17 console + verifiable mirror)

**Status: LIVE** as of 2026-08-19. Deployed to Cloud Run in `project-3ba93cec-8ca6-43c0-ba4` (region `us-central1`).

This replaces the old "GCP is stubbed to a local mirror" state. The deliverable
is now genuinely runnable on GCP:

- **Cloud Run service:** `fleet-approval-console` — the D17 human-approval
  console. Fail-closed: it holds only the human approver's **public** cert and
  GCP data; it never holds a private key and can verify but never forge a
  signature (control stays local).
- **Firestore:** signed artifacts replicate live to `fleet_ledger_live`; pending
  consequential actions live in `fleet_pending_actions`; approved records in
  `fleet_approvals`. All three are reconstructable from public keys only.

## What is verifiable on GCP (true, not asserted)
1. The audit ledger fans out to **live Firestore** via `GcpBridge(mode="gcp")`.
2. A verifier (`FirestoreVerifier`) recomputes the hash-chain and checks every
   signature using **only public keys** — identical code path to the console.
3. A judge can `GET /pending` on the console, sign an approval off-platform
   (private key never leaves the operator machine), `POST /approve`, and the
   console verifies that signature against the deployed public cert before
   persisting the record.

## How to judge a live action
```bash
source .deploy-venv/bin/activate
export FLEET_PROJECT=project-3ba93cec-8ca6-43c0-ba4
export CONSOLE_URL=https://<cloud-run-url>   # printed by deploy

# 1) Seed the live chain + push one pending action to the console /queue
python scripts/seed_gcp.py

# 2) Sign + POST an approval off-platform (uses the deterministic human key)
python scripts/judge_approve.py --action-id live-e2e-1 --approve
```

The human keypair is **deterministic** (`HUMAN_SEED` in both scripts) so the
deployed cert matches the off-platform signer. Changing the seed breaks the
judge loop — do not change it between seed and judge.

## Independent ledger verification (no console)
Beyond the console judge loop, a judge can verify the raw Firestore copy
**directly**, off-platform, with only public keys — no console, no private key,
no `ControlPlane`:

```python
from scripts.seed_gcp import reconstruct_audit_pubkey
from fleet.gcp.bridge import GcpBridge
from fleet.gcp.verify import FirestoreVerifier

bridge = GcpBridge(mode="gcp", project="project-3ba93cec-8ca6-43c0-ba4",
                   firestore_collection="fleet_ledger_live")
docs = bridge.mirror_docs()
assert FirestoreVerifier(docs, reconstruct_audit_pubkey()).verify() is True
```

`reconstruct_audit_pubkey()` re-derives the **public** audit key used to sign
the chain from the same HKDF derivation the seeder uses — so the check a judge
runs is byte-for-byte identical to the seeder's own verification. It performs no
Firestore writes, and `build()` (the ControlPlane constructor) is side-effect
free, so importing the seeder for verification can never fork or corrupt the
live chain.

## Files
- `fleet/gcp/bridge.py` — `GcpBridge` with `local` + `gcp` modes; pending/approvals.
- `fleet/gcp/console.py` — D17 WSGI console: `GET /` (live view), `POST /queue`,
  `GET /pending`, `POST /approve` (fail-closed verify).
- `fleet/gcp/deploy.py` — Cloud Run WSGI entrypoint (binds only public cert).
- `scripts/seed_gcp.py` — seeds live chain + publishes human cert + queues action.
- `scripts/judge_approve.py` — off-platform human signer (judge loop).
- `deployment/Dockerfile`, `cloudbuild.yaml`, `requirements-gcp.txt` — build artifacts.
- `scripts/deploy_gcp.sh` — single-shot deploy (non-destructive, no git push).

## Honesty note
`demo/scenes/gcp_proof.py` stamps `LOCAL_MIRROR_PROJECT` / `MODE: local` when run
locally, and `GCP_PROJECT` / `MODE: gcp` only when actually pointed at live GCP.
The proof script does NOT claim a live deployment it didn't make.
