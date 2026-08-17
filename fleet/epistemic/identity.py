"""Phase 2 — AgentIdentity (the runtime security primitive, R1).

`AgentIdentity` is the *least* an agent must be: a governance-issued
certificate. It carries NO scope, NO capability grant, NO authority. Those are
separate (EpistemicContract + externally-signed AuthorityGrant). The identity is
issued by the IdentityRoot and signed by a root key the agent does not hold, so
the agent cannot alter its own `capabilities`/`role`/`cert_seq`.

Reuses `AgentCert` from `fleet.crypto.foundation` (the existing, implemented
certificate type) rather than duplicating it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Tuple

from fleet.crypto.foundation import AgentCert


@dataclass(frozen=True)
class AgentIdentity:
    """Who the agent is, as certified by governance. Nothing more."""

    KIND: ClassVar[str] = "agent_identity"

    agent_id: str
    role: str
    capabilities: Tuple[str, ...]      # operational capabilities (from the cert)
    cert_seq: int
    issued_at: int
    expires_at: int
    pubkey_pem: str
    root_sig: str

    @classmethod
    def from_cert(cls, cert: AgentCert) -> "AgentIdentity":
        """Build an identity view from an existing (root-signed) AgentCert."""
        return cls(
            agent_id=cert.agent_id,
            role=cert.role,
            capabilities=tuple(cert.capabilities),
            cert_seq=cert.cert_seq,
            issued_at=cert.issued_at,
            expires_at=cert.expires_at,
            pubkey_pem=cert.pubkey_pem,
            root_sig=cert.root_sig,
        )

    def state(self) -> dict:
        return {
            "kind": self.KIND,
            "agent_id": self.agent_id,
            "role": self.role,
            "capabilities": self.capabilities,
            "cert_seq": self.cert_seq,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "pubkey_pem": self.pubkey_pem,
            "root_sig": self.root_sig,
        }

    def compute_hash(self) -> str:
        from fleet.crypto.foundation import canonical_bytes, sha256
        return sha256(canonical_bytes(self.state()))
