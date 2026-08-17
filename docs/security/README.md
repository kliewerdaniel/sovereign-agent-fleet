# Security — adversarial, attestation, consensus

The security properties of this system are **demonstrated by passing tests**, not asserted in
prose. Every property below has a corresponding test (or adversarial beat) in `fleet/tests/` or
`exchange/tests/`.

## The adversarial 8-beat governability demo (canonical "aha")

Each beat is a passing automated test (`fleet/tests/test_adversarial_beats_phase5.py`):

1. Prompt injection stripped at the structured boundary (Model Armor)
2. Capability denial → Gateway DENY + signed deny event
3. Consequential action without approval blocked pre-FINAL
4. Human-signed `ApprovalRecord` grants authority
5. Execution succeeds; artifact signed, chained, replicated
6. Post-hoc audit edit detected by the hash-chain verifier
7. Forged identity (not signed by root) rejected
8. Revoke + rotate: fresh key, chain intact

## D21 security-audit hardening (honest, after audit)

- **Cryptographically bound approval (A1/A2):** `Operator.act` fails-closed; the human
  `ApprovalRecord` is a genuine Ed25519 signature binding *exact* action id + capability +
  artifact hash. Forged/rebound/reused approvals rejected.
- **Root-key backup + rotation + verifier continuity (K1):** encrypted blob only; rotation
  re-signs live certs, keeps historical certs verifiable under their epoch's key.
- **Revoke/rotate invalidates live grants (A3):** gateway idempotency cache re-validates cert
  liveness on replay; a revoked agent cannot replay an old token.
- **Deep Model Armor (M1/M2):** injection stripping + PII redaction recurse through nested
  structures at the evidence boundary.
- **Default-deny by property (P1):** exhaustively asserts every unknown `(role, capability)` is
  DENY.
- **Console fails closed (G2):** the Cloud Run approval console rejects any approval it cannot
  cryptographically verify.
- **Pinned, audited supply chain (S1):** locked versions on both dependency surfaces + CycloneDX
  SBOM + `pip-audit` CI gate.
- **Replay defense (C3):** the signed hash-chain detects a re-inserted historical entry.

## ZK attestation (D24) — advanced "wow"

`exchange/quant/zk.py` is a **genuine Σ-protocol** (pure-Python secp256k1 + Pedersen commitment
+ Cramer-Schnorr OR range proof + Ed25519 binding). It proves a **learned prior lies in
`[lo, hi]`** *without revealing the prior value* — the verifier learns only the predicate, not
the witness. This is a real ZK proof (unlike the earlier D22 selective-disclosure signature,
which is honestly named as such).

- `build_zk_attestation(prior_p_yes, state_hash_hex, quant_key, cert_pem)` → `ZKAttestation`
- `ZKAttestation.verify()` → bool (sig binds `state‖commitment‖range`; per-bit OR proofs;
  `Σ C_i == C`)
- Tests: `exchange/tests/test_quant_d24.py` (10 passing)

This is the **secondary** demo after the core governance→execution→verification story.

## Consensus (D23 / E2)

A VERIFIED-tier claim requires **two distinct Brain backends** to agree; disagreement downgrades
to ASSERTED and emits a signed `consensus.disagreement` event. The model stays proposal-only;
the deterministic gate decides. Consensus can only *escalate*, never authorize (I12).

## Key documents

- [`research/07-adversarial-test-plan.md`](../research/07-adversarial-test-plan.md)
- [`research/D21-security-audit.md`](../research/D21-security-audit.md)
- [`research/D22-zk-policy-proof.md`](../research/D22-zk-policy-proof.md) (honest selective-disclosure)
- [`research/D24-real-zk-compliance-proof.md`](../research/D24-real-zk-compliance-proof.md) (real ZK)
- [`research/D23-multi-brain-consensus.md`](../research/D23-multi-brain-consensus.md)
- [`research/05-cryptographic-design.md`](../research/05-cryptographic-design.md)
