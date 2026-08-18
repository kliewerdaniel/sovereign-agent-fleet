"""Mirror <-> fleet.epistemic adapter (Phase 6 — FIFTH external consumer proof).

This package is the bilingual node for the ``mirror`` domain. It is structurally
identical to the other four adapters (``exchange``/``incident``/``supply``/
``hypothesis``) — and adds the L0 ladder promotion path
(``plan_to_proposal``) that the others did not need to surface.

It lives OUTSIDE both restricted trees (``fleet/epistemic/`` and
``mirror/sim.py``):

    * ``fleet/epistemic`` may import ONLY ``fleet.crypto.foundation`` — it does
      NOT import this adapter, so it stays completely ignorant of agent
      self-observability.
    * ``mirror/sim`` imports NOTHING from the substrate — the adapter imports
      it, not the reverse.

So the import graph is strictly one-directional and leaves the substrate clean:

        mirror.sim             fleet.epistemic
              |                     |
              |                     |
              +---- adapter --------+    (this package -- the only bilingual node)

The substrate's ``AuthorizationDecision`` is produced ONLY by ``decide()`` over a
signed ``AuthorityGrant``. This adapter performs the SIGNING (it holds the
trusted governance key) and the TRANSLATION (it knows what a ``MirrorSignal``
is). The neutral substrate does neither.

Re-export the public surface so the consumer (a test, or later a real runtime)
can do everything through ``mirror.epistemic_adapter`` without reaching into
``fleet.epistemic`` or ``mirror.sim`` directly.
"""
from __future__ import annotations

from .authority import GovernanceAuthority, issue_grant
from .translate import (
    build_capability_scope,
    build_authorization_scope,
    build_governance_constraints,
    build_proposal_scope,
    signal_to_proposition,
    signal_to_evidence,
    plan_to_recommendation,
    plan_to_assessment,
    plan_to_proposal,
    plan_to_request,
    decide_mirror_action,
    CAP_MIRROR_SELF_TUNE,
    MIRROR_PROPOSAL_SCOPE,
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
    "plan_to_proposal",
    "plan_to_request",
    "decide_mirror_action",
    "CAP_MIRROR_SELF_TUNE",
    "MIRROR_PROPOSAL_SCOPE",
]
