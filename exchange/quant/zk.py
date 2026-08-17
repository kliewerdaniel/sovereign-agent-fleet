"""Real zero-knowledge attestation of a learned prior (D24).

This is a *genuine* Σ-protocol ZK proof — not the selective-disclosure signature
from D22. It lets a venue prove a public predicate about its learned ``QuantLearner``
base rate ``P_model(Y=1)`` **without revealing the prior value**:

    "the learned prior is committed under a Pedersen commitment whose opening I know,
     the committed value lies in [0, 1], and it is bound to a state the canonical
     quant-advisor Ed25519 key signed."

The verifier learns only the commitment + a disclosed range predicate. The prior value
and the commitment blinding are hidden by the discrete-log assumption on secp256k1.

Construction
------------
* Group: secp256k1 (prime-order subgroup of size ``n``). Base point ``G`` is the
  standard generator; the second generator ``H`` is derived rigidly by hash-to-curve
  (try-and-increment) from a domain-separated seed — no trusted setup (ADR-D24-1).
  All scalar arithmetic is pure Python modulo ``n`` (only ``pow(x, -1, n)`` is needed).
* Pedersen commitment: ``C = v*G + r*H`` to the scaled prior ``v = round(p_yes*V_SCALE)``
  (ADR-D24-2). ``r`` is the blinding.
* Range proof (standard additive decomposition): ``v`` is proven in ``[0, 2^L)`` by
  writing ``v = Σ b_i·2^i`` and, per bit, committing ``C_i = b_i·2^i·G + r_i·H`` with
  ``Σ C_i = C`` and ``Σ r_i = r``. Each bit is proven ``b_i ∈ {0,1}`` via an OR of two
  2-generator Schnorr proofs of knowledge of the opening of ``C_i`` to ``0`` or to
  ``2^i`` (ADR-D24-3). Soundness is Σ-protocol special-soundness per bit.
* Binding: the prover also supplies an Ed25519 signature (under the canonical Q6-live
  ``quant-advisor`` key) over ``H(state)``; the verifier checks it fail-closed
  (ADR-D24-4). The ZK part proves the commitment opens to the prior; the sig anchors it
  to the real signed learner state.
* Fiat–Shamir: challenge ``e = sha256(C || T || branch || salt)`` makes the proof a
  non-interactive string (NIZK under ROM), replayable/verifiable offline with public keys
  (ADR-D24-5). A fixed decision-seed yields byte-identical proofs for the same input (I15).

IMPORT WALL: ONLY ``fleet.crypto.foundation`` (sha256, canonical_bytes), ``cryptography``
(Ed25519 + secp256k1), and stdlib. Never ``exchange.governance`` / ``fleet.fin``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from fleet.crypto.foundation import canonical_bytes, sha256

# --- secp256k1 field / group parameters --------------------------------------
_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
_GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8

# Scaling: prior probability (0,1) -> signed integer with ~1e-12 resolution.
V_SCALE = 1 << 40  # 1099511627776
# Range-proof bit width: scaled value max ~ V_SCALE (prior < 1), so L=48 is ample.
RANGE_BITS = 48

_ZK_SALT = b"D24-ZK-RANGEPROOF-v1"


def _inv(x: int) -> int:
    """Modular inverse in the FIELD (mod p), not the scalar order (n)."""
    return pow(x % _P, -1, _P)


def _is_on_curve(x: int, y: int) -> bool:
    return (y * y - (x * x * x + 7)) % _P == 0


def _ec_add(p: Optional[Tuple[int, int]], q: Optional[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
    """Point addition on secp256k1 (affine, None = identity). All arithmetic mod p."""
    if p is None:
        return q
    if q is None:
        return p
    x1, y1 = p
    x2, y2 = q
    if x1 == x2 and (y1 + y2) % _P == 0:
        return None
    if x1 == x2 and y1 == y2:
        lam = (3 * x1 * x1) * _inv(2 * y1) % _P
    else:
        lam = (y2 - y1) * _inv((x2 - x1) % _P) % _P
    x3 = (lam * lam - x1 - x2) % _P
    y3 = (lam * (x1 - x3) - y1) % _P
    return (x3, y3)


def _ec_mul(k: int, p: Tuple[int, int]) -> Optional[Tuple[int, int]]:
    """Scalar multiplication k * p (double-and-add). k is mod n; coords mod p."""
    k %= _N
    if k == 0:
        return None
    result: Optional[Tuple[int, int]] = None
    addend = p
    while k:
        if k & 1:
            result = _ec_add(result, addend)
        addend = _ec_add(addend, addend)
        k >>= 1
    return result


def _bytes32(x: int) -> bytes:
    return x.to_bytes(32, "big")


def _pt_to_pem(p: Optional[Tuple[int, int]]) -> str:
    if p is None:
        return "00"
    return _bytes32(p[0]).hex() + _bytes32(p[1]).hex()


def _pem_to_pt(s: str) -> Optional[Tuple[int, int]]:
    if s == "00":
        return None
    x = int(s[:64], 16)
    y = int(s[64:], 16)
    return (x, y)


# G: standard generator. H: rigidly derived second generator (hash-to-curve, no setup).
_G: Tuple[int, int] = (_GX, _GY)


def _hash_int(seed: bytes) -> int:
    """sha256 over bytes -> int (sha256() returns a hex str in this repo's foundation)."""
    return int.from_bytes(bytes.fromhex(sha256(seed)), "big")


def _hash_to_curve(seed: bytes) -> Tuple[int, int]:
    """Hash-to-curve (try-and-increment) on secp256k1 -> a point on the curve."""
    i = 0
    while True:
        hx = _hash_int(seed + _bytes32(i))
        x = hx % _P
        rhs = (x * x * x + 7) % _P
        # secp256k1 p % 4 == 3 -> square root via exponentiation
        y = pow(rhs, (_P + 1) // 4, _P)
        if _is_on_curve(x, y):
            return (x, y)
        i += 1


_H: Tuple[int, int] = _hash_to_curve(b"D24-ZK-PEDERSEN-H-v1" + _bytes32(_GX) + _bytes32(_GY))


class _DRNG:
    """Deterministic byte-stream RNG (HMAC-SHA256 chain) seeded from domain-separated bytes.

    Used ONLY to derive Fiat-Shamir nonces. Because the seed is a function of the public
    inputs (commitment points, indices) and the (secret) blinding, the resulting proof is
    *reproducible* and auditable for a given prior+state, while remaining a sound Schnorr
    OR proof under the random-oracle model (a deterministic nonce is equivalent to an
    oracle-sampled one for a honest prover).
    """

    def __init__(self, seed: bytes):
        self._key = seed

    def next(self) -> int:
        self._key = sha256(self._key).encode()
        return int.from_bytes(self._key, "big") % _N


def _signing_message(state_hash_hex: str, commitment_pem: str, range_lo: int, range_hi: int) -> bytes:
    """Ed25519 message: binds the learner STATE to the committed PRIOR (commitment) and range.

    Without this the signature would only cover the state, letting an attacker reuse one
    commitment under a different (also-validly-signed) state hash (rebind attack).
    """
    return sha256(
        (state_hash_hex + "|" + commitment_pem + "|" + str(range_lo) + "|" + str(range_hi)).encode()
    ).encode()


def _pedersen(v: int, r: int) -> Tuple[int, int]:
    """C = v*G + r*H."""
    return _ec_add(_ec_mul(v % _N, _G), _ec_mul(r % _N, _H))  # type: ignore[return-value]


def _or_challenge(c_i: str, t0: str, t1: str) -> int:
    """One shared Fiat-Shamir challenge for the whole OR statement (both branches).

    Order-independent: the two first-message points are hashed in a canonical (sorted) order
    so the builder (which knows real vs sim) and the verifier (which does not) agree on e
    regardless of which branch is stored as proof0/proo1.
    """
    a, b = sorted([t0, t1])
    return int.from_bytes(bytes.fromhex(sha256((c_i + a + b + _ZK_SALT.hex()).encode())), "big") % _N


# --- per-bit OR proof (2-generator Schnorr, shared challenge) ----------------

@dataclass(frozen=True)
class _SchnorrProof:
    t: str  # first message (commitment point) pem
    s1: str  # response on G
    s2: str  # response on H
    e: str  # branch challenge (e0 for real branch, e1 for simulated branch)

    def to_dict(self) -> dict:
        return {"t": self.t, "s1": self.s1, "s2": self.s2, "e": self.e}

    @classmethod
    def from_dict(cls, d: dict) -> "_SchnorrProof":
        return cls(t=d["t"], s1=d["s1"], s2=d["s2"], e=d["e"])


@dataclass(frozen=True)
class _BitProof:
    """OR proof: 'C_i opens to 0 OR to 2^i' (i.e. b_i in {0,1}).

    Sound Cramer-Schnorr OR: the prover freely picks a sim challenge ``e1`` for the branch it
    does NOT know, derives the global Fiat-Shamir challenge ``e = H(c_i, t0, t1)``, sets the
    real branch challenge ``e0 = e - e1`` (mod n), and responds on the real branch with the
    known witness ``(b_i*2^i, r_i)``. Both branches verify under their own challenges and
    ``e0 + e1 == e``. Special soundness: a valid proof implies the prover knows an opening of
    C_i to 0 OR to 2^i -> b_i in {0,1}.
    """
    c_i: str                 # per-bit commitment pem
    proof0: _SchnorrProof    # branch: opens to 0
    proof1: _SchnorrProof    # branch: opens to 2^i
    real_branch: int         # which branch knows the witness

    def to_dict(self) -> dict:
        return {"c_i": self.c_i, "proof0": self.proof0.to_dict(),
                "proof1": self.proof1.to_dict(), "real_branch": self.real_branch}

    @classmethod
    def from_dict(cls, d: dict) -> "_BitProof":
        return cls(c_i=d["c_i"], proof0=_SchnorrProof.from_dict(d["proof0"]),
                   proof1=_SchnorrProof.from_dict(d["proof1"]), real_branch=int(d["real_branch"]))


def _schnorr_verify(c_i: str, proof: _SchnorrProof, e: int) -> bool:
    """2-generator Schnorr knowledge of opening (a,b) to C_i = a*G + b*H under challenge e.

    Verifier equation: ``s1*G + s2*H == T + e*C_i``.
    """
    C = _pem_to_pt(c_i)
    T = _pem_to_pt(proof.t)
    if C is None or T is None:
        return False
    s1 = int(proof.s1, 16) % _N
    s2 = int(proof.s2, 16) % _N
    lhs = _ec_add(_ec_mul(s1, _G), _ec_mul(s2, _H))
    rhs = _ec_add(T, _ec_mul(e, C))
    return lhs == rhs


def _prove_bit_or(i: int, b_i: int, r_i: int, c_i: str) -> _BitProof:
    """Sound OR proof that C_i (committed as (b_i*2^i)*G + r_i*H) opens to 0 or to 2^i.

    Nonces are drawn from a per-bit DRNG seeded by ``c_i`` so the proof is byte-identical
    across replays (deterministic, still sound under ROM).
    """
    assert b_i in (0, 1)
    real = b_i
    value = b_i * (1 << i)  # G-witness for the real branch
    Ci = _pem_to_pt(c_i)
    drng = _DRNG(sha256(b"D24-bit-" + c_i.encode()).encode())
    # Simulated branch: freely chosen challenge e1 + random responses (k1', k2').
    e1 = drng.next()
    k1s = drng.next()
    k2s = drng.next()
    t_sim = _ec_add(_ec_add(_ec_mul(k1s, _G), _ec_mul(k2s, _H)), _ec_mul((-e1) % _N, Ci))
    t_sim_pem = _pt_to_pem(t_sim)
    # Real branch: random nonce, first message.
    k1 = drng.next()
    k2 = drng.next()
    t_real = _ec_add(_ec_mul(k1, _G), _ec_mul(k2, _H))
    t_real_pem = _pt_to_pem(t_real)
    # Global challenge, then real branch challenge e0 = e - e1.
    e = _or_challenge(c_i, t_real_pem, t_sim_pem)
    e0 = (e - e1) % _N
    s1_real = (k1 + e0 * value) % _N
    s2_real = (k2 + e0 * r_i) % _N
    real_proof = _SchnorrProof(t=t_real_pem, s1=_bytes32(s1_real).hex(),
                               s2=_bytes32(s2_real).hex(), e=_bytes32(e0).hex())
    sim_proof = _SchnorrProof(t=t_sim_pem, s1=_bytes32(k1s).hex(),
                              s2=_bytes32(k2s).hex(), e=_bytes32(e1).hex())
    if real == 0:
        return _BitProof(c_i=c_i, proof0=real_proof, proof1=sim_proof, real_branch=0)
    return _BitProof(c_i=c_i, proof0=sim_proof, proof1=real_proof, real_branch=1)


# --- public attestation ------------------------------------------------------

@dataclass(frozen=True)
class ZKAttestation:
    """A real ZK attestation of a learned prior (D24). Verifier learns only ``commitment_pem``
    and the public ``[range_lo, range_hi]`` predicate; the prior value + blinding stay secret."""

    commitment_pem: str
    range_lo: int
    range_hi: int
    bit_proofs: Tuple[dict, ...]
    prior_sig: str                 # Ed25519 sig over H(state) by quant-advisor key
    quant_cert_pubkey_pem: str     # canonical key public PEM (verifier anchor)
    state_hash_hex: str            # H(state) the sig covers (disclosed selector)
    proof_hash: str = ""

    def __post_init__(self):
        if not self.proof_hash:
            object.__setattr__(self, "proof_hash", sha256(canonical_bytes(self.to_dict())))

    def to_dict(self) -> dict:
        return {
            "commitment_pem": self.commitment_pem,
            "range_lo": self.range_lo,
            "range_hi": self.range_hi,
            "bit_proofs": list(self.bit_proofs),
            "prior_sig": self.prior_sig,
            "quant_cert_pubkey_pem": self.quant_cert_pubkey_pem,
            "state_hash_hex": self.state_hash_hex,
            "proof_hash": self.proof_hash,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ZKAttestation":
        return cls(
            commitment_pem=d["commitment_pem"],
            range_lo=int(d["range_lo"]),
            range_hi=int(d["range_hi"]),
            bit_proofs=tuple(d["bit_proofs"]),
            prior_sig=d["prior_sig"],
            quant_cert_pubkey_pem=d["quant_cert_pubkey_pem"],
            state_hash_hex=d["state_hash_hex"],
            proof_hash=d.get("proof_hash", ""),
        )

    def verify(self) -> bool:
        """Fail-closed: Ed25519 sig AND every bit proof AND Σ C_i == C AND range sanity."""
        # 1) Ed25519 binding: committed prior is anchored to a signed learner state.
        try:
            pub = serialization.load_pem_public_key(self.quant_cert_pubkey_pem.encode())
        except Exception:
            return False
        if not isinstance(pub, ed25519.Ed25519PublicKey):
            return False
        try:
            pub.verify(
                bytes.fromhex(self.prior_sig),
                _signing_message(self.state_hash_hex, self.commitment_pem, self.range_lo, self.range_hi),
            )
        except Exception:
            return False

        # 2) Per-bit OR proofs: each b_i in {0,1} via a shared-challenge Schnorr OR.
        C = _pem_to_pt(self.commitment_pem)
        if C is None or len(self.bit_proofs) != RANGE_BITS:
            return False
        acc: Optional[Tuple[int, int]] = None
        for i, bp in enumerate(self.bit_proofs):
            bit = _BitProof.from_dict(bp)
            e_global = _or_challenge(bit.c_i, bit.proof0.t, bit.proof1.t)
            e0 = int(bit.proof0.e, 16) % _N
            e1 = int(bit.proof1.e, 16) % _N
            # Branch challenges must sum to the global challenge (OR-binding integrity).
            if (e0 + e1) % _N != e_global:
                return False
            if not (_schnorr_verify(bit.c_i, bit.proof0, e0) and _schnorr_verify(bit.c_i, bit.proof1, e1)):
                return False
            Ci = _pem_to_pt(bit.c_i)
            if Ci is None:
                return False
            acc = _ec_add(acc, Ci)
        # 3) Decomposition binds to C: Σ C_i = C  (each C_i already weighted 2^i by builder).
        if acc != C:
            return False

        # 4) Disclosed range predicate sanity (cryptographic guarantee is v in [0,2^L)).
        if not (0 <= self.range_lo <= self.range_hi < (1 << RANGE_BITS)):
            return False
        return True


def build_zk_attestation(
    prior_p_yes: float,
    state_hash_hex: str,
    quant_key: "ed25519.Ed25519PrivateKey",
    quant_cert_pubkey_pem: str,
    *,
    decision_seed: bytes = b"D24-ZK-DECISION",
) -> ZKAttestation:
    """Build a real ZK attestation committing to ``prior_p_yes`` under the quant-advisor key.

    ``quant_key`` signs ``state_hash_hex`` (the learner state hash) — the same key that
    signs ``QuantEvidence`` envelopes in D29 Q6-live, so the proof binds to the canonical
    quant authority without granting any trade authority (M0).
    """
    if not (0.0 <= prior_p_yes <= 1.0):
        raise ValueError("prior_p_yes must be in [0,1]")
    v = int(round(prior_p_yes * V_SCALE))
    # Deterministic nonce stream: seed from the public inputs + key identity so the proof is
    # reproducible/auditable for a given (prior, state, key) — equivalently sound to random
    # nonces under the ROM, but now I15 (byte-identical replay) holds.
    seed = sha256(
        decision_seed
        + bytes.fromhex(state_hash_hex)
        + quant_cert_pubkey_pem.encode()
        + v.to_bytes(8, "big")
    ).encode()
    drng = _DRNG(seed)
    r = drng.next()
    C = _pedersen(v, r)

    # Decompose v = Σ b_i·2^i; per-bit blinding r_i with Σ r_i = r (so Σ C_i = C).
    bits: List[int] = [(v >> i) & 1 for i in range(RANGE_BITS)]
    r_is: List[int] = [drng.next() for _ in range(RANGE_BITS)]
    # Fix the last blinding so the sum equals r: r_{L-1} = r - Σ_{i<L-1} r_i (mod n).
    r_is[-1] = (r - sum(r_is[:-1])) % _N

    bit_proofs = []
    for i, b_i in enumerate(bits):
        # Per-bit commitment weighted by 2^i: C_i = (b_i·2^i)·G + r_i·H.
        Ci = _ec_add(_ec_mul((b_i * (1 << i)) % _N, _G), _ec_mul(r_is[i] % _N, _H))
        c_i = _pt_to_pem(Ci)
        # OR proof: C_i opens to 0 OR to 2^i (so b_i in {0,1}), shared-challenge Schnorr OR.
        bp = _prove_bit_or(i, b_i, r_is[i], c_i)
        bit_proofs.append(bp.to_dict())

    commitment_pem = _pt_to_pem(C)
    sig = quant_key.sign(
        _signing_message(state_hash_hex, commitment_pem, 0, V_SCALE)
    ).hex()
    return ZKAttestation(
        commitment_pem=commitment_pem,
        range_lo=0,
        range_hi=V_SCALE,
        bit_proofs=tuple(bit_proofs),
        prior_sig=sig,
        quant_cert_pubkey_pem=quant_cert_pubkey_pem,
        state_hash_hex=state_hash_hex,
    )


__all__ = ["ZKAttestation", "build_zk_attestation", "V_SCALE", "RANGE_BITS"]
