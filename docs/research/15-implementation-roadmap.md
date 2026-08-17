# 15. Implementation Roadmap (~17-day build plan)

Deadline Aug 31 2026 5pm PDT. Phases are sequential; testing is continuous (14). Reuse over build (D4).

## Phase 0 — Foundation (days 1–2)
- Claim $150 GCP credit (owner action item, outstanding).
- Wire ChrisCrypt into repo as a module: Argon2id root, Ed25519 agent keys, HKDF per-record, XChaCha20, SHA-256 hash-chain.
- Define canonical serialization (12.7). Write crypto unit tests (14.1).
- **Gate:** all 14.1 tests green.

## Phase 1 — Control Plane (days 3–5)
- Identity Root: issue/sign `AgentCert` (12.1); revocation + rotation lists (D13/D14).
- Gateway: `request_authority` (13.1) capability eval; signed deny events.
- Policy set for R/A/O/human.
- Tests: 14.2 capability deny + handoff schema + D8 separation.

## Phase 2 — Runtime + Handoff (days 6–8)
- Sovereign lifecycle state machine (03.7) with checkpointing (failure #11/#13).
- Researcher → Analyst → Operator agents emitting 12.2/12.3/12.4.
- Model Armor (12.6, 04.3): structured tool results + signed envelopes + PII scan.
- Analyst verification gate (D16) implemented + tested (14.4).
- Tests: 14.2/14.3/14.4.

## Phase 3 — GCP + Observability (days 9–11)
- GCP already provisioned by owner (project `project-3ba93cec-8ca6-43c0-ba4`, service-account admin). Deploy conservatively (min instances 0).
- Cloud Run: runtime + gateway + approval console (D17).
- Firestore: ledger + Audit Ledger ("Memory Bank") mirror (manifest-only, opt-in).
- Pub/Sub: async handoffs + idempotency (failure #3/#12).
- OTel export of audit + reasoning traces (03.2 #7).
- Tests: 14.8 (verifier against Firestore copy).

## Phase 4 — Gemini + Gemma (days 12–13)
- GenAI SDK direct Gemini 3.5 Flash calls (D20), brain-only (D15), schema-validated. Used for the submission demo only.
- Dev/test used local abliterated Gemma4 across ALL R/A/O use cases (D18) — free, controllable, no credit burn.
- Gemma bonus: local Gemma4 is the dev brain; document as Gemma integration (D2/D18).
- Tests: brain output schema enforcement (same tests pass for both models via pluggable interface).

## Phase 5 — Adversarial + Video (days 14–16)
- Script all 8 beats as pytest fixtures (14.5/14.6/14.7).
- Record 4-min video per 08.2 (optional GCP replication proof; default runtime is local-first).
- Architecture diagram render.

## Phase 6 — Submission (day 17)
- Repo + shares (testing@devpost.com, cloudhackathons@google.com).
- README spin-up (local + deploy). Final doc package assembly.
- Optional: blog + social #AllThingsAgenticHackathon.

## Critical path
Phase 1 Gateway + Phase 2 verification gate are the hard core; everything else attaches to them. If slipping, drop Gemma bonus + blog before dropping adversarial beats.

## Cost discipline
Dev entirely on local Gemma4 (D18) — zero Gemini spend until the final demo. Gemini calls capped; Cloud Run min instances 0; Firestore tiny; not live at judging. If budget tightens, drop blog + social bonus before anything else.

## Reuse checklist (do not rebuild)
- [ ] ChrisCrypt: Argon2id, XChaCha20, HKDF, Ed25519, hash-chain, device sessions
- [ ] Sovereign Worker: runtime, lifecycle, policy, persistent state
- [ ] SKC/GraphRAG: Analyst knowledge (11)
