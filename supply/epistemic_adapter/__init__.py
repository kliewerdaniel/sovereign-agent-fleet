"""Supply-chain <-> fleet.epistemic adapter (M0 — THIRD external consumer).

The third bilingual node. Structurally identical to ``exchange/epistemic_adapter``
and ``incident/epistemic_adapter``. The import graph stays one-directional and
leaves the substrate clean:

        supply/sim            fleet.epistemic
              |                     |
              +---- adapter --------+    (this package -- the only bilingual node)

Two adapters of one kind would already prove generality; a THIRD, in a completely
different domain shape (operations/logistics vs finance vs security), removes any
doubt that the substrate is keyed to "the kind of domain." It serves all three
through the identical ``decide()`` with zero substrate edits.

Re-exports the public surface so consumers use only this package + the neutral
types, never reaching into ``fleet.epistemic`` or ``supply/sim`` directly.
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
    decide_supply_action,
    CAP_SUPPLY_REORDER,
    CAP_SUPPLY_EXPEDITE,
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
    "decide_supply_action",
    "CAP_SUPPLY_REORDER",
    "CAP_SUPPLY_EXPEDITE",
]
