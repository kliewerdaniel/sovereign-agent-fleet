"""Phase 4 (M0) — governance issuer side of the SECOND adapter.

Structurally identical to ``exchange/epistemic_adapter/authority.py``. The
neutral substrate (``fleet.epistemic``) deliberately CANNOT mint authority;
``AuthorityGrant`` is a data holder and ``verify_grant`` only validates. This
adapter holds the trusted issuer Ed25519 key and signs grants that ``decide()``
later verifies against ``public_key_pem``.

The point of having a SECOND, identical issuer: the substrate cannot distinguish
an incident-response grant from an exchange grant. Its decision function reads
only the grant's scope/epoch and the deterministic policy — never the domain.
Two domains, one substrate, zero substrate edits.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from fleet.crypto.foundation import canonical_bytes
from fleet.epistemic.authority import AuthorityGrant
from fleet.epistemic.scope import AuthorizationScope


@dataclass
class GovernanceAuthority:
    """The trusted issuer of AuthorityGrants for the incident domain.

    Holds the governance Ed25519 private key. Issues grants that ``decide()``
    will later verify against ``public_key_pem`` (the trust anchor). This object
    is the ONLY place in this adapter that signs grants; the substrate has no
    equivalent capability.
    """

    private_key: Ed25519PrivateKey
    governance_role: str = "SecurityOps"

    @property
    def public_key_pem(self) -> str:
        return self.private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    def issue_grant(
        self,
        *,
        grant_id: str,
        agent_id: str,
        authorization_scope: AuthorizationScope,
        epoch: int,
        now: int,
        ttl_seconds: int = 3600,
        governance_role: Optional[str] = None,
    ) -> AuthorityGrant:
        """Sign a fresh, externally-issued AuthorityGrant.

        The grant binds to the agent id, the referenced AuthorizationScope (by
        hash), the current epoch (R3 supersession), and a TTL backstop. The
        signature is computed over the same canonical body ``verify_grant``
        checks.
        """
        role = governance_role or self.governance_role
        grant = AuthorityGrant(
            grant_id=grant_id,
            agent_id=agent_id,
            authorization_scope_hash=authorization_scope.compute_hash(),
            epoch=epoch,
            issued_at=now,
            expires_at=now + ttl_seconds,
            governance_role=role,
            signer_pubkey_pem=self.public_key_pem,  # descriptive; verifier pins trust
            signature="",
        )
        body = canonical_bytes(grant.state())
        sig = self.private_key.sign(body).hex()
        return replace(grant, signature=sig)

    def verify_grant(self, grant: AuthorityGrant) -> bool:
        """Verify a grant against THIS authority's trusted key (mirrors decide)."""
        if not grant.signature:
            return False
        try:
            key = serialization.load_pem_public_key(self.public_key_pem.encode("utf-8"))
            if not isinstance(key, Ed25519PublicKey):
                return False
            key.verify(bytes.fromhex(grant.signature), canonical_bytes(grant.state()))
            return True
        except (InvalidSignature, ValueError, Exception):
            return False


def issue_grant(
    *,
    authority: GovernanceAuthority,
    grant_id: str,
    agent_id: str,
    authorization_scope: AuthorizationScope,
    epoch: int,
    now: int,
    ttl_seconds: int = 3600,
    governance_role: Optional[str] = None,
) -> AuthorityGrant:
    """Convenience wrapper around ``GovernanceAuthority.issue_grant``."""
    return authority.issue_grant(
        grant_id=grant_id,
        agent_id=agent_id,
        authorization_scope=authorization_scope,
        epoch=epoch,
        now=now,
        ttl_seconds=ttl_seconds,
        governance_role=governance_role,
    )
