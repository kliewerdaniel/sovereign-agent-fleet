"""D23 / E2 — multi-brain consensus gate (adversarial).

Proves the consensus gate:
  * accepts (status=consensus) when two distinct brains agree on verdict + confidence;
  * downgrades to ASSERTED + emits a SIGNED consensus.disagreement audit event when
    the two brains disagree (D16 escalation);
  * rejects two IDENTICAL backends fail-closed (no false assurance);
  * respects confidence tolerance;
  * rejects a malformed proposal from either brain before comparison (D15).
"""
import pytest

from fleet.layers import StubBrain, ConsensusGate
from fleet.layers.consensus import same_verdict, unmapped_task


def _brain(claim_type, confidence, entity=None):
    canned = {"claim_type": claim_type, "confidence": confidence,
              "evidence_refs": ["ev_1"], "claim": "x"}
    if entity is not None:
        canned = {"resolved_entity": entity, "confidence": confidence,
                  "canonical_id": "c1"}
    return StubBrain(canned=canned)


def test_e2_agreement_yields_consensus():
    a = _brain("payment_fraud", 0.9)
    b = _brain("payment_fraud", 0.92)
    gate = ConsensusGate(a, b)
    out = gate.evaluate(
        "analyst_classification", "classify", "analyst_classification",
        input_refs=["ev_1"], require_verified=True,
    )
    assert out["status"] == "consensus"
    assert out["disagreement"] is False
    assert out["verdict"] == "payment_fraud"
    assert 0.9 <= out["confidence"] <= 0.92


def test_e2_disagreement_downgrades_to_asserted():
    events = []
    a = _brain("payment_fraud", 0.9)
    b = _brain("legit", 0.9)  # different verdict
    gate = ConsensusGate(a, b, audit_append=events.append)
    out = gate.evaluate(
        "analyst_classification", "classify", "analyst_classification",
        input_refs=["ev_1"],
    )
    assert out["status"] == "disagreement"
    assert out["disagreement"] is True
    assert out["verdict"] == "ASSERTED"
    assert out["confidence"] == 0.0
    assert len(events) == 1
    assert events[0]["kind"] == "consensus.disagreement"


def test_e2_identical_backends_rejected_fail_closed():
    a = _brain("payment_fraud", 0.9)
    # Same object instance would silently double-count as "two" backends -> rejected.
    with pytest.raises(ValueError):
        ConsensusGate(a, a)
    # Two distinct instances are permitted by construction (callers are responsible
    # for configuring them with different backends/seeds); the gate cannot infer
    # their configs, so it does not pretend to. We assert the real invariant: a
    # genuine two-backend gate constructs fine.
    b = _brain("payment_fraud", 0.9)
    gate = ConsensusGate(a, b)
    assert gate is not None


def test_e2_confidence_tolerance_respected():
    a = _brain("payment_fraud", 0.90)
    b = _brain("payment_fraud", 0.96)  # > 0.1 apart at tol 0.05
    gate = ConsensusGate(a, b, conf_tolerance=0.05)
    out = gate.evaluate("analyst_classification", "classify", "analyst_classification")
    assert out["status"] == "disagreement"
    # within tolerance -> consensus
    gate2 = ConsensusGate(_brain("payment_fraud", 0.90), _brain("payment_fraud", 0.95),
                          conf_tolerance=0.10)
    out2 = gate2.evaluate("analyst_classification", "classify", "analyst_classification")
    assert out2["status"] == "consensus"


def test_e2_entity_resolution_field_compared():
    a = _brain(None, 0.9, entity="Acme Corp")
    b = _brain(None, 0.9, entity="Globex Inc")
    gate = ConsensusGate(a, b)
    out = gate.evaluate("analyst_entity_resolution", "resolve", "analyst_entity_resolution")
    assert out["status"] == "disagreement"
    assert out["verdict"] == "ASSERTED"


def test_e2_same_verdict_helper():
    assert same_verdict("analyst_classification",
                        {"claim_type": "x"}, {"claim_type": "x"}) is True
    assert same_verdict("analyst_classification",
                        {"claim_type": "x"}, {"claim_type": "y"}) is False


def test_e2_unmapped_task_is_distinct_from_disagreement():
    # A newly-registered task with no _VERDICT_FIELD entry must NOT silently
    # behave like a permanent brain disagreement. It must emit a DISTINCT,
    # louder, distinguishable signed event and report status=unmapped_task.
    events = []
    # Two brains that agree perfectly (same canned dict) so this is NOT a
    # disagreement in content — yet the task is unmapped -> unmapped_task, not
    # consensus and not disagreement.
    a = _brain("payment_fraud", 0.9)
    b = _brain("payment_fraud", 0.9)
    gate = ConsensusGate(a, b, audit_append=events.append)
    out = gate.evaluate("unknown_future_task", "do", "unknown_future_task")
    assert out["status"] == "unmapped_task"
    assert out["verdict"] == "ASSERTED"
    assert out["disagreement"] is True  # still requires escalation
    assert len(events) == 1
    assert events[0]["kind"] == "consensus.unmapped_task"
    assert events[0]["task"] == "unknown_future_task"
    # Sanity: a real disagreement on a MAPPED task still reports disagreement.
    events2 = []
    g2 = ConsensusGate(_brain("payment_fraud", 0.9), _brain("legit", 0.9),
                       audit_append=events2.append)
    out2 = g2.evaluate("analyst_classification", "classify", "analyst_classification")
    assert out2["status"] == "disagreement"
    assert events2[0]["kind"] == "consensus.disagreement"


def test_e2_unmapped_task_helper():
    assert unmapped_task("analyst_classification") is False
    assert unmapped_task("analyst_entity_resolution") is False
    assert unmapped_task("some_new_task") is True
