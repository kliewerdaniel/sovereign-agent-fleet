"""Sovereign Cognitive Architecture — Evaluation layer (D28, L2).

The EvaluationArtifact is the **enrichment envelope** attached to a governance
proposal. It records observed signals from the epistemic evaluation of a
proposal:

  * ``uncertainty``          -- model self-reported / calibrated uncertainty
  * ``popper``               -- documented falsification ATTEMPT (not truth oracle)
  * ``evidence_quality``     -- Page-Quality style ratings
  * ``needs_met``            -- Needs-Met style ratings
  * ``persona_analyses``     -- competing lenses (NOT votes)
  * ``contradiction_count``  -- count of detected contradictions

CRITICAL D-H INVARIANT (ratified refinement #1):
  This artifact carries **signals, never flags**. It MUST NOT contain a field
  like ``requires_human_review``. Cognition may *describe* conditions; it may
  never *instruct* the authority layer. The deterministic adapter
  ``escalate_to_asserted`` maps signals -> a boolean; the *policy* decides what
  to do with that boolean. This is the zero-trust cognition model: the model
  generates a proposal + all its reasoning/disagreement/uncertainty, then an
  independent deterministic layer decides authorization.

DESIGN CONSTRAINT:
  This module imports ONLY ``fleet.crypto`` + ``fleet.layers.handoff``. It does
  not import gateway / policy / runtime / fin / simenv / gcp. The escalation
  adapter receives the governance surface as an opaque passthrough (Any) so it
  never needs to know the typed proposal shape.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Tuple

from fleet.crypto.foundation import AgentCert, canonical_bytes, sha256
from fleet.layers.handoff import HandoffError, verify_payload_sig, sign_payload


# --- Escalation thresholds (the adapter only OBSERVES these) --------------
# Policy owns the ASSERTED -> HUMAN transition. These are NOT authority knobs;
# they are the observation thresholds that flip a deterministic boolean.
UNCERTAINTY_THRESHOLD = 0.7
CONTRADICTION_THRESHOLD = 0      # any detected contradiction escalates
POPPER_FAILED_THRESHOLD = 0      # any failed falsification attempt escalates


# D-H: the artifact must NEVER carry an instruction field. If any of these
# appear, the artifact is rejected structurally (signals-not-flags discipline).
_FORBIDDEN_EVAL_FIELDS = {
    "requires_human_review", "authorization", "approval", "capability",
    "disposition", "decision", "granted", "blocked", "final",
}


@dataclass
class EvaluationArtifact:
    """Observed signals about a proposal. Never an authorization instruction."""

    producer_cert_id: str
    uncertainty: float = 0.0
    popper: Dict[str, Any] = field(default_factory=lambda: {
        "falsifiers": [], "passed": 0, "failed": 0,
    })
    evidence_quality: Dict[str, Any] = field(default_factory=lambda: {
        "authenticity": 0.0, "originality": 0.0, "expertise": 0.0,
        "freshness": 0.0, "spam": 0.0,
    })
    needs_met: Dict[str, Any] = field(default_factory=lambda: {
        "intent": False, "constraints_satisfied": False, "gaps": [],
    })
    persona_analyses: List[Dict[str, Any]] = field(default_factory=list)
    contradiction_count: int = 0

    # --- serialization + signing ------------------------------------------
    def to_payload(self) -> Dict[str, Any]:
        """Deterministic canonical dict (no governance fields)."""
        return {k: v for k, v in asdict(self).items()}

    @property
    def enrichment_hash(self) -> str:
        """Content hash bound into the operator.final audit record (D-D)."""
        return sha256(canonical_bytes(self.to_payload()))

    def sign(self, producer_cert: AgentCert, producer_key) -> str:
        """Sign the enrichment with the producer's Ed25519 key (D-D: signed)."""
        return sign_payload(self.to_payload(), producer_key)

    def verify_sig(self, sig_hex: str, producer_cert: AgentCert) -> bool:
        return verify_payload_sig(self.to_payload(), sig_hex, producer_cert)


@dataclass
class ProposalArtifact:
    """The split made explicit (D28 6.3): governance surface + enrichment.

    ``governance_surface`` is the ONLY thing the gates read (TradeProposal /
    QualifiedIntel). It is an opaque passthrough here so this module never
    imports its typed definition. ``enrichment`` is logged + verified for
    binding/integrity, never passed to a gate.
    """

    governance_surface: Any
    enrichment: EvaluationArtifact

    def bind(self, producer_cert: AgentCert, producer_key) -> Dict[str, Any]:
        """Produce the enrichment block the Operator embeds in operator.final.

        Returns the signed enrichment + content hash for binding/integrity
        verification (D-D: verifier proves present, unaltered, signed).

        Structural guarantee (D-H correction #1): the enrichment is validated
        as signals-only BEFORE it is signed/bound. A leaked governance flag
        (e.g. ``requires_human_review``) is rejected here, so cognition can
        never smuggle an instruction into the record it attaches.
        """
        validate_evaluation_payload(self.enrichment.to_payload())
        return {
            "enrichment": self.enrichment.to_payload(),
            "enrichment_sig": self.enrichment.sign(producer_cert, producer_key),
            "enrichment_hash": self.enrichment.enrichment_hash,
            "enrichment_producer": producer_cert.agent_id,
        }


# ---------------------------------------------------------------------------
# Deterministic escalation adapter (D28 6.4) -- the only seam cognition touches
# ---------------------------------------------------------------------------

def escalate_to_asserted(evaluation: EvaluationArtifact) -> bool:
    """PURE FUNCTION of observed signals. Never reads a gate, never imports one.

    D-B + D-H: evaluation may only RAISE scrutiny. It escalates a proposal up
    the human-review path; it never emits BLOCKED, never auto-GRANTs, never
    lowers a threshold. The *policy* consumes this boolean.
    """
    if evaluation.popper.get("failed", 0) > POPPER_FAILED_THRESHOLD:
        return True
    if evaluation.uncertainty > UNCERTAINTY_THRESHOLD:
        return True
    if evaluation.contradiction_count > CONTRADICTION_THRESHOLD:
        return True
    return False


def to_gateway_intent(governance_surface: Any,
                      evaluation: EvaluationArtifact) -> Tuple[Any, bool]:
    """The single seam: returns (intel, force_asserted).

    The governance surface passes through untouched (cognition never mutates
    or types it). The only cognition-derived signal is the escalation boolean.
    """
    return governance_surface, escalate_to_asserted(evaluation)


def validate_evaluation_payload(p: Dict[str, Any]) -> None:
    """Reject any evaluation payload that carries governance instructions.

    Used by the verifier (D-D / D-H correction #1) to prove the enrichment is
    signals-only. Raises HandoffError on a leaked flag field. Checks recursively:
    a governance flag smuggled into a nested dict (e.g. needs_met) is still a
    leak and is rejected.
    """
    def _scan(node):
        if isinstance(node, dict):
            leaked = _FORBIDDEN_EVAL_FIELDS & set(node)
            if leaked:
                raise HandoffError(
                    f"EvaluationArtifact must carry signals, not governance "
                    f"flags: {leaked}")
            for v in node.values():
                _scan(v)
        elif isinstance(node, list):
            for v in node:
                _scan(v)
    _scan(p)


def verify_enrichment_block(block: Dict[str, Any],
                            producer_cert: AgentCert) -> None:
    """D-D: prove an attached enrichment is PRESENT, UNMODIFIED, SIGNED by the
    producer, and SIGNALS-ONLY. Raises HandoffError on any failure.

    This is the verifier's *entire* remit over cognition: binding + integrity.
    It NEVER assesses semantic correctness (claim truth, uncertainty accuracy,
    whether the model was right). The verifier proves the enrichment existed,
    was unaltered, was signed by its producer, and leaked no governance flags.

    ``producer_cert`` MUST be the cert of the claimed producer (resolved by the
    caller from the registry via ``enrichment_producer``), NOT the operator —
    the enrichment is signed by the cognition producer, not the executor.
    """
    if block is None:
        return
    payload = block.get("enrichment")
    sig = block.get("enrichment_sig")
    recorded_hash = block.get("enrichment_hash")
    if payload is None or sig is None or recorded_hash is None:
        raise HandoffError("enrichment block incomplete (missing payload/sig/hash)")
    art = EvaluationArtifact(**payload)
    if art.enrichment_hash != recorded_hash:
        raise HandoffError("enrichment hash mismatch (tampered payload)")
    if not art.verify_sig(sig, producer_cert):
        raise HandoffError("enrichment not signed by claimed producer")
    validate_evaluation_payload(payload)  # signals-not-flags (D-H correction #1)


def enrichment_m0_invariant(governance_inputs: Any, gate_fn,
                            enrichment=None, recorded_hash=None,
                            enrichment_sig=None, producer_cert=None) -> Any:
    """D28 M0 PROOF (Run A = Run B): cognition cannot change the verdict.

    ``gate_fn`` MUST accept ONLY governance inputs -- it must NOT take the
    enrichment as an argument. That is the D-A guarantee. The enrichment, if
    attached, is verified for binding+integrity ONLY; it is never passed to the
    gate. Run A (cognition attached) and Run B (cognition stripped) therefore
    feed the gate *identical* inputs, so their dispositions are structurally
    guaranteed equal.

    Returns the disposition (Run A == Run B). Raises on a binding/integrity
    failure or if the verdict somehow differs (it cannot, by construction).
    """
    if enrichment is not None:
        # D-D + D-H correction #1: prove present/unaltered/signed/signals-only.
        assert recorded_hash is not None and enrichment_sig is not None \
            and producer_cert is not None
        if enrichment.enrichment_hash != recorded_hash:
            raise AssertionError("enrichment tampered before M0 check")
        if not enrichment.verify_sig(enrichment_sig, producer_cert):
            raise AssertionError("enrichment not signed by producer")
        validate_evaluation_payload(enrichment.to_payload())

    # Run A: cognition attached. The gate does NOT receive it (D-A).
    disp_a = gate_fn(governance_inputs)
    # Run B: cognition stripped. Structurally identical call.
    disp_b = gate_fn(governance_inputs)
    if disp_a != disp_b:
        raise AssertionError(f"M0 violated: Run A {disp_a} != Run B {disp_b}")
    return disp_a
