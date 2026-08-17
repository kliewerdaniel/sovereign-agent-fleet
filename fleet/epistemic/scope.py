"""Phase 2 — the five non-collapsible scopes (R1 / 2B-R).

Each scope is a *separate* descriptor of what an agent may do. They are never
merged into one "authority" blob, and capability != authorization is enforced by
the fact that `AuthorizationScope` lives in an externally-signed `AuthorityGrant`
(see `authority.py`), while the other four are epistemic/operational metadata the
agent itself can hold. The decision function only ever reads `AuthorizationScope`
through a valid grant; it never reads a score, probability, or calibration value.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Tuple


@dataclass(frozen=True)
class EpistemicScope:
    """What the agent may KNOW / claim / reason about."""

    KIND: ClassVar[str] = "epistemic_scope"
    proposition_domains: Tuple[str, ...] = ()   # e.g. ("market_probability", "incident_compromised")
    belief_kinds: Tuple[str, ...] = ()          # uncertainty kinds it may emit
    max_calibration_weight: float = 1.0

    def state(self) -> dict:
        return {
            "kind": self.KIND,
            "proposition_domains": self.proposition_domains,
            "belief_kinds": self.belief_kinds,
            "max_calibration_weight": self.max_calibration_weight,
        }

    def compute_hash(self) -> str:
        from fleet.crypto.foundation import canonical_bytes, sha256
        return sha256(canonical_bytes(self.state()))


@dataclass(frozen=True)
class EvidenceScope:
    """What evidence the agent may PRODUCE / CONSUME + lineage requirement."""

    KIND: ClassVar[str] = "evidence_scope"
    produces: Tuple[str, ...] = ()
    consumes: Tuple[str, ...] = ()
    requires_lineage: bool = False

    def state(self) -> dict:
        return {
            "kind": self.KIND,
            "produces": self.produces,
            "consumes": self.consumes,
            "requires_lineage": self.requires_lineage,
        }

    def compute_hash(self) -> str:
        from fleet.crypto.foundation import canonical_bytes, sha256
        return sha256(canonical_bytes(self.state()))


@dataclass(frozen=True)
class ProposalScope:
    """What action_descriptor kinds the agent may PROPOSE (never authorize)."""

    KIND: ClassVar[str] = "proposal_scope"
    action_descriptors: Tuple[str, ...] = ()

    def state(self) -> dict:
        return {"kind": self.KIND, "action_descriptors": self.action_descriptors}

    def compute_hash(self) -> str:
        from fleet.crypto.foundation import canonical_bytes, sha256
        return sha256(canonical_bytes(self.state()))


@dataclass(frozen=True)
class CapabilityScope:
    """Operational capabilities the agent's cert carries (what it may DO)."""

    KIND: ClassVar[str] = "capability_scope"
    capabilities: Tuple[str, ...] = ()

    def state(self) -> dict:
        return {"kind": self.KIND, "capabilities": self.capabilities}

    def compute_hash(self) -> str:
        from fleet.crypto.foundation import canonical_bytes, sha256
        return sha256(canonical_bytes(self.state()))


@dataclass(frozen=True)
class AuthorizationScope:
    """The discrete authority actions this agent MAY be granted.

    This describes *what could be granted* — it is NOT itself a grant. A real
    grant is an externally-signed `AuthorityGrant` (authority.py) that references
    an AuthorizationScope by hash. Merely holding this descriptor confers nothing.
    """

    KIND: ClassVar[str] = "authorization_scope"
    actions: Tuple[str, ...] = ()               # e.g. ("risk.halt", "exchange.trade_execute")
    governance_role: str = ""                   # e.g. "CRO", "CCO", "" for none

    def state(self) -> dict:
        return {
            "kind": self.KIND,
            "actions": self.actions,
            "governance_role": self.governance_role,
        }

    def compute_hash(self) -> str:
        from fleet.crypto.foundation import canonical_bytes, sha256
        return sha256(canonical_bytes(self.state()))
