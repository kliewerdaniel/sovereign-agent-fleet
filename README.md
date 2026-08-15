# Sovereign Agent Fleet

A **Fortified Enterprise Fleet** for the #AllThingsAgenticHackathon.

> Thesis: *Do not trust the model. Trust the execution protocol.* Authority
> (signing, approval, secrets, the knowledge graph) stays **local-first**; only
> signed, cryptographically verifiable artifacts replicate to GCP for public
> auditability.

The fleet demonstrates a governable 3-agent system — **Researcher → Analyst →
Operator** — that qualifies B2B sales prospects (ICP fit) against a *simulated*
CRM, with a hard verification gate and human-in-the-loop approval, while every
action is recorded in a tamper-evident, signed audit ledger.

## What's here (Phase 0 — crypto foundation)

| Path | Purpose |
|------|---------|
| `fleet/crypto/chriscrypt/` | Vendored **ChrisCryptSN** (MIT): Argon2id, XChaCha20-Poly1305 envelopes w/ per-record HKDF, Ed25519-signed hash-chain ledger. |
| `fleet/crypto/foundation.py` | Root-of-trust identity hierarchy, agent certs, per-record secret vault, tamper-evident `AuditTrail` — built clean-room on ChrisCryptSN. |
| `fleet/tests/test_crypto_phase0.py` | 22 crypto unit tests (key hierarchy, sign/verify, tamper + truncation detection, rotation/revocation). |
| `docs/planning/` | 19 living design docs: architecture, data model, interface contracts, testing strategy, roadmap, risk register, judging/submission strategy (D1–D20). |

Later phases add the **Control Plane** (Identity Registry + capability Gateway),
the three workers, and the GCP layer (Cloud Run / Firestore / Pub/Sub).

## Quick start

```bash
# 1. create an environment (Python 3.11+)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. run the Phase 0 crypto verification suite
PYTHONPATH=. python -m pytest fleet/tests/test_crypto_phase0.py -q
```

All tests should pass. The vendored ChrisCryptSN suite also runs green against
this same environment.

## Security properties (tested in Phase 0)

- **Root of trust:** an Argon2id-strengthened master derives a root Ed25519 key;
  every agent identity is a root-signed certificate. A forged/unsigned cert is
  rejected by the gateway.
- **Confidentiality:** local secrets are sealed with XChaCha20-Poly1305 under
  per-record HKDF subkeys (key-bound, name-bound — no plaintext fallback).
- **Tamper-evidence:** the audit ledger is an Ed25519-signed hash chain with a
  signed checkpoint, so any modification, reordering, or truncation is detected
  at verify time (fail-closed).
- **Live rotation:** an agent's key can be revoked and re-issued while the chain
  stays continuous (adversarial "revoke → rotate → resume" story).

## Mandatory hackathon constraints

- **Model:** Gemini 3.5 Flash (used only at the submission demo; dev/test run on
  a local Gemma4 brain behind a pluggable model interface).
- **Framework:** Google GenAI SDK (Gemini API called directly).
- **Cloud:** ≥1 GCP service — Cloud Run (runtime + approval console), Firestore
  (ledger + Memory Bank mirror), Pub/Sub (async bus).
- **Track:** Fortified Enterprise Fleet.

## License

MIT — Copyright (c) 2026 Daniel Kliewer. `fleet/crypto/chriscrypt/` is vendored
from ChrisCryptSN (MIT); its original LICENSE is preserved in that directory.
