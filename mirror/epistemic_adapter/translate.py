"""Phase 6 (M0) — agent-side translation: mirror concepts -> neutral epistemic contract.

This is the mirror of ``hypothesis/epistemic_adapter/translate.py`` for a FIFTH,
unrelated domain (agent self-observability/introspection). Every function is a
pure mapping from a mirror object (which the neutral substrate has never heard
of) into one of the generic epistemic types in ``fleet.epistemic``. The mirror
*semantics* (cpu_load, error_rate, queue_depth, tune_priority, verification)
never cross into ``fleet.epistemic`` — they are rendered into domain-neutral
fields (proposition domain/subject/predicate, evidence payload, assessment
condition/observed/result, recommendation text). The substrate can hold and hash
these objects without ever knowing they originated in a self-reflection system.

The single boundary the user insisted on: NONE of these translations produce
authority. They produce requests (``AuthorizationRequest``) that must later be
passed to ``decide()`` together with a signed ``AuthorityGrant`` issued by
governance. The adapter's ``decide_mirror_action`` wires that end-to-end.

The L0 ladder (novel here): a mirror plan flows through

    signal_to_proposition -> signal_to_evidence -> plan_to_assessment
    -> plan_to_recommendation        (advisory, authority="NONE")
    -> plan_to_proposal              (intent, bounded by ProposalScope)
    -> plan_to_request               (the boundary just before governance)

``plan_to_proposal`` enforces the promotion gate FAIL-CLOSED: a ``Proposal`` may
only describe action descriptors listed in ``MIRROR_PROPOSAL_SCOPE``. The frozen
substrate is domain-neutral and does not read ``ProposalScope``; the adapter is
the only place that does, and it refuses to promote out-of-scope intent. This is
the structural guarantee that a self-reflection can never silently become
authority — authorization still requires an externally-signed ``AuthorityGrant``
verified by ``decide()``.
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
from fleet.epistemic.proposal import Proposal
from fleet.epistemic.recommendation import Recommendation
from fleet.epistemic.scope import AuthorizationScope, CapabilityScope, ProposalScope

# Capability strings the mirror domain uses. Plain strings to the substrate;
# only the grant's AuthorizationScope + GovernanceConstraints know what they
# mean. Scoped actions, NOT universal authorizations.
CAP_MIRROR_SELF_TUNE = "mirror.self_tune"

# The action descriptors a mirror Proposal is permitted to express. This is the
# adapter-level promotion gate: a self-tuning intent outside this set is refused
# (fail-closed). It mirrors the substrate's ProposalScope but is enforced at the
# bilingual boundary because the frozen substrate is intentionally domain-neutral.
MIRROR_PROPOSAL_SCOPE: Tuple[str, ...] = ("self_tune", "throttle", "restart_module")


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
    """Neutral deterministic policy. The mirror-specific policy is expressed as
    plain allow/deny lists + a human-approval flag — no mirror object leaks in."""
    return GovernanceConstraints(
        allowlist=tuple(allowlist),
        denylist=tuple(denylist),
        require_human_approval=require_human_approval,
        policy_refs=tuple(policy_refs),
    )


def build_proposal_scope() -> ProposalScope:
    """The action descriptors a mirror agent MAY propose (never authorize).

    This is the L0 ladder's 'what may be proposed' boundary, enforced by
    ``plan_to_proposal``. It is deliberately narrow — self-observability cannot
    propose arbitrary world actions.
    """
    return ProposalScope(action_descriptors=MIRROR_PROPOSAL_SCOPE)


# ---------------------------------------------------------------------------
# Mirror cognition -> neutral epistemic artifacts (advisory, no authority)
# ---------------------------------------------------------------------------
def signal_to_proposition(
    sig, domain: str = "agent_health", producer: str = "observer"
) -> Proposition:
    """MirrorSignal -> neutral Proposition (the 'about what' statement)."""
    return Proposition(
        domain=domain,
        subject=f"agent-{sig.agent_id}",
        predicate="needs_tuning",
        params={"method": sig.method},
    )


def signal_to_evidence(
    sig, proposition: Proposition, producer: str = "observer"
) -> Evidence:
    """MirrorSignal -> neutral Evidence (lineage node carrying the payload).

    The cpu_load/error_rate/queue_depth values live only inside ``payload`` as
    opaque data. The substrate neither reads nor acts on them.
    """
    return Evidence(
        producer=producer,
        evidence_kind="observation",
        payload={
            "needs_tuning": sig.needs_tuning,
            "cpu_load": sig.cpu_load,
            "error_rate": sig.error_rate,
            "queue_depth": sig.queue_depth,
            "method": sig.method,
        },
        inputs=[proposition.proposition_hash],
    )


def plan_to_recommendation(
    plan, proposition: Proposition, producer: str = "observer"
) -> Recommendation:
    """SelfTunePlan -> neutral Recommendation (advisory ONLY).

    ``authority`` is forced to "NONE" by the substrate's own __post_init__ guard,
    so this can never become a permission. The action is plain rationale text."""
    return Recommendation(
        producer=producer,
        target=proposition.subject,
        action_suggestion=f"run {plan.action} on {plan.agent_id} (priority {plan.tune_priority})",
        rationale=f"verification={plan.verification}; priority={plan.tune_priority}",
        evidence_refs=[],
    )


def plan_to_assessment(
    plan, subject: str = "agent", producer: str = "observer"
) -> Assessment:
    """SelfTunePlan -> neutral Assessment (deterministic state-vs-policy view).

    ``result`` is a classification ("RUN"/"HOLD"), NOT a permission."""
    return Assessment(
        producer=producer,
        subject=subject,
        condition={"max_tune_priority": 3},
        observed={"tune_priority": plan.tune_priority},
        result=plan.recommendation,  # "RUN" / "HOLD"
        reason="mirror self-tune classification",
    )


def plan_to_proposal(plan, *, proposal_scope: ProposalScope, producer: str = "observer") -> Proposal:
    """SelfTunePlan -> neutral Proposal (intent), gated by ProposalScope.

    This is the L0 ladder promotion step. The badge enforces FAIL-CLOSED that the
    frozen, domain-neutral substrate does not: a self-tuning intent may only
    describe an action_descriptor present in ``proposal_scope.action_descriptors``.
    Anything else is refused — a self-reflection cannot promote into an intent to
    perform an out-of-scope action.

    NOTE: a Proposal is still NOT authority. It must later become an
    AuthorizationRequest and clear ``decide()`` with an externally-signed grant.
    """
    if plan.action not in proposal_scope.action_descriptors:
        raise AssertionError(
            f"refusing to promote out-of-scope action {plan.action!r}: "
            f"not in ProposalScope {proposal_scope.action_descriptors}"
        )
    return Proposal(
        producer=producer,
        action_descriptor=plan.action,
        rationale=f"self-tuning for {plan.agent_id}; priority {plan.tune_priority}",
        target_ref=plan.plan_id,
        evidence_refs=[],
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
    """Build an AuthorizationRequest from a self-tune plan. No authority granted."""
    return AuthorizationRequest(
        producer=producer,
        request_id=request_id,
        capability=capability,
        action_descriptor=action_descriptor,
        conditions=conditions or {},
        proposal_ref=plan_ref,
    )


# ---------------------------------------------------------------------------
# End-to-end: run the neutral decision over a mirror-described action
# ---------------------------------------------------------------------------
def decide_mirror_action(
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
    """The single seam where mirror intent meets the neutral decision function.

    This is the ONLY place ``decide()`` is invoked for this domain. All mirror
    translation happened in the functions above; here we hand the neutral
    substrate a fully generic request + signed grant + policy, and it returns a
    generic AuthorizationDecision. The substrate never sees the words "mirror",
    "cpu_load", or "tune".
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
