# 14. Testing Strategy

Goal: every adversarial beat + every failure mode is **provably** reproducible by an automated test, so the demo is not "we clicked and it worked" but "the protocol enforces this by construction."

## 14.1 Unit (crypto + protocol, no model)
- Key hierarchy: Argon2id→root→agent keypair derivation matches spec (05).
- Sign/verify: valid sig verifies; 1-bit flip fails.
- Hash-chain: walk passes on intact ledger; fails at altered seq.
- HKDF per-record key: different record → different key; same record salt → stable key.
- Nonce: duplicate `(key,nonce)` rejected by Runtime.

## 14.2 Protocol (authority + handoff)
- Capability deny: agent without `crm_write` → `request_authority` returns `granted=false` (beat 2).
- Handoff schema: Analyst emitting `QualifiedIntel` with `evidence_ref` to missing/revoked evidence → rejected.
- Operator consuming `HALLUCINATION` intel → blocked (D16).
- Researcher emitting `classification` field → rejected (capability separation D8).

## 14.3 Model Armor (D12)
- Prompt injection: tool result containing instruction string → stripped; only structured fields reach model; no exfil call emitted (beat 1).
- Tool poisoning: `ToolEnvelope` with bad `tool_sig` → blocked before model (failure #7).
- PII: outbound artifact containing detected PII pattern → blocked/redacted; not in plaintext log.

## 14.4 Verification gate (D16)
- Claim with ≥2 valid refs, confidence≥0.6 → `VERIFIED`.
- Claim with 1 ref, confidence<0.6 → `ASSERTED` (requires approval).
- Claim with 0 refs → `HALLUCINATION` flag, not recorded.
- Stale ref (>30d) → `staleness_ok=false`, confidence discounted.

## 14.5 Adversarial E2E (beats 1–8, 07)
- Each beat scripted as a pytest fixture; asserts the expected Gateway/Verification outcome + that the corresponding AuditEntry was chained.

## 14.6 Tamper detection
- Fixture: take a valid ledger, flip one `AuditEntry` body, re-run verifier → assert failure located at that seq; unaltered entries still verify (beat 6).

## 14.7 Forged identity / rotation (D13/D14)
- Present `AgentCert` not signed by root → Gateway reject (beat 7).
- Revoke + re-issue cert; assert post-rotation actions sign under new key + verify; pre-rotation entries legacied (beat 8).

## 14.8 Integration (GCP)
- Deploy to Cloud Run/Firestore/Pub/Sub; assert replicate() writes verifiable docs; assert verifier run *against Firestore copy* (using only public keys) reproduces tamper detection — proves GCP holds verifiable data, not authority.

## 14.9 Coverage gate
- All 13 failure modes (06) + 8 adversarial beats (07) have a passing automated test before the demo is recorded.
