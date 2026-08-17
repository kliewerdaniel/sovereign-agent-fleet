# Sovereign Enterprise Agent Fleet — Executive Summary

## One-line thesis
> **An enterprise agent fleet in which intelligence is probabilistic, but authority, execution, evidence, and audit are deterministic and cryptographically verifiable.**

Central principle: **Do not trust the model. Trust the execution protocol.** The model may propose plans, actions, and interpretations; the deterministic Control Plane decides authority, permission, required evidence, required verification, required approval, what is recorded, and how the event is cryptographically protected.

## What we built (planned)
A **Fortified Enterprise Fleet** (hackathon track) of three worker agents — **Researcher → Analyst → Operator** — coordinated by a deterministic Control Plane and bound by explicit identity, policy, evidence, verification, approval, and audit. Private keys, encrypted secrets, and signing never leave the local Sovereign runtime; only signed, verifiable artifacts replicate to Google Cloud.

## Why it matters
Enterprises cannot adopt agentic automation because they cannot answer: *which agent did this, under what authority, using what evidence, and has the record been altered?* Our fleet answers all four cryptographically, and proves it is **governable, not just autonomous** via an 8-beat adversarial demo (injection blocked, capability denied, approval gated, execution signed, tamper detected, forged identity rejected, compromised worker revoked + rotated).

## Architecture in one diagram
```
LOCAL (sovereign, keys never leave)          GCP (verifiable artifacts, no authority)
ChrisCrypt: root key, agent Ed25519,           Cloud Run   → runtime+gateway+approval console
  per-record XChaCha20                        Firestore   → tamper-evident ledger + manifest mirror
Sovereign Control Plane (Identity/Policy/      Pub/Sub     → async handoffs + idempotency
  Gateway/Runtime/Memory/Model Armor)          Gemini      → cloud brain, demo-time only (GCP opt-in, default local)
Researcher→Analyst→Operator (Gemini/Gemma)         ▲ signed evidence + hash-chain replicate OUT
```
Public vocabulary maps 1:1 to the hackathon's 7 Fleet components (Registry, Runtime, Memory Bank, Identity, Gateway, Model Armor, Observability) — "Memory Bank" is the Audit Ledger in current code.

## Security properties (kept distinct)
Authentication (Ed25519 + root cert) · Authorization (capability policy) · Encryption (XChaCha20 per-record) · Integrity (SHA-256 hash-chain) · Provenance (signed evidence citing capability+policy) · Non-repudiation (Ed25519 verifiable by public key) · Auditability (OTel ledger + traces). Model Armor is **structural + deterministic** — no probabilistic classifier.

## Hackathon fit (all mandatory requirements met, architecturally)
- **Gemini 3.5 Flash** — probabilistic brain inside R/A/O; never for policy/signing (D15).
- **GenAI SDK** — Google agent framework (Gemini API direct; Sovereign = orchestration) (D20).
- **GCP** — Cloud Run + Firestore + Pub/Sub, deployed + proven in video.
- **Fortified Enterprise Fleet** — all 7 components implemented via Sovereign/ChrisCrypt reuse.
- **Bonus** — local abliterated Gemma4 as the dev/test brain across all use cases (D18), plus optional blog + social.

## Reuse, not rewrite
ChrisCryptSN (Argon2id, XChaCha20-Poly1305, HKDF, Ed25519, signed hash-chain, device sessions) and Sovereign Worker (runtime, lifecycle, policy, state) are reused as modules. Only Model Armor + OTel export are net-new. No cryptographic primitives invented.

## Demo
One scenario — *qualify 20 ICP-fit prospects and prepare simulated outreach* — executed R→A→O, plus the 8-beat adversarial segment, in a ≤4-min video showing the GCP console as deployment proof.

## Status
Planning/docs phase complete. 20 decisions (D1–D20) recorded as ADRs. No implementation code written (documentation-first rule). GCP provisioned (project `project-3ba93cec-8ca6-43c0-ba4`); credits used conservatively — dev on local Gemma4, Gemini only at final demo.
