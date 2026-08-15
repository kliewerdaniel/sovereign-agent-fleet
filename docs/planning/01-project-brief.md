# 1. Project Brief

## Vision
An enterprise agent fleet in which **intelligence is probabilistic, but authority, execution, evidence, and audit are deterministic and cryptographically verifiable.** Autonomous agents coordinate as a fleet while remaining bounded by explicit identity, authorization, policy, evidence, verification, approval, and audit.

## Problem
Today's enterprise agents are either (a) single chatbots that "talk" but don't act, or (b) autonomous systems whose actions are opaque, ungoverned, and unauditable. Enterprises cannot adopt agentic automation because they cannot answer: *which agent did this, under what authority, using what evidence, and has the record been altered?* The Fortified Enterprise Fleet track exists precisely because enterprises need agents that hook into production infra **without violating compliance, data sovereignty, or security policy.**

## Who it is for
- Enterprise platform/security teams evaluating agentic automation.
- The hackathon's Fortified Enterprise Fleet judging panel (primary audience for the demo + docs).

## Why multiple agents (not one)
A single agent that both *gathers*, *judges*, and *acts* concentrates authority and removes the verification boundary. Splitting into **Researcher → Analyst → Operator** creates enforceable handoffs: evidence is produced by one agent and *judged* by another under a different capability set, so no single probabilistic component holds gather+judge+act authority. The deterministic Control Plane sits *above* all of them and issues/denies authority per action.

## Why better than a conventional agent
- **Governable, not just autonomous.** Authority is issued by a protocol, not assumed by the model.
- **Verifiable.** Every consequential event is signed and hash-chained; tampering is detectable by anyone holding public keys.
- **Local-first sovereignty.** Private keys, encrypted secrets, and signing never leave the local runtime; only verifiable artifacts replicate to cloud.
- **Fail-safe.** Hallucination is caught by the Verification layer; tampering by the signature layer; unauthorized action by the Gateway — three independent mechanisms.

## Minimum Viable Demonstration (MVD)
One end-to-end scenario — *qualify 20 ICP-fit prospects and prepare simulated outreach* — executed by Researcher→Analyst→Operator, producing signed evidence + a tamper-evident audit ledger, plus an 8-beat adversarial segment proving the fleet is **governable** (injection blocked, capability denied, approval gated, tamper detected, forged identity rejected, compromised worker revoked + rotated).

## Reuse (do not rewrite)
- **Sovereign Worker** runtime, lifecycle (REQUEST→…→AUDIT), policy enforcement, persistent state.
- **ChrisCryptSN** primitives: Argon2id, XChaCha20-Poly1305, HKDF per-record keys, Ed25519, signed hash-chain, device-bound sessions, encrypted local state.
- **Sovereign Knowledge Compiler (SKC) / GraphRAG** for Analyst knowledge representation (see `11-knowledge-architecture.md`).
