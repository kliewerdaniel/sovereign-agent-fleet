"""Phase 7 (M0) — grid-side translation: energy concepts -> neutral epistemic contract.

This is the grid analog of ``hypothesis/epistemic_adapter/translate.py`` for a
SIXTH, unrelated domain (energy / demand-response balancing). Every function is a
pure mapping from a grid object (which the neutral substrate has never heard of)
into one of the generic epistemic types in ``fleet.epistemic``. The grid
*semantics* (load_mw, capacity_mw, imbalance_pct, price) never cross into
``fleet.epistemic`` — they are rendered into domain-neutral fields (proposition
domain/subject/predicate, evidence payload, assessment condition/observed/result,
recommendation text). The substrate can hold and hash these objects without ever
knowing they originated in a power-grid controller.

The single boundary the user insisted on: NONE of these translations produce
authority. They produce requests (``AuthorizationRequest``) that must later be
passed to ``decide()`` together with a signed ``AuthorityGrant`` issued by
governance. The adapter's ``decide_grid_action`` wires that end-to-end.
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

# Capability strings the grid domain uses. Plain strings to the substrate;
# only the grant's AuthorizationScope + GovernanceConstraints know what they
# mean. Scoped actions, NOT universal authorizations.
CAP_GRID_BALANCE = "grid.balance"


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
    """Neutral deterministic policy. The grid-specific policy is expressed as
    plain allow/deny lists + a human-approval flag — no grid object leaks in."""
    return GovernanceConstraints(
        allowlist=tuple(allowlist),
        denylist=tuple(denylist),
        require_human_approval=require_human_approval,
        policy_refs=tuple(policy_refs),
    )


# ---------------------------------------------------------------------------
# Grid cognition -> neutral epistemic artifacts (advisory, no authority)
# ---------------------------------------------------------------------------
def signal_to_proposition(
    sig, domain: str = "grid_balance", producer: str = "observer"
) -> Proposition:
    """GridSignal -> neutral Proposition (the 'about what' statement)."""
    return Proposition(
        domain=domain,
        subject=f"node-{sig.node_id}",
        predicate="needs_balancing",
        params={"method": sig.method},
    )


def signal_to_evidence(
    sig, proposition: Proposition, producer: str = "observer"
) -> Evidence:
    """GridSignal -> neutral Evidence (lineage node carrying the payload).

    The load_mw/capacity_mw/imbalance_pct/price values live only inside
    ``payload`` as opaque data. The substrate neither reads nor acts on them.
    """
    return Evidence(
        producer=producer,
        evidence_kind="observation",
        payload={
            "needs_balancing": sig.needs_balancing,
            "load_mw": sig.load_mw,
            "capacity_mw": sig.capacity_mw,
            "imbalance_pct": sig.imbalance_pct,
            "price": sig.price,
            "method": sig.method,
        },
        inputs=[proposition.proposition_hash],
    )


def plan_to_recommendation(
    plan, proposition: Proposition, producer: str = "observer"
) -> Recommendation:
    """GridPlan -> neutral Recommendation (advisory ONLY).

    ``authority`` is forced to "NONE" by the substrate's own __post_init__ guard,
    so this can never become a permission. The action is plain rationale text."""
    return Recommendation(
        producer=producer,
        target=proposition.subject,
        action_suggestion=f"run {plan.action} on {plan.node_id} (priority {plan.balancing_priority})",
        rationale=f"verification={plan.verification}; priority={plan.balancing_priority}",
        evidence_refs=[],
    )


def plan_to_assessment(
    plan, subject: str = "grid", producer: str = "observer"
) -> Assessment:
    """GridPlan -> neutral Assessment (deterministic state-vs-policy view).

    ``result`` is a classification ("RUN"/"HOLD"), NOT a permission."""
    return Assessment(
        producer=producer,
        subject=subject,
        condition={"max_balancing_priority": 3},
        observed={"balancing_priority": plan.balancing_priority},
        result=plan.recommendation,  # "RUN" / "HOLD"
        reason="grid balancing classification",
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
    producer: str = "observer",
) -> AuthorizationRequest:
    """Build an AuthorizationRequest from a balancing plan. No authority granted."""
    return AuthorizationRequest(
        producer=producer,
        request_id=request_id,
        capability=capability,
        action_descriptor=action_descriptor,
        conditions=conditions or {},
        proposal_ref=plan_ref,
    )


# ---------------------------------------------------------------------------
# End-to-end: run the neutral decision over a grid-described action
# ---------------------------------------------------------------------------
def decide_grid_action(
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
    """The single seam where grid intent meets the neutral decision function.

    This is the ONLY place ``decide()`` is invoked for this domain. All grid
    translation happened in the functions above; here we hand the neutral
    substrate a fully generic request + signed grant + policy, and it returns a
    generic AuthorizationDecision. The substrate never sees the words "grid",
    "megawatt", or "imbalance".
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
