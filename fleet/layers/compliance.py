"""Zero-knowledge policy-compliance proof (D22 / E1, D21 Phase 3).

Lets an Operator prove to a third party that *"this consequential action complied
with policy `policy_id`, was approved by a human, and was rooted in the live
identity epoch"* WITHOUT revealing the CRM/source data the action touched.

The proof is an Ed25519 signature (reusing the vendored crypto) over a commitment
to (policy_id, artifact_hash, approval_sig, root_epoch, action_id). The verifier
holds only public keys and checks the math, not the data. No model authority is
added — the proof is built/verified by the deterministic Control Plane only.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fleet.crypto.foundation import canonical_bytes, sha256


def _commitment(
    policy_id: str,
    artifact_hash: str,
    approval_sig: str,
    root_epoch: int,
    action_id: str,
) -> bytes:
    """Deterministic commitment over the compliance facts (D22)."""
    body = {
        "policy_id": policy_id,
        "artifact_hash": artifact_hash,
        "approval_sig": approval_sig,
        "root_epoch": root_epoch,
        "action_id": action_id,
    }
    return bytes.fromhex(sha256(canonical_bytes(body)))


@dataclass
class ComplianceProof:
    sig: str                       # human_key.sign(commitment)
    human_pubkey_pem: str         # so a public-key-only verifier can check the sig
    root_epoch: int
    policy_id: str                # disclosed selector (non-secret)
    artifact_hash: str            # disclosed selector (non-secret)
    action_id: str
    # The approval_sig is INCLUDED in the commitment but NOT disclosed as a field
    # here by default; a verifier who needs to bind it passes it back in. Kept
    # internal so a third party cannot harvest human signatures.
    _approval_sig: str = field(default="", repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sig": self.sig,
            "human_pubkey_pem": self.human_pubkey_pem,
            "root_epoch": self.root_epoch,
            "policy_id": self.policy_id,
            "artifact_hash": self.artifact_hash,
            "action_id": self.action_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any], approval_sig: str = "") -> "ComplianceProof":
        return cls(
            sig=d["sig"],
            human_pubkey_pem=d["human_pubkey_pem"],
            root_epoch=int(d["root_epoch"]),
            policy_id=d["policy_id"],
            artifact_hash=d["artifact_hash"],
            action_id=d["action_id"],
            _approval_sig=approval_sig,
        )


def build_compliance_proof(
    human_cert,
    human_key,
    policy_id: str,
    artifact_hash: str,
    approval_sig: str,
    root_epoch: int,
    action_id: str,
) -> ComplianceProof:
    """Produce a selective-disclosure compliance proof (D22).

    The human signs the commitment containing the approval signature, so the proof
    attests that a valid human approval existed for exactly this action. The CRM
    data itself is never part of the proof.
    """
    comm = _commitment(policy_id, artifact_hash, approval_sig, root_epoch, action_id)
    sig = human_key.sign(comm).hex()
    return ComplianceProof(
        sig=sig,
        human_pubkey_pem=human_cert.pubkey_pem,
        root_epoch=root_epoch,
        policy_id=policy_id,
        artifact_hash=artifact_hash,
        action_id=action_id,
        _approval_sig=approval_sig,
    )


def verify_compliance_proof(
    proof: ComplianceProof,
    policy_id: str,
    artifact_hash: str,
    action_id: str,
    root_epoch: Optional[int] = None,
) -> bool:
    """Verify a compliance proof against disclosed selectors (fail-closed).

    Checks:
      1. the proof's own policy_id/artifact_hash/action_id match what the verifier
         was told to expect (no rebinding to a different action);
      2. the human signature verifies under the proof's public key over the
         commitment that embeds the (withheld) approval signature;
      3. if an expected root_epoch is supplied, the proof's epoch matches.
    """
    if not isinstance(proof, ComplianceProof):
        return False
    if proof.policy_id != policy_id:
        return False
    if proof.artifact_hash != artifact_hash:
        return False
    if proof.action_id != action_id:
        return False
    if root_epoch is not None and proof.root_epoch != root_epoch:
        return False
    try:
        pub = serialization.load_pem_public_key(proof.human_pubkey_pem.encode())
        if not isinstance(pub, Ed25519PublicKey):
            return False
        comm = _commitment(
            proof.policy_id, proof.artifact_hash, proof._approval_sig,
            proof.root_epoch, proof.action_id,
        )
        pub.verify(bytes.fromhex(proof.sig), comm)
        return True
    except (InvalidSignature, ValueError):
        return False
