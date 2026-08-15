# 4. Security Model

## 4.1 The seven distinct properties (never conflated)
| Property | Question it answers | Mechanism |
|----------|--------------------|-----------|
| **Authentication** | Is this agent who it claims? | Ed25519 identity + root-of-trust cert (D13) |
| **Authorization** | Is this agent allowed this action? | Capability-based policy at Gateway (D9) |
| **Encryption** | Is confidential state unreadable at rest/in transit? | XChaCha20-Poly1305 per-record keys (D13) |
| **Integrity** | Has this record been altered? | SHA-256 hash-chain over audit ledger |
| **Provenance** | Which agent produced this, under what authority? | Signed evidence/audit records citing capability + policy ID |
| **Non-repudiation** | Can the agent deny it did this? | Ed25519 signature verifiable by any holder of public key |
| **Auditability** | Can we reconstruct the full event history? | OTel-compliant audit ledger + reasoning traces |

## 4.2 Threat model
| Threat | Vector | Defense (layer) |
|--------|--------|-----------------|
| Prompt injection | malicious instruction in tool result / cross-agent msg | Model Armor: agents receive only schema-validated structured results; no free-text instruction execution surface (D12) |
| Tool poisoning | tampered/forged tool output | Signed tool envelope (tool ID + output hash + tool key); fail before model sees it (D12) |
| PII leak | sensitive field in outbound artifact / log | Deterministic allow/deny + format scanner over outbound; fields encrypted under ChrisCrypt, never plaintext (D12) |
| Unauthorized action | agent requests capability it lacks | Gateway capability-based deny; signed deny event (D9) |
| Forged identity | agent presents non-root-certified Ed25519 key | Cert validation at Gateway; reject (D13) |
| Compromised worker | key exfiltrated | Root revoke + live re-issue/rotation; old entries legacied (D14) |
| Audit tampering | post-hoc edit of a record | Hash-chain walk fails at altered entry; alert (D13) |
| Hallucination | model asserts unsupported claim | Verification layer: unsupported-claim detection vs cited evidence (content correctness, distinct from integrity) |
| Replay / duplicate | Operator write replayed | Idempotency keys on consequential writes |
| Stale/conflicting evidence | old source reused | Analyst confidence + provenance timestamps; staleness flag |

## 4.3 Model Armor — structural + deterministic (D12) [the one genuine gap we designed]
No probabilistic classifier. Three sub-threats, three structural controls:
1. **Prompt injection** — agents only receive *structured tool results* (schema-validated). Cross-agent messages carry a signed sender identity the receiver must verify. An injected "ignore previous instructions" string has no execution surface because the protocol never executes free-text as instruction.
2. **Tool poisoning** — every tool result wrapped in a signed envelope `(tool_id, output_hash, tool_sig)`. A tampered or forged output fails signature verification *before* the model is shown it; the Runtime logs the failure as evidence.
3. **PII leaks** — deterministic allow-list/deny-list + regex/format scanner over *outbound* artifacts (Operator outreach, audit-exposed fields). Sensitive fields stored encrypted under ChrisCrypt; plaintext never written to logs or ledger.

## 4.4 Authentication vs Authorization vs Encryption (explicit separation)
- The **root key** authenticates *identities* (signs certs). It does **not** authorize actions.
- **Authorization** is a separate capability set the Gateway evaluates per action, independent of who signed.
- **Encryption** keys (per-record XChaCha20) are derived separately from signing keys; a signing key compromise does not expose encrypted state, and vice versa.

## 4.5 Trust roots
- Single Control Plane **root key** (the only trust anchor). It certifies agent identities and signs revocation/rotation lists.
- All verification reduces to: "is this signature valid under a key certified by root, and is that cert unrevoked?"
