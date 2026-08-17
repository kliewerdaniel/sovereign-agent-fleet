"""Phase 3 — agent-side translation: quant concepts -> neutral epistemic contract.

Every function here is a pure mapping from a financial object (which the neutral
substrate has never heard of) into one of the generic epistemic types defined in
``fleet.epistemic``. The financial *semantics* (edge, kelly, expiry, venue) never
cross into ``fleet.epistemic`` — they are rendered into domain-neutral fields
(proposition domain/subject/predicate, evidence payload, assessment condition/
observed/result, recommendation text). The substrate can hold and hash these
objects without ever knowing they originated in a trading system.

The single boundary the user insisted on: NONE of these translations produce
authority. They produce requests (``AuthorizationRequest``) that must later be
passed to ``decide()`` together with a signed ``AuthorityGrant`` issued by
governance. The adapter's ``decide_quant_order`` wires that end-to-end.
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

# Capability strings the financial firm uses. They are plain strings to the
# substrate; only the grant's AuthorizationScope + GovernanceConstraints know
# what they mean. They are NOT universal authorizations — they are scoped actions.
CAP_TRADE_EXECUTE = "exchange.trade_execute"
CAP_RISK_HALT = "risk.halt"


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
    """Neutral deterministic policy. The finance-specific policy is expressed as
    plain allow/deny lists + a human-approval flag — no trading object leaks in."""
    return GovernanceConstraints(
        allowlist=tuple(allowlist),
        denylist=tuple(denylist),
        require_human_approval=require_human_approval,
        policy_refs=tuple(policy_refs),
    )


# ---------------------------------------------------------------------------
# Quant cognition -> neutral epistemic artifacts (advisory, no authority)
# ---------------------------------------------------------------------------
def probability_to_proposition(
    est, domain: str = "market_probability", producer: str = "quant"
) -> Proposition:
    """ProbabilityEstimate -> neutral Proposition (the 'about what' statement)."""
    return Proposition(
        domain=domain,
        subject=f"exchange-{est.exchange_id}",
        predicate="P_yes",
        params={"model_id": est.model_id, "method": est.method},
    )


def probability_to_evidence(
    est, proposition: Proposition, producer: str = "quant"
) -> Evidence:
    """ProbabilityEstimate -> neutral Evidence (lineage node carrying the payload).

    The probability NUMBER lives only inside ``payload`` as opaque data. The
    substrate neither reads nor acts on it.
    """
    return Evidence(
        producer=producer,
        evidence_kind="statistic",
        payload={
            "p_yes": est.p_yes,
            "uncertainty": est.uncertainty,
            "model_id": est.model_id,
            "method": est.method,
        },
        inputs=[proposition.proposition_hash],
    )


def kelly_to_recommendation(
    kelly, proposition: Proposition, producer: str = "quant"
) -> Recommendation:
    """KellyProposal -> neutral Recommendation (advisory ONLY).

    ``authority`` is forced to "NONE" by the substrate's own __post_init__ guard,
    so this can never become a permission. The sizing is plain rationale text."""
    return Recommendation(
        producer=producer,
        target=proposition.subject,
        action_suggestion=f"size {kelly.proposed_qty} contracts (kelly {kelly.recommendation})",
        rationale=f"edge_bps={kelly.edge_bps}; proposed_usd={kelly.proposed_usd}",
        evidence_refs=[],
    )


def kelly_to_assessment(
    kelly, subject: str = "portfolio:EXC", producer: str = "quant"
) -> Assessment:
    """KellyProposal -> neutral Assessment (deterministic state-vs-policy view).

    ``result`` is a classification ("BET"/"NO_BET"), NOT a permission."""
    return Assessment(
        producer=producer,
        subject=subject,
        condition={"min_edge_bps": 0.0},
        observed={"edge_bps": kelly.edge_bps, "proposed_qty": kelly.proposed_qty},
        result=kelly.recommendation,  # "BET" / "NO_BET"
        reason="kelly sizing classification",
    )


# ---------------------------------------------------------------------------
# Requests (the boundary just before governance)
# ---------------------------------------------------------------------------
def proposal_to_request(
    *,
    request_id: str,
    capability: str,
    action_descriptor: str,
    proposal_ref: str,
    conditions: dict | None = None,
    producer: str = "quant",
) -> AuthorizationRequest:
    """Build an AuthorizationRequest from a proposal's hash. No authority granted."""
    return AuthorizationRequest(
        producer=producer,
        request_id=request_id,
        capability=capability,
        action_descriptor=action_descriptor,
        conditions=conditions or {},
        proposal_ref=proposal_ref,
    )


def trade_decision_to_request(
    *,
    request_id: str,
    capability: str,
    action_descriptor: str,
    client_order_id: str,
    qty: int,
    producer: str = "quant",
) -> AuthorizationRequest:
    """Map an exchange trade intent into a neutral AuthorizationRequest."""
    return AuthorizationRequest(
        producer=producer,
        request_id=request_id,
        capability=capability,
        action_descriptor=action_descriptor,
        conditions={"client_order_id": client_order_id, "qty": qty},
        proposal_ref="",
    )


# ---------------------------------------------------------------------------
# End-to-end: run the neutral decision over a financially-described order
# ---------------------------------------------------------------------------
def decide_quant_order(
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
    """The single seam where financial intent meets the neutral decision function.

    This is the ONLY place ``decide()`` is invoked. All financial translation
    happened in the functions above; here we hand the neutral substrate a fully
    generic request + signed grant + policy, and it returns a generic
    AuthorizationDecision. The substrate never sees the word "trade", "kelly",
    or "probability".
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
