# Sovereign Enterprise Agent Fleet — Master Submission Document

> Single combined reference for judges + implementers. Generated from the living planning docs (`00-INDEX.md` onward). **Implementation complete: 205 tests passing on `main` (commit 764aff5); D26/D27/D28 shipped and tested.**

## 1. Executive Summary
See `18-executive-summary.md`. Thesis: intelligence probabilistic, authority/execution/evidence/audit deterministic + verifiable. Principle: do not trust the model — trust the execution protocol.

## 2. Project Vision
A coordinated agent fleet that is autonomously capable yet cryptographically governable — every consequential action is issued authority by a deterministic protocol, evidenced, signed, and hash-chained, and tampering/forgery are detectable by any holder of the public keys.

## 3. Problem Statement
Enterprise agents are either chatbots (talk, don't act) or unauditable autonomous systems. Enterprises can't adopt them because they can't answer: which agent, under what authority, using what evidence, has the record been altered? The Fortified Enterprise Fleet track exists for exactly this.

## 4. Goals / Non-Goals
See `02-goals-nongoals.md`. Goals: multi-agent autonomy, governability, verifiability, full hackathon compliance, local-first sovereignty, judgeable docs, Gemma bonus. Non-goals: production deployment, novel crypto, probabilistic security classifiers, real PII, live-at-judging.

## 5. Hackathon Requirements Mapping
See `09-hackathon-mapping.md`. All mandatory met: Gemini 3.5 Flash, GenAI SDK, Cloud Run+Firestore+Pub/Sub, Fortified Enterprise Fleet (7 components), repo+README+diagram+video. Bonus: local Gemma4 + blog + social.

## 6. System Architecture
See `03-architecture.md`. Control Plane (deterministic infra: Identity Root, Registry, Policy/Gateway, Runtime, Memory Bank, Model Armor, Observability) above 3 fleet workers (Researcher/Analyst/Operator). Hard handoff schema enforces R→A→O boundary. Topology: local authority/keys, GCP verifiable artifacts.

## 7. Agent Architecture
- Researcher: emits `SourcedEvidence` (citation+extract+source_hash+provenance); forbidden from judging.
- Analyst: emits `QualifiedIntel` (predicates + confidence + evidence_refs); verification gate D16.
- Operator: prepares artifacts; executes approved consequential actions.
- Control Plane is NOT a fleet agent (D9). Fleet requests authority; protocol grants/denies.

## 8. Sovereign Worker Integration
Reuse Sovereign runtime, lifecycle (REQUEST→…→AUDIT), policy enforcement, persistent encrypted state. ChrisCryptSN provides all crypto. No rewrite (D4).

## 9. Control Plane Specification
Identity Root (root-of-trust, certs, revocation, rotation) · Registry (publish/version/discover) · Gateway (capability-based authority) · Runtime (checkpointed lifecycle) · Memory Bank (encrypted + Firestore manifest mirror) · Model Armor (structural guardrails) · Observability (OTel ledger+traces).

## 10. Identity Model
Per-agent Ed25519 keypair; root signs `AgentCert { pubkey, role, capabilities, expiry, cert_seq, root_sig }` (12.1). Human approver has own root-certified identity (D17). Forged = unsigned-by-root → reject.

## 11. Authorization / Policy Model
Capability-based. Gateway evaluates `AgentCert.capabilities` + policy; never calls Gemini. Deny emits signed event. Unauthorized op = capability never issued (not "tries and gets blocked").

## 12. Cryptographic Architecture
See `05-cryptographic-design.md`. Hierarchy: Argon2id root → root Ed25519 → per-agent Ed25519 → HKDF per-record XChaCha20. Encrypt confidential state; sign evidence/audit/certs/envelopes; hash-chain audit (SHA-256 prev_hash). Nonce 24-byte per record; session/device binding. Live rotation (D14).

## 13. Threat Model
See `04-security-model.md` + `06-failure-model.md`. 7 properties distinct; 13 failure modes each owned by a layer. Content correctness (Verification) ≠ integrity (signature+hashchain).

## 14. Evidence Model
`SourcedEvidence` (Researcher) → `QualifiedIntel` (Analyst, cites refs) → `ApprovalRecord` (human) → `AuditEntry` (hash-chain). Every record content-addressed + signed; canonical serialization (12.7).

## 15. Audit / Event Model
`AuditEntry { seq, prev_hash, event{who,what,when,why,policy,tool,evidence_refs,result,verified,approved_by}, body_hash, sig }`. Tamper = `SHA256(entry) != next.prev_hash`. Verifiable by public key; replicated to Firestore.

## 16. Knowledge Architecture
See `11-knowledge-architecture.md`. SKC/GraphRAG/vectors serve the Analyst (judge), not Researcher. Graph stays local (D19); Firestore mirrors manifest-only (hashes+refs). Provenance in `source_hash`.

## 17. Google / ADK / Gemini Integration
Gemini 3.5 Flash = brain only (D15); GenAI SDK direct (D20); GCP Cloud Run/Firestore/Pub/Sub (D5). Local-first authority (D3/D6). Dev on local abliterated Gemma4 (D18).

## 18. Cloud Architecture
Local Sovereign runtime → replicate signed artifacts to Firestore (ledger + manifest), Pub/Sub (handoffs), serve runtime/gateway/approval console from Cloud Run. Vertex AI hosts Gemini. GCP = verifiable storage, not authority.

## 19. Data Model
See `12-data-model.md` — field-level `AgentCert`, `SourcedEvidence`, `QualifiedIntel`, `ApprovalRecord`, `AuditEntry`, `ToolEnvelope`.

## 20. Interface Contracts
See `13-interface-contracts.md` — agent→gateway authority, agent→agent signed handoff, control-plane→GCP replication, Gemini brain-only, Gemma local, idempotency keys.

## 21. Failure Model
See `06-failure-model.md` — 13 modes → owning layer (Verification/Runtime/Pub-Sub/Gateway/Model Armor/Root/Hash-chain/Operator lifecycle).

## 22. Adversarial Test Plan
See `07-adversarial-test-plan.md` — 8 runnable beats: injection blocked, capability denied, approval gated, execution signed, tamper detected, forged identity rejected, revoke→rotate→resume.

## 23. Demonstration Script
See `08-demo-script.md` — ICP scenario R→A→O + Registry beat; ≤4-min video shot plan; GCP console proof; local Gemma4 bonus.

## 24. Testing Strategy
See `14-testing-strategy.md` — every beat + failure mode provably tested (unit crypto, protocol, Model Armor, verification gate, adversarial E2E, tamper, forged/rotation, GCP verifier).

## 25. Implementation Roadmap
See `15-implementation-roadmap.md` — 6 phases over ~17 days; critical path = Gateway + verification gate; cost discipline (dev on Gemma4).

## 26. Risk Register
See `16-risk-register.md` — R1–R15; accepted scope boundaries (single root, simulated CRM, not-live-at-judging).

## 27. Judging / Submission Strategy
See `17-judging-submission-strategy.md` — criteria alignment, submission artifacts, bonus capture, secondary Architecture target, recording checklist, anti-patterns.

## Decision Log (D1–D20)
See `10-decisions-ADR.md`. All Accepted. Key: track=Fortified Fleet+Architecture; Gemini brain-only; local-first; reuse ChrisCrypt/Sovereign; GCP trio; hard R→A→O handoff; structural Model Armor; root-of-trust + live rotation; verification gate (D16); human cert approval (D17); local Gemma4 dev brain (D18); graph local (D19); GenAI SDK direct (D20).

## Open / action items
- Verify GCP project ID `project-3ba93cec-8ca6-43c0-ba4` against console before video (R14).
- Broad admin IAM documented as dev-only (R13); fleet identity least-privilege.
- Conservative credit use; Gemini only at final demo (R15).
