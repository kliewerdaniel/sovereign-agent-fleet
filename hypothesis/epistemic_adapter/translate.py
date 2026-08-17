"""Phase 5 (M0) — agent-side translation: hypothesis concepts -> neutral epistemic contract.

Mirror of ``incident/epistemic_adapter/translate.py`` / ``supply/epistemic_adapter/
translate.py`` for a FOURTH, unrelated domain (scientific research / reasoning).
Every function is a pure mapping from a hypothesis object (the substrate has
never heard of) into one of the generic epistemic types in ``fleet.epistemic``.
The hypothesis *semantics* (p_value, effect_size, confidence) never cross into
``fleet.epistemic`` — they are rendered into domain-neutral fields (proposition
domain/subject/predicate, evidence payload, assessment condition/observed/result,
recommendation text). The substrate holds and hashes these objects without ever
knowing they came from a research system.

Notably, this domain exercises the linchpin ``Proposition`` type most directly:
the substrate's own ``Proposition`` docstring names this exact domain
(``domain="hypothesis_true"``, ``subject="H3"``, ``predicate="will_occur"``) as a
canonical example. The adapter fills in precisely those fields, proving the
neutral contract was designed to be domain-shaped, not finance-shaped.

The single boundary: NONE of these translations produce authority. They produce
requests (``AuthorizationRequest``) passed to ``decide()`` with a signed
``AuthorityGrant`` from governance. ``decide_hypothesis_action`` wires that
end-to-end.
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

# Capability strings the hypothesis domain uses. Plain strings to the substrate;
# only the grant's AuthorizationScope + GovernanceConstraints know what they
# mean. Scoped actions, NOT universal authorizations.
CAP_HYPOTHESIS_RUN = "hypothesis.run_experiment"
CAP_HYPOTHESIS_PUBLISH = "hypothesis.publish"


# ---------------------------------------------------------------------------
# Identity / scopes (the contract the agent is bound under)
# ---------------------------------------------------------------------------
def build_capability_scope(capabilities: Tuple[str, ...]) -> CapabilityScope:
    """Map the agent's research capabilities into a neutral CapabilityScope."""
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
    """Neutral deterministic policy. The hypothesis-specific policy is expressed
    as plain allow/deny lists + a human-approval flag — no hypothesis object
    leaks in."""
    return GovernanceConstraints(
        allowlist=tuple(allowlist),
        denylist=tuple(denylist),
        require_human_approval=require_human_approval,
        policy_refs=tuple(policy_refs),
    )


# ---------------------------------------------------------------------------
# Hypothesis cognition -> neutral epistemic artifacts (advisory, no authority)
# ---------------------------------------------------------------------------
def signal_to_proposition(
    sig, domain: str = "hypothesis_true", producer: str = "researchops"
) -> Proposition:
    """HypothesisSignal -> neutral Proposition (the 'about what' statement).

    This is the linchpin match: the substrate's own ``Proposition`` docstring
    names this exact domain/subject/predicate triple as the canonical
    non-finance example. The adapter fills those identical neutral fields.
    """
    return Proposition(
        domain=domain,
        subject=f"hyp-{sig.hypothesis_id}",
        predicate="will_occur",
        params={"method": sig.method},
    )


def signal_to_evidence(
    sig, proposition: Proposition, producer: str = "researchops"
) -> Evidence:
    """HypothesisSignal -> neutral Evidence (lineage node carrying the payload).

    The p_value/effect_size values live only inside ``payload`` as opaque data.
    The substrate neither reads nor acts on them.
    """
    return Evidence(
        producer=producer,
        evidence_kind="observation",
        payload={
            "is_supported": sig.is_supported,
            "p_value": sig.p_value,
            "effect_size": sig.effect_size,
            "method": sig.method,
        },
        inputs=[proposition.proposition_hash],
    )


def plan_to_recommendation(
    plan, proposition: Proposition, producer: str = "researchops"
) -> Recommendation:
    """ExperimentPlan -> neutral Recommendation (advisory ONLY).

    ``authority`` is forced to "NONE" by the substrate's own __post_init__ guard,
    so this can never become a permission. The action is plain rationale text."""
    return Recommendation(
        producer=producer,
        target=proposition.subject,
        action_suggestion=f"run {plan.action} on {plan.hypothesis_id} (priority {plan.experiment_priority})",
        rationale=f"verification={plan.verification}; priority={plan.experiment_priority}",
        evidence_refs=[],
    )


def plan_to_assessment(
    plan, subject: str = "hypothesis", producer: str = "researchops"
) -> Assessment:
    """ExperimentPlan -> neutral Assessment (deterministic state-vs-policy view).

    ``result`` is a classification ("RUN"/"HOLD"), NOT a permission."""
    return Assessment(
        producer=producer,
        subject=subject,
        condition={"max_experiment_priority": 3},
        observed={"experiment_priority": plan.experiment_priority},
        result=plan.recommendation,  # "RUN" / "HOLD"
        reason="hypothesis experiment classification",
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
    producer: str = "researchops",
) -> AuthorizationRequest:
    """Build an AuthorizationRequest from an experiment plan's hash. No authority granted."""
    return AuthorizationRequest(
        producer=producer,
        request_id=request_id,
        capability=capability,
        action_descriptor=action_descriptor,
        conditions=conditions or {},
        proposal_ref=plan_ref,
    )


# ---------------------------------------------------------------------------
# End-to-end: run the neutral decision over a hypothesis-described action
# ---------------------------------------------------------------------------
def decide_hypothesis_action(
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
    """The single seam where hypothesis intent meets the neutral decision function.

    This is the ONLY place ``decide()`` is invoked for this domain. All hypothesis
    translation happened above; here we hand the neutral substrate a fully
    generic request + signed grant + policy, and it returns a generic
    AuthorizationDecision. The substrate never sees the words "hypothesis",
    "p_value", or "effect_size".
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
