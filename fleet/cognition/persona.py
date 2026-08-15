"""Sovereign Cognitive Architecture — Persona MoE GraphRAG (D28, L1).

Personas are LENSES, not voters (D-C). Each persona applies a distinct analytical
perspective to a proposal / evidence and emits OBSERVED SIGNALS only. Those
signals feed ``EvaluationArtifact.persona_analyses`` (enrichment); they are NEVER
arguments to a gate (D-A), never votes, never dispositions.

The persona SET is PROTECTED EPISTEMIC INFRASTRUCTURE (D-G): the system cannot
autonomously remove the adversarial perspectives — ``skeptic`` / ``falsifier`` /
``risk`` are constitutional checks. Removing one fails closed
(``ensure_constitutional_coverage``).

The reference implementation is DETERMINISTIC: it performs lightweight, fully
reproducible lens extraction (no model call). A production MoE would route each
persona to a DISTINCT backend — the D-C guarantee that real consensus requires
distinct backends is enforced by ``fleet.layers.consensus``. The schema and the
constitutional-guard contract defined here are what governance relies on.

Import wall: ONLY ``fleet.crypto`` + ``fleet.layers.handoff``.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from fleet.crypto.foundation import AgentCert, sha256
from fleet.layers.handoff import HandoffError


# D-G: constitutional perspectives the system may never prune. Their absence is a
# structural failure, not a tuning choice.
CONSTITUTIONAL_PERSONAS = ("skeptic", "falsifier", "risk")

_ROLE_DESCRIPTION = {
    "skeptic": "challenge assumptions / demand evidence",
    "falsifier": "attempt falsification / surface disconfirming cases",
    "risk": "surface downside / blast radius",
}


@dataclass
class Persona:
    """A single analytical lens. Descriptive only; never a voter."""

    persona_id: str
    role: str
    lens: str = ""
    # Production: route each persona to a DISTINCT backend (D-C real-consensus
    # guarantee). The reference implementation is backend-agnostic.
    backend: str = "default"

    @property
    def is_constitutional(self) -> bool:
        return self.role in CONSTITUTIONAL_PERSONAS

    def to_payload(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items()}


@dataclass
class PersonaAnalysis:
    """The OBSERVED signal a persona emits about a text/proposal.

    Signals only — never a disposition, vote, or authorization hint.
    """

    persona_id: str
    role: str
    observations: Dict[str, Any] = field(default_factory=dict)
    constitutional: bool = False

    def to_payload(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items()}


# Lightweight deterministic lens extractors. Each returns an observations dict of
# pure signals. Kept tiny + reproducible; a production lens would be a model call.
def _skeptic_obs(text: str) -> Dict[str, Any]:
    assumptions = len(re.findall(r"\b(assume|should|must|clearly|obviously)\b",
                                 text, re.I))
    unverified = 1 if ("?" in text or "untested" in text.lower()) else 0
    return {"assumptions_flagged": assumptions, "unverified_claims": unverified}


def _falsifier_obs(text: str) -> Dict[str, Any]:
    disconfirming = len(re.findall(r"\b(but|however|counter|except|fail)\b",
                                   text, re.I))
    return {"disconfirming_cues": disconfirming}


def _risk_obs(text: str) -> Dict[str, Any]:
    downside = len(re.findall(
        r"\b(risk|loss|exposure|blast|down|breach|compromise)\b", text, re.I))
    return {"downside_cues": downside}


_LENS = {
    "skeptic": _skeptic_obs,
    "falsifier": _falsifier_obs,
    "risk": _risk_obs,
}


def apply_persona(text: str, persona: Persona) -> PersonaAnalysis:
    """Apply one persona lens to ``text``, producing observed signals only."""
    fn = _LENS.get(persona.role)
    obs = fn(text) if fn else {}
    return PersonaAnalysis(
        persona_id=persona.persona_id,
        role=persona.role,
        observations=obs,
        constitutional=persona.is_constitutional,
    )


def apply_personas(text: str, personas: List[Persona]) -> List[Dict[str, Any]]:
    """Apply a SET of persona lenses. Constitutional coverage is enforced (D-G)."""
    ensure_constitutional_coverage(personas)
    return [apply_persona(text, p).to_payload() for p in personas]


def ensure_constitutional_coverage(personas: List[Persona]) -> None:
    """D-G: fail closed if any constitutional perspective is absent."""
    present = {p.role for p in personas}
    missing = set(CONSTITUTIONAL_PERSONAS) - present
    if missing:
        raise HandoffError(
            f"Persona graph violates D-G: missing constitutional perspectives "
            f"{sorted(missing)}")


@dataclass
class PersonaGraph:
    """The M(oE) + GraphRAG framing: a protected set of lenses over a corpus.

    Construction and every analysis enforce constitutional coverage (D-G). The
    graph never produces a verdict; it produces signals attached to enrichment.
    """

    personas: List[Persona] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        ensure_constitutional_coverage(self.personas)

    def analyze(self, text: str) -> Dict[str, Any]:
        ensure_constitutional_coverage(self.personas)
        return {
            "persona_analyses": apply_personas(text, self.personas),
            "entity_count": len(self.entities),
            "constitutional_present": sorted(
                {p.role for p in self.personas
                 if p.role in CONSTITUTIONAL_PERSONAS}),
        }


def default_persona_graph() -> PersonaGraph:
    """The reference constitutional graph: 3 protected lenses + 2 enrichment lenses."""
    personas = [
        Persona("p-skeptic", "skeptic", _ROLE_DESCRIPTION["skeptic"]),
        Persona("p-falsifier", "falsifier", _ROLE_DESCRIPTION["falsifier"]),
        Persona("p-risk", "risk", _ROLE_DESCRIPTION["risk"]),
        Persona("p-optimist", "optimist", "surface upside / supporting cases"),
        Persona("p-domain", "domain_expert", "domain-specific contextual read"),
    ]
    return PersonaGraph(personas=personas, entities=[])
