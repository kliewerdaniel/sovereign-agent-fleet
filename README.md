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

## Demo

- **4-minute demo video:** [`demo/sovereign_agent_fleet_demo.mp4`](demo/sovereign_agent_fleet_demo.mp4)
  — the live adversarial 8-beat governability demo, narrated.
- **Architecture diagram:** [`docs/assets/architecture.png`](docs/assets/architecture.png)
  (dark-first; source SVG alongside).

The demo is assembled entirely from **real artifacts**: the pytest beat output,
the GCP public-key verification proof (`GcpBridge` + `FirestoreVerifier`), and
the pluggable-brain schema boundary. GCP is not live in the demo (Cloud Run
min-instances 0) — the identical local code path is used and labeled as such.

## What's here (Phases 0–5, all complete)

| Path | Purpose |
|------|---------|
| `fleet/crypto/chriscrypt/` | Vendored **ChrisCryptSN** (MIT): Argon2id, XChaCha20-Poly1305 envelopes w/ per-record HKDF, Ed25519-signed hash-chain ledger. |
| `fleet/crypto/foundation.py` | Root-of-trust identity hierarchy, agent certs, per-record secret vault, tamper-evident `AuditTrail`. |
| `fleet/layers/registry.py` | Agent Registry: publish / version / discover / revoke / rotate (on IdentityRoot + AuditTrail). |
| `fleet/layers/policy.py` | Deterministic policy engine `(role, capability) → GRANT / REQUIRE_APPROVAL / DENY`. Never calls the model. |
| `fleet/layers/gateway.py` | Capability Gateway: `request_authority`, root-signed cert auth, signed deny events, idempotency. |
| `fleet/layers/handoff.py` | Signed cross-agent handoff envelopes; D8 separation (R→raw evidence, A→qualified intel). |
| `fleet/layers/runtime.py` | Runtime lifecycle (03.7) + checkpointing + idempotency; `Researcher`/`Analyst`/`Operator` workers; `Approval` (D17). |
| `fleet/layers/armor.py` | Model Armor (D12): injection strip, signed tool envelopes, PII scan/redact. |
| `fleet/layers/verification.py` | D16 verification gate: `VERIFIED` / `ASSERTED` / `HALLUCINATION`. |
| `fleet/layers/brain.py` | Pluggable Brain interface: `GemmaBrain` (local, D18) / `GeminiBrain` (demo-only, D18/D20) / `SchemaEnforcedBrain` (D15 boundary). |
| `fleet/layers/approval.py` | D21 A1/A2: `verify_approval` — Ed25519-verifies + binds the human `ApprovalRecord` to exact action/capability/artifact (fail-closed). |
| `fleet/layers/compliance.py` | D21 E1 (D22): selective-disclosure compliance attestation — Ed25519-signed proof that an action complied + was human-approved + under live epoch, without revealing CRM/source data (not a zero-knowledge proof). |
| `fleet/layers/consensus.py` | D21 E2 (D23): multi-brain consensus gate — two distinct Brain backends must agree to VERIFY; disagreement → ASSERTED + signed event. |
| `fleet/gcp/` | `GcpBridge` (Firestore/Pub-Sub mirror), `FirestoreVerifier` (public-key), `OtelExporter`, D17 Cloud Run approval console. |
| `fleet/tests/` | 125 tests across Phases 0–5 + D21 hardening + Round-2 extensions (R1–R4). |
| `docs/planning/` | Living design docs: D1–destructure decision ADRs, D21 security audit + hardening, D22 selective-disclosure attestation, D23 consensus gate, D25 Operator-sandbox re-eval. (D24 = real-ZK variant scoped but intentionally unimplemented — see D22.) |

## Quick start

```bash
# 1. create an environment (Python 3.11+)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. run the full suite (all phases)
python -m pytest fleet/tests -q
```

All **125 tests** should pass. The vendored ChrisCryptSN suite also runs green
against this same environment.

## Security properties (tested across Phases 0–5)

- **Root of trust:** an Argon2id-strengthened master derives a root Ed25519 key;
  every agent identity is a root-signed certificate. A forged/unsigned cert is
  rejected by the gateway (beat 7).
- **Confidentiality:** local secrets are sealed with XChaCha20-Poly1305 under
  per-record HKDF subkeys (key-bound, name-bound — no plaintext fallback).
- **Tamper-evidence:** the audit ledger is an Ed25519-signed hash chain with a
  signed checkpoint, so any modification, reordering, or truncation is detected
  at verify time (fail-closed) — beat 6.
- **Deterministic authority:** policy + capability + signing live in the
  Control Plane, never in the model. The model proposes; the protocol decides.
- **Probabilistic-content separation (D15):** brain prompts carry evidence only,
  never policy/approval vocabulary; model output is schema-enforced at the
  boundary before it becomes any record.
- **Human-in-the-loop (D17):** consequential actions (`crm_write`) require a
  human-signed `ApprovalRecord` even for verified intel — beat 3 blocks without
  one, beat 4 grants with one.
- **Live rotation (D14):** an agent's key can be revoked and re-issued while the
  chain stays continuous — beat 8.
- **Public verifiability:** GCP holds only signed, verifiable artifacts; a
  public-key holder can verify any record without ever holding authority.

### D21 security audit hardening (added after audit)

- **Cryptographically bound human approval (A1/A2):** `Operator.act` now
  fails-closed — a consequential action runs only if the human `ApprovalRecord`
  is a genuine Ed25519 signature binding to the *exact* action id +
  capability + artifact hash. Forged, rebound, or reused approvals are rejected.
- **Root key backup + rotation + verifier continuity (K1):** the root seed is
  exportable only as an encrypted blob (never plaintext), restorable solely
  with the correct KEK + master (fail-closed); rotation re-signs live certs and
  keeps historical certs verifiable under their epoch's public key.
- **Revoke/rotate invalidates live grants (A3):** the Gateway idempotency cache
  re-validates cert liveness on replay and drops a grant the moment its cert is
  revoked or the root rotates — a revoked agent cannot replay an old token.
- **Deep Model Armor (M1/M2):** injection stripping and PII redaction recurse
  through nested structures and run at the evidence boundary (Researcher), so
  PII never reaches the analyst/operator/ledger.
- **Default-deny by property (P1):** an exhaustive property test asserts every
  unknown `(role, capability)` pair is DENIED — no silent allow.
- **Console fails closed (G2):** the Cloud Run approval console rejects any
  approval it cannot cryptographically verify; with no verifier wired it rejects
  *all* approvals rather than trusting.
- **Pinned, audited supply chain (S1):** locked dependency versions on **both**
  dependency surfaces (base + GCP), a CycloneDX SBOM uploaded as a build
  artifact, and a `pip-audit` CI gate (fail-closed) run as a matrix over both
  lockfiles.
- **Replay defense documented + tested (C3):** the signed hash-chain detects a
  re-inserted historical entry (broken position + chain link), fail-closed.

### D21 extensions (verifiable without trusting the model further)

- **Selective-disclosure compliance attestation (E1 / D22):** an Operator proves
  "this action complied with policy X, had a valid human approval, and was rooted in
  the live identity epoch" *without revealing the CRM/source data or the raw
  approval signature*. The verifier checks the math, not the data; a
  tampered/rebound/forged attestation is rejected. (Honestly named: this is a
  signed selective-disclosure attestation, **not** a zero-knowledge proof — the
  action's `policy_id`/`artifact_hash` are revealed by design.)
- **Multi-brain consensus gate (E2 / D23):** a VERIFIED-tier claim requires two
  *distinct* Brain backends to agree; disagreement downgrades to ASSERTED and
  emits a signed `consensus.disagreement` audit event (D16 escalation). A task
  with no verdict-field mapping emits a distinct, louder
  `consensus.unmapped_task` event instead of silently masquerading as a
  permanent disagreement (R2). The model stays proposal-only; the deterministic
  gate decides.

## Adversarial 8-beat governability demo (Phase 5)

Each beat is a passing automated test (`fleet/tests/test_adversarial_beats_phase5.py`):

1. Prompt injection stripped at the structured boundary (Model Armor)
2. Capability denial → Gateway DENY + signed deny event
3. Consequential action without approval blocked pre-FINAL
4. Human-signed `ApprovalRecord` grants authority
5. Execution succeeds; artifact signed, chained, replicated
6. Post-hoc audit edit detected by the hash-chain verifier
7. Forged identity (not signed by root) rejected
8. Revoke + rotate: fresh key, chain intact

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
