"""AuthorizationRequest — the boundary object immediately before governance.

This is the LAST object Phase 1 implements. It is a *request*, not a grant. It
may reference a ``Proposal`` (by hash), the requested capability, the exact
action, the governing conditions, and relevant evidence/lineage — but it grants
nothing. ``AuthorizationDecision``, ``AuthorityGrant``, and the deterministic
authorization function are deliberately NOT implemented here (Phase 2).

The intended future ladder (Phase 1 = left of the boundary):

    Proposition -> Belief/Assessment -> Recommendation -> Proposal
                -> AuthorizationRequest -> [PHASE 2] -> AuthorizationDecision
                -> execution / state transition
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .artifact import Artifact


@dataclass(frozen=True)
class AuthorizationRequest(Artifact):
    """A request for authorization. Grants no authority itself."""

    KIND: ClassVar[str] = "authorization_request"

    request_id: str = ""
    capability: str = ""                 # authority being REQUESTED (governance vocab)
    action_descriptor: str = ""          # EXACT action requested
    conditions: dict = field(default_factory=dict)  # context governance reads
    proposal_ref: str = ""               # hash link to Proposal (NOT embedded belief)

    def state(self) -> dict:  # type: ignore[override]
        return {
            **super().state(),
            "request_id": self.request_id,
            "capability": self.capability,
            "action_descriptor": self.action_descriptor,
            "conditions": self.conditions,
            "proposal_ref": self.proposal_ref,
        }
