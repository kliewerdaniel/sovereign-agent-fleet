"""Grid <-> fleet.epistemic adapter (Phase 7 — SIXTH external consumer proof).

This package is the bilingual node for the ``grid`` domain. It is structurally
identical to the other five adapters (``exchange``/``incident``/``supply``/
``hypothesis``/``mirror``).

It lives OUTSIDE both restricted trees (``fleet/epistemic/`` and ``grid/sim.py``):

    * ``fleet/epistemic`` may import ONLY ``fleet.crypto.foundation`` — it does
      NOT import this adapter, so it stays completely ignorant of energy balancing.
    * ``grid/sim`` imports NOTHING from the substrate — the adapter imports it,
      not the reverse.

So the import graph is strictly one-directional and leaves the substrate clean:

        grid.sim              fleet.epistemic
          |                     |
          |                     |
          +---- adapter --------+    (this package -- the only bilingual node)

The substrate's ``AuthorizationDecision`` is produced ONLY by ``decide()`` over a
signed ``AuthorityGrant``. This adapter performs the SIGNING (it holds the trusted
governance key) and the TRANSLATION (it knows what a ``GridSignal`` is). The
neutral substrate does neither.

Re-export the public surface so the consumer (a test, or later a real runtime)
can do everything through ``grid.epistemic_adapter`` without reaching into
``fleet.epistemic`` or ``grid.sim`` directly.
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
    decide_grid_action,
    CAP_GRID_BALANCE,
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
    "decide_grid_action",
    "CAP_GRID_BALANCE",
]
