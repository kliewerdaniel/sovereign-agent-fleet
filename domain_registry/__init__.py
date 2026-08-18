"""Domain registry — harness over the SIX external consumers (M0 consolidation).

This is NOT a domain and NOT part of the substrate. It is a bilingual harness
node whose only job is to make the M0 domain-generality claim *operative and
parameterized*: instead of each domain suite re-asserting the same cross-generality
block, the registry owns a single uniform capability table and a single generic
decide path that all six consumers share.

It lives OUTSIDE both restricted trees (``fleet/epistemic/`` and every
``<domain>/sim.py``). It imports the neutral builders from the *reference*
adapter (``exchange.epistemic_adapter``) and the four capability constants from
each adapter. It calls the neutral ``fleet.epistemic.decide()`` directly — the
same function every domain's ``decide_*_action`` thin-wrapper calls.

    fleet.epistemic          exchange.epistemic_adapter (builders)
              ^                        ^
              |                        |
              +---- domain_registry ---+---- (capability constants only)
                      |
        exchange / incident / supply / hypothesis

The registry adds zero substrate behavior. It makes "add a domain" a one-line
table edit: append ``(label, capability)`` to ``REGISTERED_CAPABILITIES`` and the
single parametrized generality suite automatically covers the new domain.
"""
from __future__ import annotations

from dataclasses import dataclass

from exchange.epistemic_adapter import (
    build_authorization_scope,
    build_governance_constraints,
    issue_grant,
    GovernanceAuthority,
    CAP_TRADE_EXECUTE,
)
from incident.epistemic_adapter import CAP_INCIDENT_REMEDIATE
from supply.epistemic_adapter import CAP_SUPPLY_REORDER
from hypothesis.epistemic_adapter import CAP_HYPOTHESIS_RUN
from mirror.epistemic_adapter import CAP_MIRROR_SELF_TUNE
from grid.epistemic_adapter import CAP_GRID_BALANCE

from fleet.epistemic.identity import AgentIdentity
from fleet.epistemic.decision import AuthorizationRequest, decide
from fleet.crypto.foundation import AgentCert
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# The single source of truth: every registered external consumer, as a
# (human-readable label, literal capability string the substrate sees).
REGISTERED_CAPABILITIES: tuple[tuple[str, str], ...] = (
    ("exchange/finance", CAP_TRADE_EXECUTE),
    ("incident/security", CAP_INCIDENT_REMEDIATE),
    ("supply/logistics", CAP_SUPPLY_REORDER),
    ("hypothesis/research", CAP_HYPOTHESIS_RUN),
    ("mirror/self-observability", CAP_MIRROR_SELF_TUNE),
    ("grid/energy", CAP_GRID_BALANCE),
)


@dataclass(frozen=True)
class RegisteredDecision:
    """One substrate verdict produced through the registry's uniform path."""
    label: str
    capability: str
    verdict: str
    reason: str


def decide_registered(
    label: str,
    capability: str,
    *,
    policy_allow: bool,
    human: bool,
    gov: GovernanceAuthority,
    request_capability: str | None = None,
    now: int = 100,
    epoch: int = 1,
) -> RegisteredDecision:
    """Run ONE generic decide() for a registered capability.

    The substrate never sees ``label`` — only the literal ``capability`` string
    plus the generic (grant, scope, policy) tuple. This is exactly the input any
    domain's ``decide_*_action`` would produce; the registry just bypasses the
    domain-specific wrapper to prove the verdict depends on nothing else.

    The grant's scope is ALWAYS bound to ``capability`` (the registered one).
    ``request_capability`` (default = ``capability``) is what is actually
    requested; setting it to something else exercises the bounded-scope invariant
    (step 5: a request outside the granted scope is BLOCKED, regardless of
    policy).
    """
    request_capability = request_capability or capability
    cert = AgentCert(
        agent_id="registry-agent", pubkey_pem="pub", role="operator",
        capabilities=[capability], issued_at=0, expires_at=10**9,
        cert_seq=0, root_sig="",
    )
    ident = AgentIdentity.from_cert(cert)
    az = build_authorization_scope((capability,))
    constr = build_governance_constraints(
        allowlist=(capability,) if policy_allow else (),
        require_human_approval=human,
    )
    grant = gov.issue_grant(
        grant_id="g-reg", agent_id=ident.agent_id,
        authorization_scope=az, epoch=epoch, now=now)
    req = AuthorizationRequest(
        producer="registry", request_id="r-reg",
        capability=request_capability, action_descriptor="x", proposal_ref="")
    d = decide(
        identity=ident, grant=grant, authorization_scope=az, request=req,
        constraints=constr, current_epoch=epoch, now=now,
        trusted_issuer_pubkey_pem=gov.public_key_pem)
    return RegisteredDecision(label, capability, d.verdict, d.reason)


def decide_all(
    *, policy_allow: bool, human: bool,
    gov: GovernanceAuthority | None = None,
) -> list[RegisteredDecision]:
    """Decide through the registry for EVERY registered domain under one policy.

    The returned list preserves ``REGISTERED_CAPABILITIES`` order. Used by the
    single parametrized generality suite so that adding a domain is a table edit,
    not a new test.
    """
    gov = gov or GovernanceAuthority(Ed25519PrivateKey.generate())
    return [
        decide_registered(label, cap, policy_allow=policy_allow, human=human, gov=gov)
        for (label, cap) in REGISTERED_CAPABILITIES
    ]


__all__ = [
    "REGISTERED_CAPABILITIES",
    "RegisteredDecision",
    "decide_registered",
    "decide_all",
]
