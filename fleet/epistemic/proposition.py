"""Neutral Proposition (F1 structured statement target).

A Proposition is the *linchpin* of the epistemic vocabulary: two beliefs are
"about the same thing" iff their Propositions match on
``(domain, subject, predicate, params)``. That is what makes disagreement and
calibration computable.

It is deliberately domain-neutral:
    * quantitative finance: domain="market_probability", subject="KXIN-2026",
      predicate="P_yes"
    * incident response:    domain="incident_compromised", subject="host-17",
      predicate="is_compromised"
    * scientific research:  domain="hypothesis_true", subject="H3",
      predicate="will_occur"

No probability, no trading, no authority fields. Just enough to identify the
statement deterministically.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from fleet.crypto.foundation import canonical_bytes, sha256


@dataclass(frozen=True)
class Proposition:
    """A typed statement/question target that epistemic artifacts refer to."""

    domain: str
    subject: str
    predicate: str
    params: dict = field(default_factory=dict)
    proposition_hash: str = ""

    def state(self) -> dict:
        return {
            "domain": self.domain,
            "subject": self.subject,
            "predicate": self.predicate,
            "params": self.params,
        }

    def compute_hash(self) -> str:
        return sha256(canonical_bytes(self.state()))

    def __post_init__(self) -> None:
        if not self.proposition_hash:
            object.__setattr__(self, "proposition_hash", self.compute_hash())

    def __hash__(self) -> int:
        return hash(self.proposition_hash)
