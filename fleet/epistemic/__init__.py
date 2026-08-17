"""Neutral epistemic substrate (Phase 1 kernel + Phase 2 contract).

Phase 1 (kernel) — the neutral epistemic vocabulary, powerless by construction:
    Artifact, Proposition, Uncertainty, Evidence, Belief, Assessment,
    Recommendation, Proposal, AuthorizationRequest

Phase 2 (contract) — the agent authority contract, introduced strictly as a
contract increment. It names identity + the five scopes + the externally-issued
grant + the deterministic decision boundary. It does NOT wire the financial firm
into it, and it does NOT move any financial object (ProbabilityEstimate,
QuantEvidence, CalibrationRecord, Mandate, RiskLayer, TradeDecision) into this
package.

Dependency rule (enforced by fleet/tests/test_boundary_epistemic.py):

    fleet.epistemic  ->  fleet.crypto.foundation  ->  stdlib

Forbidden imports (the neutral layer is the LEAST-privileged layer):

    fleet.epistemic  X  fleet.cognition
    fleet.epistemic  X  exchange.quant
    fleet.epistemic  X  exchange.governance
    fleet.epistemic  X  fleet.fin
    fleet.epistemic  X  fleet.simenv
    fleet.epistemic  X  fleet.layers.*

The direction of dependency is:  financial / domain-specific cognition  ->  neutral
epistemic substrate  ->  governance (which consumes the substrate deterministically).

The decisive invariant:

    epistemic artifacts can influence what is PROPOSED,
    but they can NEVER become PERMISSION.
"""
# Phase 1 kernel
from .artifact import Artifact
from .proposition import Proposition
from .uncertainty import Uncertainty
from .evidence import Evidence
from .belief import Belief
from .assessment import Assessment
from .recommendation import Recommendation, assert_advisory, AuthorityPromotionError
from .proposal import Proposal
from .authorization import AuthorizationRequest

# Phase 2 contract
from .identity import AgentIdentity
from .scope import (
    EpistemicScope,
    EvidenceScope,
    ProposalScope,
    CapabilityScope,
    AuthorizationScope,
)
from .governance_constraints import GovernanceConstraints
from .authority import AuthorityGrant
from .decision import AuthorizationDecision, decide
from .contract import EpistemicContract

__all__ = [
    # Phase 1
    "Artifact",
    "Proposition",
    "Uncertainty",
    "Evidence",
    "Belief",
    "Assessment",
    "AuthorityPromotionError",
    "Recommendation",
    "assert_advisory",
    "Proposal",
    "AuthorizationRequest",
    # Phase 2
    "AgentIdentity",
    "EpistemicScope",
    "EvidenceScope",
    "ProposalScope",
    "CapabilityScope",
    "AuthorizationScope",
    "GovernanceConstraints",
    "AuthorityGrant",
    "AuthorizationDecision",
    "decide",
    "EpistemicContract",
]
