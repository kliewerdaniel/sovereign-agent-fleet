"""Human approval verification (D17 hardening — findings A1/A2 of D21).

The Operator MUST cryptographically verify a human ``ApprovalRecord`` before
executing a consequential action, and the approval must bind to the *exact*
action it authorizes:

  * ``action_id``  — the idempotency key of the action being executed
  * ``capability`` — the capability being granted
  * ``artifact_hash`` — the hash of the (redacted) artifact being committed

A caller who controls the Operator process cannot forge an approval, swap it
onto a different action, or reuse an approval for a different artifact.

Verification uses ONLY public material (the human cert's Ed25519 public key),
mirroring ``FirestoreVerifier`` — no authority is needed to *check* an
approval. Everything fails closed: any malformed, unsigned, mis-bound, or
non-'approve' record returns ``False`` and the Operator blocks.
"""
from __future__ import annotations

from typing import Any, Dict

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fleet.crypto.foundation import AgentCert, canonical_bytes


def approval_sign_body(record: Dict[str, Any]) -> bytes:
    """Reconstruct the exact canonical body ``Approval.sign`` signed.

    ``approval_id`` is blanked because the signature is computed before the id
    is minted (see ``runtime.Approval.sign``).
    """
    body = {
        "approval_id": "",
        "agent_id": record.get("agent_id"),
        "action_id": record.get("action_id"),
        "capability": record.get("capability"),
        "artifact_hash": record.get("artifact_hash"),
        "decision": record.get("decision"),
        "reason": record.get("reason"),
        "human_id": record.get("human_id"),
        "ts": record.get("ts"),
    }
    return canonical_bytes(body)


def verify_approval(
    record: Dict[str, Any],
    human_cert: AgentCert,
    action_id: str,
    capability: str,
    artifact_hash: str,
) -> bool:
    """True iff ``record`` is a valid, strictly-bound human approval.

    Fail-closed. Checks, in order:

    1. ``record`` is a dict and ``decision == 'approve'``.
    2. ``human_sig`` verifies under the human cert's Ed25519 public key over the
       canonical signed body.
    3. ``action_id``, ``capability``, and ``artifact_hash`` match the action
       actually being executed (no rebinding / reuse).
    """
    if not isinstance(record, dict):
        return False
    if record.get("decision") != "approve":
        return False
    sig = record.get("human_sig")
    if not isinstance(sig, str) or not sig:
        return False
    try:
        pub = serialization.load_pem_public_key(human_cert.pubkey_pem.encode())
        if not isinstance(pub, Ed25519PublicKey):
            return False
        pub.verify(bytes.fromhex(sig), approval_sign_body(record))
    except (InvalidSignature, ValueError):
        return False
    # Strict binding to THIS action — a forged/rebound approval fails here.
    if record.get("action_id") != action_id:
        return False
    if record.get("capability") != capability:
        return False
    if record.get("artifact_hash") != artifact_hash:
        return False
    return True
