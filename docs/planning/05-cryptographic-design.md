# 5. Cryptographic Design

> Established primitives only. No inventions. (Argon2id, XChaCha20-Poly1305, HKDF, Ed25519, SHA-256.)

## 5.1 Key hierarchy (D13)
```
Root KMS key
  └─ derived from: Argon2id(passphrase ‖ device_secret)   [never used directly to sign/encrypt]
       │
       ├─ CONTROL PLANE ROOT KEY (Ed25519)
       │     └─ signs each Agent Identity Certificate (root-of-trust)
       │     └─ signs Revocation List + Rotation List
       │
       └─ per-agent IDENTITY KEYPAIR (Ed25519, separated per worker)
             ├─ signs: evidence records, audit entries, cross-agent envelopes
             └─ derives per-record DATA KEY via HKDF(agent_priv ‖ record_salt)
                   └─ XChaCha20-Poly1305 encrypts confidential state (CRM draft, PII)
```
- Signing keys and encryption keys are **separate**; a signing-key compromise does not expose encrypted state.

## 5.2 What is encrypted / signed / hashed
| Artifact | Crypto op | Key |
|----------|-----------|-----|
| Confidential state (CRM draft, PII fields) | **Encrypt** XChaCha20-Poly1305 | per-record HKDF data key |
| Evidence record | **Sign** Ed25519 + **Hash** SHA-256 | agent identity key |
| Audit entry | **Sign** Ed25519 + **Hash** SHA-256 (commits to prev hash) | agent identity key |
| Agent identity | **Sign** Ed25519 (cert) | root key |
| Tool result envelope | **Sign** Ed25519 (envelope) | tool key |
| Cross-agent message | **Sign** Ed25519 (envelope) | sender agent key |
| Revocation / rotation list | **Sign** Ed25519 | root key |

## 5.3 Hash-chain (audit integrity)
- Each `AuditEntry` contains `prev_hash = SHA-256(prev_entry)`. Genesis entry uses a fixed root anchor signed by root.
- Verification = walk chain; recompute each `SHA-256(entry)` and compare to `next.prev_hash`. First mismatch → tamper located at that entry.
- Altered record → next entry's `prev_hash` no longer matches → break detected (adversarial beat 6).

## 5.4 Identity lifecycle (D13/D14)
- **Issue:** root signs `AgentCert { agent_id, pubkey, capabilities, expiry, root_sig }`.
- **Verify:** Gateway checks `root_sig` valid + cert unrevoked + capabilities cover requested action.
- **Revoke:** root appends `agent_id` to signed Revocation List; Gateway checks on every action. Existing chain entries stay (legacied), new entries under that key rejected.
- **Rotate (live, D14):** root issues a **new** `AgentCert` (new keypair) for the worker; old cert revoked; new records sign under new key; chain continuous. Compromise → revoke → rotate → resume demonstrated (adversarial beat 8).

## 5.5 Nonce handling
- XChaCha20-Poly1305 uses a **24-byte random nonce per encryption**; nonce stored with ciphertext (nonce reuse is the only catastrophic failure — enforced: never reuse `(key, nonce)`; derive key per record via HKDF so key reuse across records is safe, nonce uniqueness per record enforced by Runtime).
- Ed25519 is deterministic signature; no nonce.

## 5.6 Session / device binding
- Execution authority optionally bound to a device session via `device_secret` mixed into root KMS derivation (ChrisCrypt device-bound sessions). A key used off-device fails to derive the same root → no authority.

## 5.7 Key rotation cadence
- Agent identity keys: rotated on compromise (D14) and optionally at cert expiry.
- Per-record data keys: derived fresh per record (HKDF salt); no long-lived data key at rest.
- Root key: long-lived; protected by Argon2id + device secret; rotation = re-derive + re-certify agents (out of MVD scope unless compromised).

## 5.8 Recovery
- Compromised worker: revoke + rotate (D14). No full fleet re-key required.
- Corrupted local state: restore from encrypted backup; verify chain on reload; reject entries that fail chain walk.

## 5.9 What we deliberately do NOT do
- No homomorphic/threshold/FHE crypto. No novel consensus. Single root trust (documented as a scope boundary, not a weakness claim).
