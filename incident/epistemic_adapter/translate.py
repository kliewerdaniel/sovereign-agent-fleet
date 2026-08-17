"""Phase 4 (M0) — agent-side translation: incident concepts -> neutral epistemic contract.

This is the mirror of ``exchange/epistemic_adapter/translate.py`` for a DIFFERENT
domain. Every function is a pure mapping from an incident object (which the
neutral substrate has never heard of) into one of the generic epistemic types in
``fleet.epistemic``. The incident *semantics* (severity, compromised,
triage_priority, verification) never cross into ``fleet.epistemic`` — they are
rendered into domain-neutral fields (proposition domain/subject/predicate,
evidence payload, assessment condition/observed/result, recommendation text).
The substrate can hold and hash these objects without ever knowing they
originated in an incident-response system.

The single boundary the user insisted on: NONE of these translations produce
authority. They produce requests (``AuthorizationRequest``) that must later be
passed to ``decide()`` together with a signed ``AuthorityGrant`` issued by
governance. The adapter's ``decide_incident_action`` wires that end-to-end.
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

# Capability strings the incident domain uses. Plain strings to the substrate;
# only the grant's AuthorizationScope + GovernanceConstraints know what they
# mean. They are scoped actions, NOT universal authorizations.
CAP_INCIDENT_REMEDIATE = "incident.remediate"
CAP_INCIDENT_ESCALATE = "incident.escalate"


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
    """Neutral deterministic policy. The incident-specific policy is expressed as
    plain allow/deny lists + a human-approval flag — no incident object leaks in."""
    return GovernanceConstraints(
        allowlist=tuple(allowlist),
        denylist=tuple(denylist),
        require_human_approval=require_human_approval,
        policy_refs=tuple(policy_refs),
    )


# ---------------------------------------------------------------------------
# Incident cognition -> neutral epistemic artifacts (advisory, no authority)
# ---------------------------------------------------------------------------
def signal_to_proposition(
    sig, domain: str = "incident_compromised", producer: str = "secops"
) -> Proposition:
    """IncidentSignal -> neutral Proposition (the 'about what' statement)."""
    return Proposition(
        domain=domain,
        subject=f"asset-{sig.asset}",
        predicate="is_compromised",
        params={"method": sig.method},
    )


def signal_to_evidence(
    sig, proposition: Proposition, producer: str = "secops"
) -> Evidence:
    """IncidentSignal -> neutral Evidence (lineage node carrying the payload).

    The severity/confidence values live only inside ``payload`` as opaque data.
    The substrate neither reads nor acts on them.
    """
    return Evidence(
        producer=producer,
        evidence_kind="observation",
        payload={
            "is_compromised": sig.is_compromised,
            "severity": sig.severity,
            "confidence": sig.confidence,
            "method": sig.method,
        },
        inputs=[proposition.proposition_hash],
    )


def plan_to_recommendation(
    plan, proposition: Proposition, producer: str = "secops"
) -> Recommendation:
    """RemediationPlan -> neutral Recommendation (advisory ONLY).

    ``authority`` is forced to "NONE" by the substrate's own __post_init__ guard,
    so this can never become a permission. The action is plain rationale text."""
    return Recommendation(
        producer=producer,
        target=proposition.subject,
        action_suggestion=f"run {plan.action} on {plan.asset} (triage {plan.triage_priority})",
        rationale=f"verification={plan.verification}; priority={plan.triage_priority}",
        evidence_refs=[],
    )


def plan_to_assessment(
    plan, subject: str = "asset", producer: str = "secops"
) -> Assessment:
    """RemediationPlan -> neutral Assessment (deterministic state-vs-policy view).

    ``result`` is a classification ("REMEDIATE"/"HOLD"), NOT a permission."""
    return Assessment(
        producer=producer,
        subject=subject,
        condition={"max_triage_priority": 3},
        observed={"triage_priority": plan.triage_priority},
        result=plan.recommendation,  # "REMEDIATE" / "HOLD"
        reason="incident triage classification",
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
    producer: str = "secops",
) -> AuthorizationRequest:
    """Build an AuthorizationRequest from a remediation plan's hash. No authority granted."""
    return AuthorizationRequest(
        producer=producer,
        request_id=request_id,
        capability=capability,
        action_descriptor=action_descriptor,
        conditions=conditions or {},
        proposal_ref=plan_ref,
    )


# ---------------------------------------------------------------------------
# End-to-end: run the neutral decision over an incident-described action
# ---------------------------------------------------------------------------
def decide_incident_action(
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
    """The single seam where incident intent meets the neutral decision function.

    This is the ONLY place ``decide()`` is invoked for this domain. All incident
    translation happened in the functions above; here we hand the neutral
    substrate a fully generic request + signed grant + policy, and it returns a
    generic AuthorizationDecision. The substrate never sees the words "incident",
    "severity", or "compromised".
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
