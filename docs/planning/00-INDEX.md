# Sovereign Enterprise Agent Fleet — Planning Package (LIVING)

> **Status:** IMPLEMENTATION COMPLETE — all phases built, hardened, and merged to `main`. This package is the living design record (D1–D25) for the shipped code under `fleet/`.
> **Track:** Fortified Enterprise Fleet (primary) + Best Architectural Design (secondary judging target).

## Reading order (FULL — first + second pass complete)
1. `01-project-brief.md` — what we're building and why
2. `02-goals-nongoals.md` — in/out of scope
3. `03-architecture.md` — system, agent, control-plane, topology
4. `04-security-model.md` — the 7 security properties + threat model + Model Armor
5. `05-cryptographic-design.md` — exact keys, signatures, hashes, derivation, rotation
6. `06-failure-model.md` — behavior for each failure mode
7. `07-adversarial-test-plan.md` — the runnable 8-beat governability demo
8. `08-demo-script.md` — the 4-min video shot plan + ICP scenario
9. `09-hackathon-mapping.md` — requirements → implementation checklist
10. `10-decisions-ADR.md` — every decision in ADR format (D1–D17)
11. `11-knowledge-architecture.md` — where SKC / GraphRAG / vectors fit
12. `12-data-model.md` — field-level record schemas
13. `13-interface-contracts.md` — agent/gateway/GCP/Gemini/Gemma contracts
14. `14-testing-strategy.md` — every beat + failure mode provably tested
15. `15-implementation-roadmap.md` — ~17-day build plan
16. `16-risk-register.md` — risks + accepted scope boundaries
17. `17-judging-submission-strategy.md` — criteria, submission, bonus
18. `18-executive-summary.md` — one-page thesis + hackathon fit
19. `19-MASTER-SUBMISSION.md` — single combined doc (all 27 sections)
20. `D21-security-audit.md` — security audit + Round-1 hardening (A1/A2, K1, A3, M1/M2, P1, G2, S1, C3) + Round-2 follow-up (R1–R4)
21. `D22-zk-policy-proof.md` — selective-disclosure compliance attestation (honestly named; real-ZK variant scoped as D24, unimplemented)
22. `D23-multi-brain-consensus.md` — two-brain consensus gate
23. `D25-operator-sandbox.md` — Operator-sandbox re-evaluation + deferral (R4)

## Status
- **PHASE 0 COMPLETE** — crypto foundation built + 22 tests green (14.1). Fleet code under `fleet/` (clean-room, BSD/MIT-compatible; the public hackathon repo).
- Reuse: vendored `ChrisCryptSN` (MIT) into `fleet/crypto/chriscrypt` — Argon2id, XChaCha20-Poly1305, HKDF per-record, Ed25519 signed hash-chain. All 12 upstream tests + 22 new tests pass.
- **Deviation D4a:** Sovereign Worker control plane NOT vendored — its repos are all-rights-reserved (no license). Audit-ledger wrapper + Gateway written clean-room. Documented below.
- GCP live (project `project-3ba93cec-8ca6-43c0-ba4`); dev on local Gemma4, Gemini at demo only; conservative credits.
- **PHASE 4 COMPLETE** — Pluggable Brain (Gemini 3.5 Flash + local Gemma4) + schema enforcement built + 10 tests green, 69 total. `fleet/layers/brain.py`: `Brain` interface + `DeterministicBrain`/`GemmaBrain` (local, D18)/`GeminiBrain` (GenAI SDK direct, demo-only D18/D20)/`SchemaEnforcedBrain` (D15 boundary validation); prompts evidence-only, no policy leakage (D15). Workers `classify_with_brain`/`draft_with_brain` let the model PROPOSE, protocol decides.
- **PHASE 5 COMPLETE** — Adversarial 8-beat governability demo (beats 1–8 + registry setup) as 9 passing pytest fixtures (`fleet/tests/test_adversarial_beats_phase5.py`); full suite **78 tests green**. Dark-first architecture diagram (`docs/assets/architecture.svg` + `.png`). 4-min narrated demo video (`demo/sovereign_agent_fleet_demo.mp4`) assembled from real artifacts: live pytest beat output, `GcpBridge`/`FirestoreVerifier` public-key proof, and the pluggable-brain schema boundary. GCP not live in demo (min-instances 0); identical local code path used and labeled.
- All phases complete. Repo: **125 tests** (Phases 0–5 + D21 hardening + Round-2 extensions R1–R4), planning package (D1–D25), diagram, demo video.
- **D21 SECURITY AUDIT + HARDENING (complete):** A1/A2 cryptographic approval binding, K1 root-key backup/rotation, A3 revoke-invalidates-grants, M1/M2 deep Model Armor, P1 default-deny property, G2 console fails-closed, S1 pinned+audited supply chain, C3 replay defense. Full suite green.
- **Round 2 hardening (complete, merged `b03de66`):** **R1** renamed the D22 "zero-knowledge" claim to an honest *selective-disclosure compliance attestation* (scoped real-ZK as D24, unimplemented); **R2** split consensus into `consensus.disagreement` vs `consensus.unmapped_task`; **R3** CI now audits BOTH dependency surfaces (base + GCP) and uploads the SBOM as an artifact; **R4** re-evaluated and deferred (again, with reason) the Operator sandbox in **D25** — no external tool surface exists to sandbox, and the real capability boundary (Gateway + A1/A2) is already fail-closed.

## Second pass (now written)
Data Model ✅, Interface Contracts ✅, Testing Strategy ✅, Implementation Roadmap ✅, Risk Register ✅, Judging/Submission Strategy ✅.

## Decision log (summary — full text in 10-decisions-ADR.md)
| ID | Decision | Status |
|----|----------|--------|
| D1 | Track = Fortified Enterprise Fleet (+ Architecture secondary) | Accepted |
| D2 | Gemini 3.5 Flash mandatory; Gemma locally for bonus | Accepted |
| D3 | Crypto + execution protocol stay local-first; Gemini/ADK = cloud brain only | Accepted |
| D4 | Reuse ChrisCrypt + Sovereign modules, don't rewrite | Accepted |
| D5 | GCP = Cloud Run + Firestore + Pub/Sub | Accepted |
| D6 | Authority/keys local; verifiable artifacts replicate to GCP | Accepted |
| D7 | Public vocab = hackathon 7 components → Sovereign impl | Accepted |
| D8 | Hard handoff: Researcher=sourced evidence; Analyst=qualified intel | Accepted |
| D9 | Control Plane = deterministic infra, not fleet agents | Accepted |
| D10 | 3 executing workers; Registry discovery shown as setup beat | Accepted |
| D11 | Demo = simulated DailySalesOS CRM, no real sends/PII | Accepted |
| D12 | Model Armor = structural + deterministic (no classifier) | Accepted |
| D13 | Key hierarchy + root-of-trust certifies each agent identity | Accepted |
| D14 | Live key rotation in scope (revoke + re-issue + resume) | Accepted |
| D15 | Gemini = probabilistic brain only; never for policy/signing | Accepted |
| D16 | Verification gate quantifies VERIFIED vs ASSERTED (weights + 0.6 + hallucination flag) | Accepted |
| D17 | Human approver = root-cert Ed25519 id; approval console on Cloud Run, key local | Accepted |
| D18 | Local abliterated Gemma4 = dev/test brain all use cases; Gemini = demo brain | Accepted |
| D19 | Graph stays local; Firestore mirror = manifest-only | Accepted |
| D20 | Google framework = GenAI SDK direct; Sovereign = orchestration/enforcement | Accepted |

## Two precision corrections baked into the design
- **"Evidence is deterministic" is imprecise.** The *record* (hash/signature/chain position) is deterministic; the *content* a model extracts is probabilistic. Threat model splits **content correctness** (Verification layer) from **integrity** (signature+hashchain).
- **"Researcher tries unauthorized op → blocked" is weak** unless capability-based. The honest design: Gateway denies because the capability was never issued (optionally surfaced by a simulated prompt-injection). The adversarial demo is built on this.

## Open items carried forward
- Exact GCP region / cost guardrails (credits form not yet claimed — action for owner).
- Whether ADK agents wrap the local Sovereign runtime, or Sovereign runtime calls Gemini directly and ADK is the orchestration shell. (Recommend: ADK = outer orchestration/agent shell; Sovereign = inner deterministic protocol. To confirm in implementation phase.)
- Final record schemas (EvidenceRecord, AuditEntry, AgentCert) — specified structurally in 05 but field-level contract lands in Interface Contracts (second pass).
