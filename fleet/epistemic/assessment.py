"""Assessment — a deterministic evaluation of state against a condition.

An Assessment is NOT a Belief. Where a Belief carries a probabilistic future
orientation, an Assessment states the result of comparing observed state against
a policy condition. Examples (neutral, domain-general):

    exposure=12.3%, limit=10%      -> result="BREACH"
    freshness=17h, threshold=12h   -> result="STALE"
    indicator within band          -> result="OK"

It carries no probability, no future orientation, no authorization. The
verdict-like ``result`` string is a *classification*, not a permission.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .artifact import Artifact


@dataclass(frozen=True)
class Assessment(Artifact):
    """Deterministic state-vs-policy evaluation. Not probabilistic cognition."""

    KIND: ClassVar[str] = "assessment"

    subject: str = ""            # what was evaluated, e.g. "portfolio:EXC"
    condition: dict = field(default_factory=dict)   # policy condition evaluated
    observed: dict = field(default_factory=dict)    # observed state
    result: str = "OK"           # "OK" | "BREACH" | "STALE" | "PASS" | "FAIL" | ...
    reason: str = ""

    def state(self) -> dict:  # type: ignore[override]
        return {
            **super().state(),
            "subject": self.subject,
            "condition": self.condition,
            "observed": self.observed,
            "result": self.result,
            "reason": self.reason,
        }
