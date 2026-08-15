"""Sovereign Cognitive Architecture — Calibration loop (D28, L3 / D-E / D-G).

An ``AlignmentEvent`` is a SIGNED, REVIEWABLE record of a calibration adjustment
to the cognition layer. It tunes cognition-local configuration ONLY (e.g. persona
weights, uncertainty temperature) — it MUST NOT touch governance (disposition,
capability, or any threshold that changes an authorization verdict). See
``validate_alignment_payload`` for the fail-closed guard.

The event is emitted to the audit ledger by the CALLER (runtime / demo), which
lives OUTSIDE the import wall. This module only builds + signs the artifact,
keeping the import wall (``fleet.crypto`` + ``fleet.layers.handoff`` only).

D-G: the calibration loop may adapt richness; it must never remove the
constitutional adversarial perspectives. The persona SET is protected (see
``fleet.cognition.persona``).

Run A = Run B (M0) is preserved: calibration changes the *content* of signals
cognition emits, never the verdict — the gate never receives cognition state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict

from fleet.crypto.foundation import AgentCert, canonical_bytes, sha256
from fleet.layers.handoff import Handoff, HandoffError, sign_payload, verify_payload_sig


# Calibration may tune these cognition-local scopes only.
ALLOWED_CALIBRATION_SCOPES = {
    "persona_weights",
    "uncertainty_calibration",
    "evidence_quality_weights",
}

# Calibration MUST NOT carry these governance fields (would be a backdoor to auth).
_FORBIDDEN_CALIBRATION_FIELDS = {
    "disposition", "authorization", "capability", "decision", "granted",
    "requires_human_review", "blocked", "final", "threshold_override",
}


@dataclass
class AlignmentEvent:
    """A signed calibration adjustment to the cognition layer (D-E)."""

    event_id: str
    operator_cert_id: str
    scope: str
    adjustment: Dict[str, Any]
    rationale: str = ""
    ts: int = 0
    prior_event_id: str = ""

    def to_payload(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items()}

    @property
    def event_hash(self) -> str:
        return sha256(canonical_bytes(self.to_payload()))

    def sign(self, cert: AgentCert, key) -> Handoff:
        validate_alignment_payload(self.to_payload())
        return Handoff.make(cert, key, "AlignmentEvent", self.to_payload())

    def verify_sig(self, sig_hex: str, cert: AgentCert) -> bool:
        return verify_payload_sig(self.to_payload(), sig_hex, cert)


def validate_alignment_payload(p: Dict[str, Any]) -> None:
    """Fail closed if calibration carries a governance field or an out-of-scope adjustment."""
    leaked = _FORBIDDEN_CALIBRATION_FIELDS & set(p.get("adjustment", {}))
    if leaked:
        raise HandoffError(
            f"AlignmentEvent calibration must not carry governance fields: {leaked}")
    if p.get("scope") not in ALLOWED_CALIBRATION_SCOPES:
        raise HandoffError(
            f"AlignmentEvent scope is not cognition-local: {p.get('scope')}")


# Cognition-local weight state. NEVER an input to an authorization gate.
@dataclass
class CognitionState:
    persona_weights: Dict[str, float] = field(default_factory=lambda: {
        "skeptic": 1.0, "falsifier": 1.0, "risk": 1.0,
        "optimist": 1.0, "domain_expert": 1.0,
    })
    uncertainty_temp: float = 1.0

    def apply_alignment(self, event: AlignmentEvent) -> "CognitionState":
        """Pure: apply a signed AlignmentEvent to cognition-local state ONLY.

        Returns a NEW state. Does NOT touch governance. The gate never sees this
        state, so Run A = Run B (M0) is preserved: calibration changes what
        signals cognition emits, never the verdict.
        """
        validate_alignment_payload(event.to_payload())
        if event.scope == "persona_weights":
            new_weights = dict(self.persona_weights)
            for k, v in event.adjustment.items():
                if k in new_weights:
                    new_weights[k] = float(v)
            return CognitionState(persona_weights=new_weights,
                                  uncertainty_temp=self.uncertainty_temp)
        if event.scope == "uncertainty_calibration":
            temp = float(event.adjustment.get("temperature", self.uncertainty_temp))
            return CognitionState(persona_weights=dict(self.persona_weights),
                                  uncertainty_temp=temp)
        # evidence_quality_weights and unknown-but-allowed scopes: no-op state change
        return CognitionState(persona_weights=dict(self.persona_weights),
                              uncertainty_temp=self.uncertainty_temp)
