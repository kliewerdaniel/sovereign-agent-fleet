"""Phase 2 — GovernanceConstraints (neutral analog of a Mandate, R5/R6).

A domain-general container for the deterministic policy inputs an authorization
decision reads. It holds NO probability, NO confidence, NO score, NO capability
grant — only policy. The financial `Mandate` is the *implementation* of this for
the quant firm; this is the neutral generalization, and `Mandate` is NOT moved
into `fleet/epistemic/`.

`decision_for` is a pure, deterministic read: it maps a requested capability to
AUTO / HUMAN / BLOCKED using only the declared policy. It never consumes an
epistemic value.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Tuple


@dataclass(frozen=True)
class GovernanceConstraints:
    """Deterministic policy constraints an AuthorizationDecision may read."""

    KIND: ClassVar[str] = "governance_constraints"

    allowlist: Tuple[str, ...] = ()           # capabilities/actions explicitly permitted
    denylist: Tuple[str, ...] = ()            # always blocked
    require_human_approval: bool = False
    policy_refs: Tuple[str, ...] = ()         # opaque refs to policy docs/ids
    extra: dict = field(default_factory=dict)

    def decision_for(self, capability: str) -> str:
        """Neutral deterministic policy read. Returns one of:
        'BLOCKED' (denylisted), 'HUMAN' (allowed but needs a human in the loop),
        'AUTO' (allowed autonomously). Never reads probability/confidence/score.
        An unknown capability is escalated (HUMAN), never silently authorized."""
        if capability in self.denylist:
            return "BLOCKED"
        if capability in self.allowlist:
            return "HUMAN" if self.require_human_approval else "AUTO"
        return "HUMAN"

    def state(self) -> dict:
        return {
            "kind": self.KIND,
            "allowlist": self.allowlist,
            "denylist": self.denylist,
            "require_human_approval": self.require_human_approval,
            "policy_refs": self.policy_refs,
            "extra": self.extra,
        }

    def compute_hash(self) -> str:
        from fleet.crypto.foundation import canonical_bytes, sha256
        return sha256(canonical_bytes(self.state()))
