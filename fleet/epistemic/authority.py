"""Phase 2 — externally-issued AuthorityGrant + authority epoch supersession (R3).

An AuthorityGrant is a SIGNED permission issued by governance (the IdentityRoot /
a governance key the agent does NOT hold). The agent cannot self-grant: it can
only present a grant whose signature verifies against the issuer's public key.

The grant binds to:
  * the agent's identity hash (so it cannot be transferred),
  * an AuthorizationScope hash (what is being granted),
  * an epoch (R3: stale grants are structurally rejected),
  * mandatory TTL backstop (R3: clock as a secondary safety net).

`verify_grant` accepts the issuer's Ed25519 public key as an argument — the
substrate never imports, derives, or stores the governance key. This keeps the
import wall intact and makes "externally issued" literal: the substrate validates,
it does not mint.

The decision boundary (decide) reads ONLY the grant's scope/epoch and the
governance policy. It NEVER reads probability, confidence, score, or calibration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Optional


@dataclass(frozen=True)
class AuthorityGrant:
    """An externally-signed permission. Carries NO epistemic content."""

    KIND: ClassVar[str] = "authorization_grant"

    grant_id: str
    agent_id: str
    authorization_scope_hash: str
    epoch: int
    issued_at: int
    expires_at: int                       # TTL backstop (R3)
    governance_role: str = ""
    signature: str = ""                  # Ed25519 sig over canonical body (excl. sig)
    signer_pubkey_pem: str = ""          # PEM of the issuer; passed in for verification

    def state(self) -> dict:
        # Signature is excluded from the signed body (matches _UNSIGNED convention):
        # the hash/signature is derived from the rest, never from itself. The
        # issuer's public key is part of the signed body (like AgentCert.pubkey_pem),
        # so it cannot be swapped without invalidating the signature.
        return {
            "kind": self.KIND,
            "grant_id": self.grant_id,
            "agent_id": self.agent_id,
            "authorization_scope_hash": self.authorization_scope_hash,
            "epoch": self.epoch,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "governance_role": self.governance_role,
            "signer_pubkey_pem": self.signer_pubkey_pem,
        }

    def compute_hash(self) -> str:
        from fleet.crypto.foundation import canonical_bytes, sha256
        return sha256(canonical_bytes(self.state()))

    def verify_grant(self, issuer_pubkey_pem: Optional[str] = None) -> bool:
        """True iff the signature is valid and issued by the expected signer.

        `issuer_pubkey_pem` is the governance public key (passed in by the caller
        at verification time). If omitted, falls back to `self.signer_pubkey_pem`.

        The signature is computed over the canonical body EXCLUDING `signature`,
        matching the repo convention (canonical_bytes drops `sig`/`id`).
        """
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        from fleet.crypto.foundation import canonical_bytes

        pub_pem = issuer_pubkey_pem or self.signer_pubkey_pem
        if not pub_pem:
            return False
        body = canonical_bytes(self.state())
        try:
            key = serialization.load_pem_public_key(pub_pem.encode("utf-8"))
            if not isinstance(key, Ed25519PublicKey):
                return False
            key.verify(bytes.fromhex(self.signature), body)
            return True
        except Exception:
            return False

    def is_current(self, current_epoch: int, now: int) -> bool:
        """R3: epoch-supersession is primary; TTL is a backstop.

        A grant is usable only if its epoch is the current epoch AND it has not
        passed its TTL. Either condition failing => stale => rejected.
        """
        return self.epoch == current_epoch and self.expires_at > now
