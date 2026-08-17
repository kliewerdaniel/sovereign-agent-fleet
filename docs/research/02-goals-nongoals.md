# 2. Goals / Non-Goals

## Goals
1. Demonstrate a **multi-agent fleet** executing a real, multi-step enterprise workflow autonomously.
2. Prove the fleet is **governable**: policy denies unauthorized action, approval gates consequential action, and tampering/forgery are detected.
3. Show **cryptographic verifiability** of identity, evidence, and audit without trusting the model.
4. Satisfy **all mandatory hackathon requirements** (Gemini 3.5 Flash, ADK, ≥1 GCP service, Fortified Enterprise Fleet track components) with architecturally meaningful (not bolted-on) usage.
5. Preserve **local-first sovereignty**: keys/signing/encrypted secrets stay local; only verifiable artifacts go to cloud.
6. Make the architecture **documentable enough for a judge to follow** and reproducible from the repo.
7. Earn the **Gemma bonus** via an honest local sub-task.

## Non-Goals
1. **Not** a production-grade, internet-facing enterprise deployment. The demo CRM is simulated; no real sends.
2. **Not** a novel cryptographic primitive. We use established primitives (Argon2id, XChaCha20-Poly1305, HKDF, Ed25519, SHA-256) correctly — no inventions.
3. **Not** a probabilistic security classifier. Model Armor is structural/deterministic; we do not add an LLM-based injection detector to a security control.
4. **Not** full zero-trust mesh across arbitrary orgs. Single-tenant Control Plane with cross-department Registry discovery demonstrated as a setup beat.
5. **Not** real PII processing. Demo data is synthetic; PII controls are demonstrated structurally.
6. **Not** live at judging moment (allowed by rules) — only proof of GCP deployment required.
7. **Not** rewriting Sovereign Worker/ChrisCrypt. Reuse as modules (D4).
