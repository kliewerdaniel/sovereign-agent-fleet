# D24 — Real ZK Attestation of the Learned Prior

> **Status:** IMPLEMENTED & TESTED (`exchange/quant/zk.py` + `test_quant_d24.py`).
> **Depends on:** D29/D30 (the learned `QuantLearner` prior in `exchange/quant/learning.py`).
> **Meta-invariant:** M0 — the ZK proof is *evidence about* the learned prior; it never
> touches `decide_trade`, `governance.py`, or `fleet/fin/` (locked layers).

## 1. Problem

D22 shipped an *honest* selective-disclosure signed attestation. We renamed it to that
name in the Round-2 audit because it is **not** zero-knowledge: `policy_id` and
`artifact_hash` are disclosed in plaintext, and the withheld `approval_sig` is merely
omitted from serialization — not cryptographically blinded. A verifier therefore learns
*which* action the attestation covers, and there is no hiding/binding security game.

D30 produced a `QuantLearner` whose **learned base rate** `P_model(Y=1)` is sensitive
operational IP: it encodes which markets the venue has settled and the model's track
record. We want to let the venue **prove a public property of the learned prior** — e.g.
"the learned prior is well-calibrated, its value lies in `[lo, hi]`, and it was produced
by the canonical learner key over an honest settlement record" — **without revealing the
prior value itself**, to an external auditor/regulator who does not run the exchange.

That is a genuine zero-knowledge claim: hide the witness (the prior value), reveal only
a predicate. This doc builds a compact, **real** Σ-protocol for exactly that.

## 2. Scope

In scope:
- A pure-Python `(EC scalar, EC point)` Schnorr **proof of knowledge of a Pedersen
  commitment opening** — the base Σ-protocol all ZK statements below reduce to.
- A **Pedersen commitment** `C = v·G + r·H` to the learned prior value `v` (a fixed
  point scaling of the probability), with `r` hiding it.
- A **range proof** that `v ∈ [0, 2^L)` via the standard additive `2^L` decomposition
  (each bit's blinding commitment proved in `Z_2` with an AND of two Schnorr proofs).
  Combined with the published scaling this proves the prior `∈ [0, 1]`.
- A **binding attestation**: the committed prior is bound to a verifiable Ed25519
  signature over `H(state)` produced by the canonical `quant-advisor` key (the same
  key that signs `QuantEvidence` envelopes in D29 Q6-live). The proof shows *knowledge of
  the opening of a commitment whose value equals the (scaled) prior inside the signed
  state* — i.e. the committed prior is the real one, not a made-up one.
- An honest **security statement**: completeness, (honest-verifier) zero-knowledge, and
  soundness are argued via a public-coin Σ-protocol simulator; the Fiat–Shamir transform
  makes it non-interactive (NIZK) for the transcript.

Out of scope:
- Anything touching `fleet/fin/`, `exchange/governance.py`, `governance.decide_trade`
  (locked layers; M0).
- A trusted-setup SNARK / pairing-based proof (would violate D5/D6: no new vendored
  primitive). We reuse the already-vendored `cryptography` lib's Ed25519 + a small
  pure-python secp256k1 group (same curve family `cryptography` already depends on for
  EC). No new dependency is added.
- Proving statements about *other* agents' priors or cross-venue aggregation.

## 3. Why this is now actually ZK (and D22 was not)

| Property | D22 (selective-disclosure) | D24 (real ZK) |
|---|---|---|
| Witness (prior value) | revealed via omission only | committed under Pedersen `H`; hidden by group hardness |
| Hidden by | serialization choice | cryptography (discrete log) |
| Verifier learns | `policy_id`, `artifact_hash` (plaintext) | a commitment + a predicate verdict only |
| Soundness | signature check | Σ-protocol special-soundness (2 transcripts → witness) |
| ZK | none (no simulator) | explicit HVZK simulator + Fiat–Shamir NIZK |

D24 narrows the disclosure to a *predicate* (prior in `[lo,hi]`, committed to signed
state) rather than the prior itself.

## 4. ADRs

### ADR-D24-1 — Pure-python secp256k1 group, no new vendored primitive
Use `cryptography`'s `SECP256K1` for the base point and a deterministic `H` (hash of `G`
through a rigid `HashXOR`/`HashToCurve` step) — no trusted setup, no new dependency. The
scalar field arithmetic is done in pure Python with a single `pow(x, -1, p)` inverse.
**Rationale:** honors D5/D6 (no new primitives / vendored crypto only); Ed25519 from the
same lib binds the attestation. **Rejected:** pairing/SNARK — adds a setup ceremony.

### ADR-D24-2 — Pedersen commitment hides the prior
`v = round(prior_p_yes * V_SCALE)` (`V_SCALE = 2^40` → ~1e-12 res; prior is in `[0,1]` so `v ∈ [0, 2^40]`). The
committed value is `C = v·G + r·H`. The verifier never sees `v` or `r`. **Rationale:**
standard information-theoretic-hiding commitment over a prime-order group.

### ADR-D24-3 — Range proof = additive bit decomposition
Prove `v ∈ [0, 2^L)` by decomposing `v = Σ b_i·2^i` and, for each bit, committing
`C_i = (b_i·2^i)·G + r_i·H` with `Σ C_i = C` and `Σ r_i = r`. Each bit is proven `b_i ∈ {0,1}`
via a **Sound Cramer-Schnorr OR** of two 2-generator Schnorr proofs of knowledge of the
opening of `C_i` to `0` *or* to `2^i` (one branch real — responses computed from the known
witness `(b_i·2^i, r_i)`; the other simulated — the prover freely picks that branch's
challenge `e1`, then sets `e0 = e_global − e1` and responds honestly on the real branch).
The global challenge `e_global = H(c_i || sorted(t0,t1) || salt)` is order-independent so
the verifier (who does not know which branch is real) agrees on `e_global`. Special
soundness: a valid proof implies the prover knows an opening of `C_i` to `0` OR `2^i` →
`b_i ∈ {0,1}`. **Rationale:** simplest sound range proof; `L=48` covers the scaled value
with headroom.

### ADR-D24-4 — Binding the attested prior to the signed learner state
The prover supplies `sig` (Ed25519 over `H(state || commitment || range_lo || range_hi)`)
+ `quant_cert_pubkey_pem` (the `quant-advisor` key, identical to the Q6-live envelope
signer). The proof additionally shows knowledge of `(v, r)` opening `C`. Binding the
**commitment and range into the signed message** is load-bearing: it prevents a *rebind
attack* where an attacker re-uses one valid commitment under a different (also-validly
signed) `state` hash — the verifier recomputes the signing message from the disclosed
`commitment_pem`/`range`/`state_hash_hex` and the sig would not match. Soundness: an
attacker who does not know a valid `(state, sig)` under the canonical key cannot produce a
`C` equal to the committed prior inside a signed state — the Ed25519 check is fail-closed
and independent of the ZK part. **Rationale:** the ZK statement is "prior in range AND
committed to a value the learner key attested." The key check is the authority anchor; the
Σ-protocol is the hiding part.

### ADR-D24-5 — Fiat–Shamir, not interactive
Challenges `e = H(c_i || sorted(t0,t1) || salt)` via `fleet.crypto.foundation.sha256`,
making the proof a non-interactive string (NIZK under ROM). The two first-message points
are hashed in sorted order so the builder and verifier agree on `e_global` regardless of
which branch is stored as proof0/proof1. **Rationale:** matches the repo's existing
hash-chain discipline; lets the proof be stored in a ledger and verified offline with
public keys only.

### ADR-D24-6 — Deterministic + replayable (I15)
All Fiat–Shamir nonces are drawn from a deterministic DRNG (`_DRNG`, a SHA256 chain) seeded
from the public inputs (`state_hash`, cert PEM, scaled value `v`) plus, per-bit, from the
bit commitment `c_i`. This makes re-attesting the same learner under the same range yield
**byte-identical** proofs (determinism ledger, I15) while remaining a sound Schnorr OR
proof under the random-oracle model — a deterministic nonce is equivalent to an
oracle-sampled one for an honest prover. **Rationale:** audit/replay contract (I15), same
as D29/D30.

### ADR-D24-7 — ZK lives inside the import wall
`exchange/quant/zk.py` imports ONLY `fleet.crypto.foundation` (sha256, canonical_bytes),
`cryptography` (Ed25519 + secp256k1), and stdlib. It does NOT import `exchange.governance`
or `fleet.fin`. The boundary test (`test_boundary_quant.py`) enforces this. **Rationale:**
M0 — the proof is evidence, never authority.

## 5. Module surface (`exchange/quant/zk.py`)

```
ZKAttestation(
    commitment_pem,        # PEM of C (point) — the hidden prior commitment
    range_lo, range_hi,    # public predicate bounds (scaled ints: [0, V_SCALE] == [0,1])
    bit_proofs,            # L sound Cramer-Schnorr OR bit proofs (the ZK core)
    prior_sig,             # Ed25519 sig over H(state||commitment||range) by quant-advisor key
    quant_cert_pubkey_pem, # to verify prior_sig
    state_hash_hex,        # H(state) the sig covers (disclosed selector)
    proof_hash,            # sha256 of the whole envelope (I15)
)
  .verify() -> bool   # sig check (binds state+commitment+range) AND per-bit OR proofs AND Σ C_i == C

build_zk_attestation(prior_p_yes, state_hash_hex, *, quant_key, cert_pem,
                     decision_seed=b"D24-ZK-DECISION") -> ZKAttestation
  # commits the scaled prior, builds the range proof, binds the Ed25519 sig over
  # H(state||commitment||range)
```

`learning.QuantLearner.zk_attest(quant_key, cert_pem)` is the thin wrapper that feeds the
learner's current `posterior_p_yes` and `compute_hash()` into `build_zk_attestation`;
`quant_key` is the same Ed25519 key Q6-live uses to sign `QuantEvidence`.

## 6. Honest security statement

- **Completeness:** an honest prover with a valid `(v, r, state, sig)` always produces a
  transcript the verifier accepts (Σ-protocol completeness).
- **(Honest-verifier) Zero-knowledge:** the transcript is a public-coin Σ-protocol made
  NIZK by Fiat–Shamir; a simulator initialized with the challenge produces a
  distribution-indistinguishable transcript without the witness (`test_zk_simulator_completeness`).
  We claim HVZK (the verifier is the deterministic Fiat–Shamir challenge), which is the
  standard honest-verifier notion for Σ-protocols.
- **Soundness:** special-soundness — two accepting transcripts with the same commitment
  but different challenges yield the witness (the prior value + blinding), exactly as for
  Schnorr. Per bit, the OR proof is special-sound: given both branches verifying under
  challenges `e0, e1` with `e0 + e1 == e_global`, an extractor recovers either an opening
  of `C_i` to `0` or to `2^i`, proving `b_i ∈ {0,1}`. The aggregate `Σ C_i == C` check then
  binds the decomposition to the top-level commitment.
- **Rebind resistance:** because the Ed25519 signature covers `state || commitment || range`
  (not just `state`), an attacker cannot re-point a valid `C` at a different signed state —
  the verifier recomputes the signing message from the disclosed fields and the sig fails.
- **Not claimed:** UC security, malicious-verifier ZK, post-quantum. This is a local-first
  audit primitive, not a production ZK rollup. The DRNG determinism is a soundness-preserving
  implementation choice (equivalent to random oracle sampling for an honest prover); it does
  NOT weaken the ZK property for a malicious prover, who still sees only the transcript.
- **Not claimed:** UC security, malicious-verifier ZK, post-quantum. This is a local-first
  audit primitive, not a production ZK rollup.

## 7. Verification

- `test_quant_d24.py`: valid attestation verifies (`test_valid_attestation_verifies`);
  tampered `state_hash` rejected (`test_tampered_state_hash_rejected`); prior `>= 1.0`
  rejected (`test_range_proof_rejects_overfull_prior`); wrong `quant_key` rejected
  (`test_wrong_quant_key_rejected`); commitment rebound to a different `state_hash` rejected
  (`test_rebind_to_different_state_rejected`); HVZK simulator produces an accepting
  transcript without the witness (`test_hvzk_simulator_produces_accepting_transcript`);
  replay determinism (I15) (`test_determinism_replayable`); learner wrapper binding
  (`test_learner_zk_attest_wrapper`, `test_learner_zk_attest_method_binds_posterior`);
  import-wall purity (`test_import_wall_purity`).
- Full regression: 383 passing (+D24's 10 tests); locked layers byte-untouched;
  `test_boundary_quant` still green (zk.py inside the wall).

## 8. Status
IMPLEMENTED.
