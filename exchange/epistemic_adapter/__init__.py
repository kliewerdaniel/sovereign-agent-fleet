"""Exchange <-> fleet.epistemic adapter (Phase 3 — EXTERNAL consumer proof).

This package is the decisive Phase 3 experiment: **can the financial firm consume
the epistemic contract WITHOUT the neutral substrate learning that finance
exists?**

The answer the architecture must demonstrate is YES, and this adapter is the
only place where the translation happens. It lives OUTSIDE both restricted trees
(``fleet/epistemic/`` and ``exchange/quant/``):

    * ``fleet/epistemic`` may import ONLY ``fleet.crypto.foundation`` — it does
      NOT import this adapter, so it stays completely ignorant of trading.
    * ``exchange/quant`` may import ONLY its own allow-list — it does NOT import
      this adapter either (the adapter imports it, not the reverse).

So the import graph is strictly one-directional and leaves the substrate clean:

        exchange.quant          fleet.epistemic
                  |                 |
                  |                 |
                  +---- adapter ----+    (this package -- the only bilingual node)

The substrate's ``AuthorizationDecision`` is produced ONLY by ``decide()`` over a
signed ``AuthorityGrant``. This adapter performs the SIGNING (it holds the trusted
governance key) and the TRANSLATION (it knows what a ``ProbabilityEstimate`` is).
The neutral substrate does neither.

Re-export the public surface so the consumer (a test, or later a real runtime)
can do everything through ``exchange.epistemic_adapter`` without reaching into
``fleet.epistemic`` or ``exchange.quant`` directly.
"""
from __future__ import annotations

from .authority import GovernanceAuthority, issue_grant
from .translate import (
    build_capability_scope,
    build_authorization_scope,
    build_governance_constraints,
    proposal_to_request,
    kelly_to_recommendation,
    probability_to_proposition,
    probability_to_evidence,
    kelly_to_assessment,
    trade_decision_to_request,
    decide_quant_order,
    CAP_TRADE_EXECUTE,
    CAP_RISK_HALT,
)

__all__ = [
    "GovernanceAuthority",
    "issue_grant",
    "build_capability_scope",
    "build_authorization_scope",
    "build_governance_constraints",
    "proposal_to_request",
    "kelly_to_recommendation",
    "probability_to_proposition",
    "probability_to_evidence",
    "kelly_to_assessment",
    "trade_decision_to_request",
    "decide_quant_order",
    "CAP_TRADE_EXECUTE",
    "CAP_RISK_HALT",
]