"""Phase 4 (M0) — agent-side translation: supply concepts -> neutral epistemic contract.

Mirror of ``incident/epistemic_adapter/translate.py`` for a THIRD, unrelated
domain (operations/logistics). Every function is a pure mapping from a supply
object (the substrate has never heard of) into one of the generic epistemic types
in ``fleet.epistemic``. The supply *semantics* (stockout_prob, lead_time,
reorder_priority, verification) never cross into ``fleet.epistemic`` — they are
rendered into domain-neutral fields (proposition domain/subject/predicate,
evidence payload, assessment condition/observed/result, recommendation text).
The substrate holds and hashes these objects without ever knowing they came from
a supply-chain system.

The single boundary: NONE of these translations produce authority. They produce
requests (``AuthorizationRequest``) passed to ``decide()`` with a signed
``AuthorityGrant`` from governance. ``decide_supply_action`` wires that end-to-end.
"""
from __future__ import annotations

from typing import Tuple

from fleet.epistemic.assessment import Assessment
from fleet.epistemic.authorization import AuthorizationRequest
from fleet.epistemic.decision import AuthorizationDecision, decide
from fleet.epistemic.evidence import Evidence
from fleet.epistemic.governance_constraints import GovernanceConstraints
from fleet.epistemic.identity import AgentIdentity
from fleet.epistemic.proposition import Proposition
from fleet.epistemic.recommendation import Recommendation
from fleet.epistemic.scope import AuthorizationScope, CapabilityScope

# Capability strings the supply domain uses. Plain strings to the substrate;
# only the grant's AuthorizationScope + GovernanceConstraints know what they
# mean. Scoped actions, NOT universal authorizations.
CAP_SUPPLY_REORDER = "supply.reorder"
CAP_SUPPLY_EXPEDITE = "supply.expedite"


# ---------------------------------------------------------------------------
# Identity / scopes (the contract the agent is bound under)
# ---------------------------------------------------------------------------
def build_capability_scope(capabilities: Tuple[str, ...]) -> CapabilityScope:
    """Map the agent's operational capabilities into a neutral CapabilityScope."""
    return CapabilityScope(capabilities=tuple(capabilities))


def build_authorization_scope(
    actions: Tuple[str, ...], governance_role: str = ""
) -> AuthorizationScope:
    """The discrete actions governance MAY grant (NOT a grant itself)."""
    return AuthorizationScope(actions=tuple(actions), governance_role=governance_role)


def build_governance_constraints(
    allowlist: Tuple[str, ...] = (),
    denylist: Tuple[str, ...] = (),
    require_human_approval: bool = False,
    policy_refs: Tuple[str, ...] = (),
) -> GovernanceConstraints:
    """Neutral deterministic policy. The supply-specific policy is expressed as
    plain allow/deny lists + a human-approval flag — no supply object leaks in."""
    return GovernanceConstraints(
        allowlist=tuple(allowlist),
        denylist=tuple(denylist),
        require_human_approval=require_human_approval,
        policy_refs=tuple(policy_refs),
    )


# ---------------------------------------------------------------------------
# Supply cognition -> neutral epistemic artifacts (advisory, no authority)
# ---------------------------------------------------------------------------
def signal_to_proposition(
    sig, domain: str = "supply_stockout", producer: str = "scops"
) -> Proposition:
    """InventorySignal -> neutral Proposition (the 'about what' statement)."""
    return Proposition(
        domain=domain,
        subject=f"sku-{sig.sku}",
        predicate="is_stockout_risk",
        params={"method": sig.method},
    )


def signal_to_evidence(
    sig, proposition: Proposition, producer: str = "scops"
) -> Evidence:
    """InventorySignal -> neutral Evidence (lineage node carrying the payload).

    The stockout_prob/lead_time values live only inside ``payload`` as opaque
    data. The substrate neither reads nor acts on them.
    """
    return Evidence(
        producer=producer,
        evidence_kind="observation",
        payload={
            "is_stockout_risk": sig.is_stockout_risk,
            "stockout_prob": sig.stockout_prob,
            "lead_time_days": sig.lead_time_days,
            "method": sig.method,
        },
        inputs=[proposition.proposition_hash],
    )


def plan_to_recommendation(
    plan, proposition: Proposition, producer: str = "scops"
) -> Recommendation:
    """ReorderPlan -> neutral Recommendation (advisory ONLY).

    ``authority`` is forced to "NONE" by the substrate's own __post_init__ guard,
    so this can never become a permission. The action is plain rationale text."""
    return Recommendation(
        producer=producer,
        target=proposition.subject,
        action_suggestion=f"run {plan.action} on {plan.sku} (priority {plan.reorder_priority})",
        rationale=f"verification={plan.verification}; priority={plan.reorder_priority}",
        evidence_refs=[],
    )


def plan_to_assessment(
    plan, subject: str = "sku", producer: str = "scops"
) -> Assessment:
    """ReorderPlan -> neutral Assessment (deterministic state-vs-policy view).

    ``result`` is a classification ("REORDER"/"HOLD"), NOT a permission."""
    return Assessment(
        producer=producer,
        subject=subject,
        condition={"max_reorder_priority": 3},
        observed={"reorder_priority": plan.reorder_priority},
        result=plan.recommendation,  # "REORDER" / "HOLD"
        reason="supply reorder classification",
    )


# ---------------------------------------------------------------------------
# Requests (the boundary just before governance)
# ---------------------------------------------------------------------------
def plan_to_request(
    *,
    request_id: str,
    capability: str,
    action_descriptor: str,
    plan_ref: str,
    conditions: dict | None = None,
    producer: str = "scops",
) -> AuthorizationRequest:
    """Build an AuthorizationRequest from a reorder plan's hash. No authority granted."""
    return AuthorizationRequest(
        producer=producer,
        request_id=request_id,
        capability=capability,
        action_descriptor=action_descriptor,
        conditions=conditions or {},
        proposal_ref=plan_ref,
    )


# ---------------------------------------------------------------------------
# End-to-end: run the neutral decision over a supply-described action
# ---------------------------------------------------------------------------
def decide_supply_action(
    *,
    identity: AgentIdentity,
    grant,
    authorization_scope: AuthorizationScope,
    request: AuthorizationRequest,
    constraints: GovernanceConstraints,
    current_epoch: int,
    now: int,
    trusted_issuer_pubkey_pem: str,
) -> AuthorizationDecision:
    """The single seam where supply intent meets the neutral decision function.

    This is the ONLY place ``decide()`` is invoked for this domain. All supply
    translation happened above; here we hand the neutral substrate a fully
    generic request + signed grant + policy, and it returns a generic
    AuthorizationDecision. The substrate never sees the words "reorder",
    "stockout", or "lead_time".
    """
    return decide(
        identity=identity,
        grant=grant,
        authorization_scope=authorization_scope,
        request=request,
        constraints=constraints,
        current_epoch=current_epoch,
        now=now,
        trusted_issuer_pubkey_pem=trusted_issuer_pubkey_pem,
    )
