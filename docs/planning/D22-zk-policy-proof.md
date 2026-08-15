# D22 — Zero-Knowledge Policy-Compliance Proof (Extension E1, D21 Phase 3)

## Thesis fit
> "Do not trust the model. Trust the execution protocol."

E1 lets an Operator **prove to a third party** — an auditor, a regulator, a
downstream system — that *"this consequential action complied with policy `X`, had
a valid human approval, and was rooted in the live identity epoch"* **without
revealing the CRM/source data the action touched.** It is a natural extension of
the repo's core claim: *verifiability without authority, public keys only.*

It adds **no model authority**. The proof is produced and verified by the
deterministic Control Plane; the Brain never signs, approves, or sees the proof.

## Construction
The proof is an Ed25519 signature (reusing the already-vendored crypto) over a
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
`human_id`, and any other payload fields. The verifier learns only that *a valid
human approval existed for (policy_id, artifact_hash, action_id) under epoch N*.

## Why Ed25519 and not a full ZK-SNARK
The repo deliberately avoids new cryptographic primitives (D5/D6: "No new
primitives; vendored ChrisCryptSN + cryptography/pynacl"). A signature over a
commitment is the minimal, auditable primitive that yields *selective disclosure*:
reveal the commitment inputs you choose, keep the rest secret. It is the same
math the rest of the system already trusts (`verify_cert`, `verify_approval`,
`verify_tool_envelope`). A SNARK would add a trusted setup and a non-vendored
dependency — strictly worse for this local-first, audit-first design.

## Trust boundary (unchanged)
- Producer: deterministic `ControlPlane` only.
- Verifier: public keys only (human cert pubkey, root pubkey if epoch is checked).
- Model: never touches the proof.

## Files
- `fleet/layers/compliance.py` — `build_compliance_proof`, `verify_compliance_proof`.
- `fleet/tests/test_compliance_phase3.py` — adversarial: valid proof verifies;
  tampered artifact_hash fails; rebound to different policy fails; wrong human key
  fails; epoch mismatch fails.

## Rejected alternative
A general ZK-SNARK / SHA256-circuit proof was considered and **rejected**: it
requires a non-vendored dependency and a trusted-setup ceremony that contradicts
D5/D6 (no new primitives) and the local-first, audit-first posture. The
commitment-signature construction delivers the same selective-disclosure property
with crypto the system already trusts.
