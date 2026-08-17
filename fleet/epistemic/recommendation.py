"""Recommendation — an advisory artifact that carries NO authority.

The invariant enforced here (R2 / 2E synthesis) is structural, not conventional:

    recommendation  !=  authorization

``authority`` is fixed to the literal ``"NONE"``. It is asserted in
``__post_init__`` (a constructing agent cannot set it otherwise) AND hardcoded
into ``state()`` (so the serialized form can never claim authority even if the
in-memory field were somehow bypassed). There is deliberately **no method** to
convert a Recommendation into a Proposal — the absence of a conversion path is
the type-level guard preventing silent promotion to authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, List

from .artifact import Artifact


class AuthorityPromotionError(Exception):
    """Raised when an advisory artifact is mistakenly treated as authority."""


@dataclass(frozen=True)
class Recommendation(Artifact):
    """Advisory only. Structurally incapable of granting authority."""

    KIND: ClassVar[str] = "recommendation"

    authority: str = "NONE"       # MUST remain "NONE" — see class guard
    target: str = ""              # what the recommendation concerns (subject/ref)
    action_suggestion: str = ""   # advisory descriptor / text
    rationale: str = ""
    evidence_refs: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.authority != "NONE":
            raise AuthorityPromotionError(
                "Recommendation.authority must be 'NONE'; recommendations carry no authority"
            )

    def state(self) -> dict:  # type: ignore[override]
        # Hardcode authority so the canonical form can never assert permission.
        return {
            **super().state(),
            "authority": "NONE",
            "target": self.target,
            "action_suggestion": self.action_suggestion,
            "rationale": self.rationale,
            "evidence_refs": self.evidence_refs,
        }


def assert_advisory(artifact: Artifact) -> None:
    """Guard helper: fail closed if an artifact falsely claims authority."""
    if getattr(artifact, "authority", "NONE") != "NONE":
        raise AuthorityPromotionError(
            f"{type(artifact).__name__} carries authority={getattr(artifact, 'authority')!r}; "
            "advisory artifacts must have authority='NONE'"
        )
