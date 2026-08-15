"""Sovereign Cognitive Architecture — Scientific Knowledge Compiler (D28, L0).

A *reference* implementation of the CompiledKnowledge producer. It transforms
verified SourcedEvidence into a structured entity/relationship/claim graph with
signed provenance lineage.

DESIGN CONSTRAINTS (enforced by the import wall in test_boundary.py):
  * This module imports ONLY ``fleet.crypto`` + ``fleet.layers.handoff``.
  * It produces evidence. It does NOT authorize, decide, or execute.
  * The compiler is DETERMINISTIC for reproducibility: same inputs -> same
    compiled artifact (canonical hashing). The reference compiler performs
    lightweight, fully-deterministic extraction (entity/claim capture from
    structured evidence fields). A production SKC may layer a probabilistic
    model on top, but the *schema and signing contract* defined here is what
    governance and the verifier rely on.

The verifier (D-D) only ever checks that a CompiledKnowledge artifact:
  (1) was signed by its claimed producer cert,
  (2) cites source ids that resolve to real artifacts,
  (3) carries no governance field,
  (4) is bound to the proposal and unmodified.
It never re-runs the compiler and never judges semantic correctness.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fleet.crypto.foundation import AgentCert, sha256
from fleet.layers.handoff import Handoff, HandoffError


# Deterministic entity capture: capitalized multi-word tokens and acronyms.
_ENTITY_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}|[A-Z]{2,})\b")


def _capture_entities(text: str) -> List[str]:
    seen: List[str] = []
    for m in _ENTITY_RE.finditer(text or ""):
        ent = " ".join(m.group(0).split())
        if ent not in seen:
            seen.append(ent)
    return seen


@dataclass
class CompiledKnowledge:
    """Typed wrapper around the CompiledKnowledge handoff payload (D28)."""

    compile_id: str
    compiler_cert_id: str
    entities: List[str] = field(default_factory=list)
    relationships: List[Dict[str, str]] = field(default_factory=list)
    claims: List[Dict[str, Any]] = field(default_factory=list)
    contradictions: List[Dict[str, Any]] = field(default_factory=list)
    provenance: List[Dict[str, Any]] = field(default_factory=list)

    # --- build from verified evidence ------------------------------------
    @classmethod
    def from_evidence(
        cls,
        compile_id: str,
        compiler_cert: AgentCert,
        evidence: List[Dict[str, Any]],
    ) -> "CompiledKnowledge":
        """Compile a list of verified SourcedEvidence payloads deterministically.

        Each evidence item must carry an ``evidence_id`` and ``extract``; its
        ``source_hash`` (if present) is recorded in provenance so the verifier
        can prove the citation resolves.
        """
        entities: List[str] = []
        claims: List[Dict[str, Any]] = []
        provenance: List[Dict[str, Any]] = []
        for ev in evidence:
            eid = ev.get("evidence_id")
            if not eid:
                raise HandoffError("evidence without evidence_id cannot be compiled")
            extract = ev.get("extract", "")
            for ent in _capture_entities(extract):
                if ent not in entities:
                    entities.append(ent)
            claims.append({"claim": extract, "source_refs": [eid]})
            provenance.append({
                "source_id": eid,
                "source_hash": ev.get("source_hash", sha256(eid.encode())),
                "retrieved_at": ev.get("collected_at", 0),
            })
        return cls(
            compile_id=compile_id,
            compiler_cert_id=compiler_cert.agent_id,
            entities=entities,
            claims=claims,
            provenance=provenance,
        )

    # --- serialization ----------------------------------------------------
    def to_payload(self) -> Dict[str, Any]:
        """Return the canonical CompiledKnowledge dict (no governance fields)."""
        return {
            "compile_id": self.compile_id,
            "compiler_cert_id": self.compiler_cert_id,
            "entities": list(self.entities),
            "relationships": list(self.relationships),
            "claims": list(self.claims),
            "contradictions": list(self.contradictions),
            "provenance": list(self.provenance),
        }

    def sign(self, compiler_cert: AgentCert, compiler_key) -> Handoff:
        """Wrap this compiled knowledge in a signed Handoff (Handoff.make)."""
        return Handoff.make(
            compiler_cert, compiler_key, "CompiledKnowledge", self.to_payload()
        )

    @staticmethod
    def verify_lineage(
        payload: Dict[str, Any], known_source_ids: set
    ) -> None:
        """D28/D-D: prove the citation resolves. Does NOT judge truth.

        Raises HandoffError if a provenance source_id is unknown. Governance
        uses this to confirm the artifact's lineage is anchored to real
        evidence; it never asks whether the claims are semantically correct.
        """
        from fleet.layers.handoff import _validate_compiled_knowledge

        _validate_compiled_knowledge(payload, known_source_ids)
