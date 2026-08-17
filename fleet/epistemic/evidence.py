"""Neutral Evidence (lineage node).

Evidence describes a derived or observed fact and its provenance as a hash
chain. It does NOT verify, audit, or evaluate — verification is implemented by
the existing ``fleet.layers.verification`` (``evaluate_intel``) and the
``VerificationLog`` / ``VerificationRow`` ledger in ``fleet/api/schema.py``.
The epistemic layer *represents* evidence; the verification layer *evaluates*
it. This module imports neither ``fleet.layers`` nor ``fleet.fin``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, List

from .artifact import Artifact


@dataclass(frozen=True)
class Evidence(Artifact):
    """A provenance-carrying evidence record linking back to its inputs."""

    KIND: ClassVar[str] = "evidence"

    evidence_kind: str = "observation"   # observation|retrieved|statistic|inference|...
    payload: dict = field(default_factory=dict)
    inputs: List[str] = field(default_factory=list)  # hashes of upstream Observation/Evidence

    def state(self) -> dict:  # type: ignore[override]
        return {
            **super().state(),
            "evidence_kind": self.evidence_kind,
            "payload": self.payload,
            "inputs": self.inputs,
        }
