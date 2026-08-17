"""Neutral epistemic artifact base (Phase 1 kernel).

An ``Artifact`` is a frozen, content-addressed record of something that can be
known, asserted, evaluated, recommended, proposed, or requested. It owns only
the identity/provenance contract shared by every neutral epistemic object:

    * stable ``kind`` (class-level, deterministic per subtype)
    * ``producer`` (id of whoever produced it — agent / model / human / process)
    * ``ts`` (epoch seconds)
    * ``content_hash`` (derived solely from canonical ``state()``)

It does NOT carry authorization, capability, role, or model-internal fields.
Those belong to later phases (AgentContract / AuthorityGrant) or other layers.
The subtype owns its domain semantics; this base owns only the shared identity.

Canonicalization reuses the single repository primitive:
    fleet.crypto.foundation.canonical_bytes + sha256
No second hashing mechanism is introduced.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from fleet.crypto.foundation import canonical_bytes, sha256


@dataclass(frozen=True)
class Artifact:
    """Frozen, content-addressed base for every neutral epistemic object."""

    KIND: ClassVar[str] = "artifact"

    producer: str
    ts: int = 0
    content_hash: str = ""

    def state(self) -> dict:
        """Canonical, signature-excluded state. Must be JSON-serializable."""
        return {
            "kind": self.KIND,
            "producer": self.producer,
            "ts": self.ts,
        }

    def compute_hash(self) -> str:
        """Content-derived identity; depends only on canonical state."""
        return sha256(canonical_bytes(self.state()))

    def __post_init__(self) -> None:
        # Frozen dataclass: attribute reassignment is blocked by the interpreter,
        # and identity (content_hash) is fixed at construction, so in-place dict
        # mutation cannot change an object's hash. This matches the repo-wide
        # convention for immutable dataclasses (e.g. ProbabilityEstimate).
        if not self.content_hash:
            object.__setattr__(self, "content_hash", self.compute_hash())

    def __hash__(self) -> int:
        # Identity is the content-derived hash, never object/memory state.
        return hash(self.content_hash)
