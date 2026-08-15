# D22 — Selective-Disclosure Compliance Attestation (Extension E1, D21 Phase 3)

> Renamed from "Zero-Knowledge Policy-Compliance Proof" in the Round-2 audit
> (finding R1). The original name overclaimed: the construction is a
> selective-disclosure signed attestation, **not** a zero-knowledge proof. It is
> kept as `fleet/layers/compliance.py` (module name unchanged; the
> *selective-disclosure* property is the real one). See the "Why not zero-knowledge"
> section for the exact gap.

## Thesis fit
> "Do not trust the model. Trust the execution protocol."

E1 lets an Operator **prove to a third party** — an auditor, a regulator, a
downstream system — that *"this consequential action complied with policy `X`, had
a valid human approval, and was rooted in the live identity epoch"* **without
revealing the CRM/source data the action touched.** It is a natural extension of
the repo's core claim: *verifiability without authority, public keys only.*

It adds **no model authority**. The attestation is produced and verified by the
deterministic Control Plane; the Brain never signs, approves, or sees it.

## Construction
The attestation is an Ed25519 signature (reusing the already-vendored crypto) over a
**commitment** to the compliance facts:

```
commitment = H( policy_id || artifact_hash || approval_sig || root_epoch || action_id )
proof       = human_key.sign(commitment)           # a human approved this exact action
            + root_epoch                            # which identity epoch was live
            + policy_id, artifact_hash             # disclosed (non-secret) selectors
            + human_cert.pubkey_pem                # so the verifier can check the sig
```

A verifier with **only public keys** checks:

1. `proof.sig` verifies under `human_cert.pubkey_pem` over `H(policy_id || artifact_hash || approval_sig || root_epoch || action_id)`.
2. The disclosed `approval_sig` is the same one bound into the commitment (it is
   included verbatim in the commitment hash — the verifier does not need to verify
   the approval itself, only that the human signed *this* commitment containing it).
3. `policy_id` / `artifact_hash` in the proof match the ones the verifier was
   told to expect (so the proof cannot be rebound to a different action).

**What is hidden:** the CRM record, the source extract, the human's identity
`human_id`, and the raw `approval_sig`. The verifier learns only that *a valid
human approval existed for (policy_id, artifact_hash, action_id) under epoch N*.
The `approval_sig` is withheld from `to_dict()` so a third party cannot harvest
human signatures.

## Why Ed25519 and not a SNARK
The repo deliberately avoids new cryptographic primitives (D5/D6: "No new
primitives; vendored ChrisCryptSN + cryptography/pynacl"). A signature over a
commitment is the minimal, auditable primitive that yields *selective disclosure*:
reveal the commitment inputs you choose, keep the rest secret. It is the same
math the rest of the system already trusts (`verify_cert`, `verify_approval`,
`verify_tool_envelope`). A SNARK would add a trusted setup and a non-vendored
dependency — strictly worse for this local-first, audit-first design.

## Why NOT call this "zero-knowledge"
An honest assessment (R1, Round 2) of what this construction does **not** provide:

- **No zero-knowledge on the action identity.** `policy_id` and `artifact_hash`
  are disclosed in plaintext by design — a verifier learns exactly which action the
  attestation covers. A true ZK proof would let the verifier confirm "an action
  compliant with *some* policy, approved by a human, under epoch N" *without*
  learning `policy_id`/`artifact_hash` (only a commitment to them).
- **No completeness/soundness/ZK security argument.** There is no simulator, no
  knowledge-soundness reduction, no hiding/ binding game. "The verifier learns only
  these fields" is a statement about *what the dataclass serializes*, not a
  cryptographic hiding guarantee on the withheld `approval_sig`.
- **The withheld field isn't hidden by crypto, just omitted from serialization.**
  `approval_sig` is left out of `to_dict()`; it is not committed to a Pedersen
  commitment or otherwise cryptographically blinded. Anyone who has it (the issuer)
  holds it in the clear.

Calling this "zero-knowledge" in a submission a cryptographer might read would
undercut otherwise-solid engineering. We name it precisely: a
**selective-disclosure signed attestation**. If the hackathon criteria require a
true ZK property (hide the action identity too), see `D24-real-zk-compliance-proof.md`
for the scoped Sigma-protocol design — it was not implemented because the honest,
smaller primitive already satisfies the repo's verifiability goal.

## Trust boundary (unchanged)
- Producer: deterministic `ControlPlane` only.
- Verifier: public keys only (human cert pubkey, root pubkey if epoch is checked).
- Model: never touches the attestation.

## Files
- `fleet/layers/compliance.py` — `build_compliance_proof`, `verify_compliance_proof`, `ComplianceProof`.
- `fleet/tests/test_compliance_phase3.py` — adversarial: valid attestation verifies;
  tampered artifact_hash fails; rebound to different policy fails; wrong human key
  fails; epoch mismatch fails; `approval_sig` not leaked in `to_dict()`.

## Rejected alternative
A general ZK-SNARK / SHA256-circuit proof was considered and **rejected for this
extension**: it requires a non-vendored dependency and a trusted-setup ceremony that
contradicts D5/D6 (no new primitives) and the local-first, audit-first posture. The
commitment-signature construction delivers the same *selective-disclosure* property
with crypto the system already trusts. A *true* ZK variant (D24) is a separate,
larger design effort and is out of scope for the D21 hardening pass.
