"""Proposal — an intent/request artifact (cognition-owned).

A Proposal expresses what an agent recommends should happen, including the
requested action descriptor and the epistemic references it rests on. But:

    Proposal  !=  Authorization

A Proposal contains no capability grant, no authority grant, no mutable risk
budget, and no field a downstream consumer could read as "approved". It is
suitable for later transformation into an ``AuthorizationRequest`` (Phase 2); it
is not permission itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, List

from .artifact import Artifact


@dataclass(frozen=True)
class Proposal(Artifact):
    """An intent/request artifact. Grants no authority."""

    KIND: ClassVar[str] = "proposal"

    action_descriptor: str = ""      # WHAT is intended (descriptor, not a verb)
    rationale: str = ""              # human-readable only; NOT read by gates
    target_ref: str = ""             # proposition/subject hash this targets
    belief_refs: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)

    def state(self) -> dict:  # type: ignore[override]
        return {
            **super().state(),
            "action_descriptor": self.action_descriptor,
            "rationale": self.rationale,
            "target_ref": self.target_ref,
            "belief_refs": self.belief_refs,
            "evidence_refs": self.evidence_refs,
        }
