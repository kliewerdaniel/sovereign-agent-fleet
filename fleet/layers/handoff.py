"""Signed cross-agent handoff envelopes (13.2 / D8 / 03.5).

The hard boundary between fleet workers. A message carries:
  * the sender's root-signed AgentCert (receiver re-verifies identity),
  * a typed payload (schema-validated), and
  * the sender's Ed25519 signature over the canonical payload.

The receiver (Gateway-adjacent verification) DROPS any message that is
unsigned, has an invalid sender cert, or fails schema — this is Model Armor's
injection defense (04.3): an injected "ignore previous instructions" string has
no execution surface because the protocol never executes free-text as instruction.

Two concrete payload types enforce capability separation (D8):
  * SourcedEvidence (Researcher)  -- MUST NOT contain classification/confidence
  * QualifiedIntel  (Analyst)     -- MUST cite >=1 valid SourcedEvidence id
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from fleet.crypto.foundation import AgentCert, canonical_bytes
from fleet.layers.registry import AgentRegistry


class HandoffError(Exception):
    pass


def _load_pub(pem: str) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(pem.encode())
    if not isinstance(key, Ed25519PublicKey):
        raise HandoffError("sender cert public key is not Ed25519")
    return key


def sign_payload(payload: Dict[str, Any], sender_key: Ed25519PrivateKey) -> str:
    return sender_key.sign(canonical_bytes(payload)).hex()


def verify_payload_sig(payload: Dict[str, Any], sig_hex: str, sender_cert: AgentCert) -> bool:
    try:
        _load_pub(sender_cert.pubkey_pem).verify(
            bytes.fromhex(sig_hex), canonical_bytes(payload)
        )
        return True
    except (InvalidSignature, ValueError):
        return False


# ---------------------------------------------------------------------------
# Payload schemas (capability separation, D8)
# ---------------------------------------------------------------------------

def _validate_sourced_evidence(p: Dict[str, Any]) -> None:
    required = {"evidence_id", "agent_id", "citation", "extract", "source_hash"}
    missing = required - set(p)
    if missing:
        raise HandoffError(f"SourcedEvidence missing fields: {missing}")
    # D8: Researcher is FORBIDDEN from emitting judgement fields.
    forbidden = {"classification", "confidence", "intel_id"}
    leaked = forbidden & set(p)
    if leaked:
        raise HandoffError(f"SourcedEvidence must not carry judgement fields: {leaked}")


def _validate_qualified_intel(p: Dict[str, Any], evidence_ids: set) -> None:
    required = {"intel_id", "agent_id", "target_id", "predicates"}
    missing = required - set(p)
    if missing:
        raise HandoffError(f"QualifiedIntel missing fields: {missing}")
    predicates = p.get("predicates") or []
    if not isinstance(predicates, list) or not predicates:
        raise HandoffError("QualifiedIntel.predicates must be a non-empty list")
    for pred in predicates:
        refs = pred.get("evidence_refs") or []
        if not refs:
            raise HandoffError("every QualifiedIntel predicate MUST cite >=1 evidence_id")
        for ref in refs:
            if ref not in evidence_ids:
                raise HandoffError(f"evidence_ref '{ref}' does not resolve to a known SourcedEvidence")


@dataclass
class Handoff:
    sender_cert: AgentCert
    payload_type: str
    payload: Dict[str, Any]
    sender_sig: str

    # --- build (sender side) -----------------------------------------------
    @classmethod
    def make(cls, sender_cert: AgentCert, sender_key: Ed25519PrivateKey,
             payload_type: str, payload: Dict[str, Any]) -> "Handoff":
        return cls(
            sender_cert=sender_cert, payload_type=payload_type,
            payload=payload, sender_sig=sign_payload(payload, sender_key),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sender_cert": self.sender_cert.to_dict(),
            "payload_type": self.payload_type,
            "payload": self.payload,
            "sender_sig": self.sender_sig,
        }

    # --- verify + consume (receiver side) ----------------------------------
    def verify(self, registry: AgentRegistry) -> None:
        """Raise HandoffError unless the message is authentic and schema-valid.

        Authenticity: sender cert is the live, root-signed, unrevoked cert for
        that agent_id, and the sender_sig is valid under that cert's pubkey.
        """
        live = registry.discover(self.sender_cert.agent_id)
        if live is None or live.cert_seq != self.sender_cert.cert_seq:
            raise HandoffError("sender identity not authenticated by registry")
        if not verify_payload_sig(self.payload, self.sender_sig, self.sender_cert):
            raise HandoffError("sender signature invalid")

    def consume(self, registry: AgentRegistry, known_evidence: set) -> Dict[str, Any]:
        """Verify then schema-validate. Returns the validated payload."""
        self.verify(registry)
        if self.payload_type == "SourcedEvidence":
            _validate_sourced_evidence(self.payload)
        elif self.payload_type == "QualifiedIntel":
            _validate_qualified_intel(self.payload, known_evidence)
        else:
            raise HandoffError(f"unknown payload_type: {self.payload_type}")
        return self.payload
