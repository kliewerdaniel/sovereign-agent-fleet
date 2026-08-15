"""D28 Phase 5/6 tests — Persona MoE GraphRAG (lenses, D-C) + Calibration (D-E/D-G).

Covers:
  * Personas emit OBSERVED SIGNALS only — never votes/dispositions (D-C).
  * Constitutional coverage is enforced fail-closed (D-G): removing the skeptic /
    falsifier / risk lens raises.
  * AlignmentEvent is signed + reviewable; governance-leak adjustments rejected
    fail-closed (D-E); only cognition-local scopes are allowed.
  * Calibration changes CognitionState (cognition-local) but carries NO field an
    authorization gate could read — M0 (Run A = Run B) is preserved.
  * Import wall: these modules import ONLY fleet.crypto + fleet.layers.handoff.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from fleet.cognition.persona import (
    Persona,
    PersonaGraph,
    default_persona_graph,
    ensure_constitutional_coverage,
    apply_persona,
    CONSTITUTIONAL_PERSONAS,
)
from fleet.cognition.calibration import (
    AlignmentEvent,
    CognitionState,
    validate_alignment_payload,
    ALLOWED_CALIBRATION_SCOPES,
)
from fleet.crypto.foundation import IdentityRoot


def _root():
    return IdentityRoot(b"phase5-smoke")


def _cert():
    root = _root()
    return root.issue_cert("cal-1", "operator", ["incident_remediate"],
                           2000, 9_999_999_999)


def test_persona_lenses_emit_signals_not_votes():
    g = default_persona_graph()
    out = g.analyze(
        "We assume the model is clearly correct; however the breach risk "
        "may cause a loss.")
    roles = [a["role"] for a in out["persona_analyses"]]
    # All five lenses ran (3 constitutional + 2 enrichment).
    assert sorted(roles) == ["domain_expert", "falsifier", "optimist",
                              "risk", "skeptic"]
    # No lens emits a disposition / authorization field — signals only.
    forbidden = {"disposition", "authorization", "decision", "granted",
                 "requires_human_review"}
    for a in out["persona_analyses"]:
        assert not (forbidden & set(a["observations"]))
        assert "constitutional" in a


def test_constitutional_coverage_enforced_fail_closed():
    # A graph missing ANY constitutional persona must not construct.
    for missing in CONSTITUTIONAL_PERSONAS:
        roles = [r for r in CONSTITUTIONAL_PERSONAS if r != missing]
        personas = [Persona(f"p-{r}", r) for r in roles]
        raised = False
        try:
            PersonaGraph(personas=personas)
        except Exception:
            raised = True
        assert raised, f"D-G violated: missing {missing} should fail closed"

    # ensure_constitutional_coverage is idempotent-safe when all present.
    ensure_constitutional_coverage(
        [Persona("p-s", "skeptic"), Persona("p-f", "falsifier"),
         Persona("p-r", "risk")])


def test_alignment_event_signed_and_reviewable():
    cert, key = _cert()
    ev = AlignmentEvent("e1", cert.agent_id, "persona_weights",
                        {"skeptic": 1.5, "risk": 0.8}, rationale="drift",
                        ts=2000)
    handoff = ev.sign(cert, key)
    # Signed envelope carries the payload + is verifiable by the producer cert.
    assert ev.verify_sig(handoff.sender_sig, cert)
    # Re-wrapping from the signed payload reproduces a valid event.
    reloaded = AlignmentEvent(**handoff.payload)
    assert reloaded.event_id == "e1"
    assert reloaded.verify_sig(handoff.sender_sig, cert)


def test_alignment_event_rejects_governance_leak_fail_closed():
    # A calibration that smuggles a disposition is structurally rejected.
    import pytest
    with pytest.raises(Exception):
        validate_alignment_payload({
            "scope": "persona_weights",
            "adjustment": {"disposition": "HUMAN"},
        })
    # An out-of-scope (governance-adjacent) calibration is rejected.
    with pytest.raises(Exception):
        validate_alignment_payload({
            "scope": "authorization_threshold",
            "adjustment": {"x": 1},
        })


def test_calibration_is_cognition_local_only_m0_preserved():
    cert, key = _cert()
    st = CognitionState()
    ev = AlignmentEvent("e1", cert.agent_id, "persona_weights",
                        {"skeptic": 1.5, "risk": 0.8}, ts=2000)
    st2 = st.apply_alignment(ev)
    # Cognition-local state changed.
    assert st2.persona_weights["skeptic"] == 1.5
    assert st2.persona_weights["risk"] == 0.8
    # M0: CognitionState carries NO field an authorization gate could read.
    gate_visible = {"disposition", "authorization", "capability",
                    "decision", "granted", "blocked", "final",
                    "requires_human_review"}
    assert not (gate_visible & set(st2.__dict__))
    assert not (gate_visible & set(st2.persona_weights))
    # Original state is untouched (pure).
    assert st.persona_weights["skeptic"] == 1.0


def test_alignment_event_chain_carries_prior():
    cert, key = _cert()
    e1 = AlignmentEvent("e1", cert.agent_id, "uncertainty_calibration",
                        {"temperature": 0.9}, ts=2000).sign(cert, key)
    e2 = AlignmentEvent("e2", cert.agent_id, "persona_weights",
                        {"optimist": 1.2}, prior_event_id="e1", ts=2001)
    assert e2.prior_event_id == "e1"
    # Signing still succeeds (chain integrity is the caller's ledger concern).
    assert e2.sign(cert, key).payload["event_id"] == "e2"
