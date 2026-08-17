"""Incident-response <-> fleet.epistemic adapter (M0 — SECOND external consumer).

This package is the decisive M0 experiment: **can a NON-financial domain consume
the SAME neutral contract the exchange adapter already consumes, WITHOUT the
substrate learning that incident-response exists?** The substrate is unchanged
from Phase 3 — we add a second bilingual node, not a substrate edit.

The import graph stays strictly one-directional and leaves the substrate clean:

        incident/sim          fleet.epistemic
              |                     |
              |                     |
              +---- adapter --------+    (this package -- the only bilingual node)

    * ``fleet/epistemic`` may import ONLY ``fleet.crypto.foundation`` — it does
      NOT import this adapter, so it stays completely ignorant of incident triage.
    * ``incident/sim`` imports ONLY its own domain — it does NOT import this
      adapter either (the adapter imports it, not the reverse).

This is the structural mirror of ``exchange/epistemic_adapter``. Two adapters,
one substrate, zero substrate edits: that is the domain-generality proof.

Re-export the public surface so a consumer can do everything through
``incident.epistemic_adapter`` without reaching into ``fleet.epistemic`` or
``incident/sim`` directly.
"""
from __future__ import annotations

from .authority import GovernanceAuthority, issue_grant
from .translate import (
    build_capability_scope,
    build_authorization_scope,
    build_governance_constraints,
    signal_to_proposition,
    signal_to_evidence,
    plan_to_recommendation,
    plan_to_assessment,
    plan_to_request,
    decide_incident_action,
    CAP_INCIDENT_REMEDIATE,
    CAP_INCIDENT_ESCALATE,
)

__all__ = [
    "GovernanceAuthority",
    "issue_grant",
    "build_capability_scope",
    "build_authorization_scope",
    "build_governance_constraints",
    "signal_to_proposition",
    "signal_to_evidence",
    "plan_to_recommendation",
    "plan_to_assessment",
    "plan_to_request",
    "decide_incident_action",
    "CAP_INCIDENT_REMEDIATE",
    "CAP_INCIDENT_ESCALATE",
]
