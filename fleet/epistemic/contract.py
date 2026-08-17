"""Phase 2 — EpistemicContract: the five-scope agent definition (R1).

The contract bundles an agent's identity and its five independent scopes. Authority
is the ONLY dimension that grants power, and it lives in an *externally-signed*
AuthorityGrant referencing the AuthorizationScope — never inside this bundle.

The contract is purely descriptive metadata. It holds NO permission. The act of
authorization is `decide()` over a valid `AuthorityGrant` (authority.py / decision.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Optional

from .identity import AgentIdentity
from .scope import (
    AuthorizationScope,
    CapabilityScope,
    EpistemicScope,
    EvidenceScope,
    ProposalScope,
)


@dataclass(frozen=True)
class EpistemicContract:
    """An agent as five independent scopes + identity. No capability grant here."""

    KIND: ClassVar[str] = "epistemic_contract"

    identity: AgentIdentity
    epistemic_scope: EpistemicScope
    evidence_scope: EvidenceScope
    proposal_scope: ProposalScope
    capability_scope: CapabilityScope
    authorization_scope: AuthorizationScope

    # A *reference* to the externally-issued grant (by hash). The grant itself is
    # not stored here; authorization is decided against the live grant at request time.
    authority_grant_ref: Optional[str] = None

    def state(self) -> dict:
        return {
            "kind": self.KIND,
            "identity": self.identity.state(),
            "epistemic_scope": self.epistemic_scope.state(),
            "evidence_scope": self.evidence_scope.state(),
            "proposal_scope": self.proposal_scope.state(),
            "capability_scope": self.capability_scope.state(),
            "authorization_scope": self.authorization_scope.state(),
            "authority_grant_ref": self.authority_grant_ref,
        }

    def compute_hash(self) -> str:
        from fleet.crypto.foundation import canonical_bytes, sha256
        return sha256(canonical_bytes(self.state()))
