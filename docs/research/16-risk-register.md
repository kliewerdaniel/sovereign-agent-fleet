# 16. Risk Register

| ID | Risk | Likelihood | Impact | Mitigation | Status |
|----|------|-----------|--------|------------|--------|
| R1 | GCP credit not claimed in time | Med | High (no deploy proof) | Owner action day 1; fallback: free tier / local-only + doc proof | Open |
| R2 | ADK wrapping unclear (13.6 open Q) | Med | Med | Confirm at Phase 4 start; Sovereign can call Gemini directly if ADK blocks | Open |
| R3 | Local-first vs GCP boundary leak (key crosses cloud) | Low | Critical | Enforce in 13.3: only signed/verifiable artifacts replicate; code review gate | Mitigated by D3/D6 |
| R4 | Hash-chain perf on large ledger | Low | Low | Ledger small for demo; append-only; walk incremental | Accept |
| R5 | Gemini rate/cost over $150 | Med | Med | Brain-only calls; cache; cost cap; not live at judging | Mitigated |
| R6 | Verification threshold too strict → few VERIFIED | Med | Med | 0.6 + weights tunable (D16); demo data curated to pass | Mitigated |
| R7 | Model Armor PII scanner misses novel PII | Med | Med | Deterministic allow/deny + format; demo data synthetic; no real PII | Mitigated |
| R8 | Nonce reuse bug in XChaCha20 | Low | Critical | Runtime enforces unique (key,nonce); test 14.1 | Mitigated |
| R9 | Root key compromise | Low | Critical | Argon2id + device secret; out of MVD scope to rotate root; documented boundary (05.9) | Accepted boundary |
| R10 | Video > 4 min / GCP proof missing | Med | High | Script 08.2; console screens mandatory; trim adversarial if needed | Open |
| R11 | Deadline slip (~17 days) | Med | High | Critical path = Phase1/2; drop Gemma/blog before adversarial | Mitigated |
| R12 | Forged-identity demo not convincing | Low | Med | Use unsigned-by-root cert (D13); show Gateway reject on screen | Mitigated |
| R13 | Broad admin IAM on single GCP account (least-privilege inconsistency) | Low | Med | Pragmatic for solo hackathon; note in writeup that fleet identity uses least-privilege, infra account is dev-only | Accepted (documented) |
| R14 | GCP project ID typo in docs / console mismatch | Low | Med | Verify exact ID `project-3ba93cec-8ca6-43c0-ba4` against console before video | Open |
| R15 | Gemini credit exhaustion before demo | Med | High | Dev on local Gemma4 (D18); Gemini only at final demo; cost cap | Mitigated |

## Scope boundaries (explicitly accepted, not risks)
- Single root trust (no threshold/mesh). Documented (05.9).
- Simulated CRM (no real sends/PII). D11.
- Not live at judging (rules allow). 09.
