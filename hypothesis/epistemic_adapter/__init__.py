"""Hypothesis <-> fleet.epistemic adapter (M0 — FOURTH external consumer).

The fourth bilingual node. Structurally identical to ``exchange/``,
``incident/``, and ``supply/`` adapters. The import graph stays one-directional
and leaves the substrate clean:

        hypothesis/sim       fleet.epistemic
              |                     |
              +---- adapter --------+    (this package -- the only bilingual node)

Four adapters of one kind remove any doubt that the substrate is keyed to "the
kind of domain." It serves all four through the identical ``decide()`` with zero
substrate edits.

Re-exports the public surface so consumers use only this package + the neutral
types, never reaching into ``fleet.epistemic`` or ``hypothesis/sim`` directly.
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
    decide_hypothesis_action,
    CAP_HYPOTHESIS_RUN,
    CAP_HYPOTHESIS_PUBLISH,
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
    "decide_hypothesis_action",
    "CAP_HYPOTHESIS_RUN",
    "CAP_HYPOTHESIS_PUBLISH",
]
