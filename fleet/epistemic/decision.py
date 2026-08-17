"""Phase 2 — deterministic AuthorizationDecision + the decision boundary (R5/R6/R7).

`AuthorizationDecision` is the FIRST object in the whole substrate that carries
permission. It is produced ONLY by `decide()`, and `decide()` is a pure,
deterministic function whose inputs are:

    identity           (who is asking — AgentIdentity)
    grant              (externally-signed AuthorityGrant)
    authorization_scope(what the grant references — AuthorizationScope)
    request            (what is requested — AuthorizationRequest)
    constraints        (deterministic GovernanceConstraints)
    current_epoch, now (governed state — NEVER epistemic)

Crucially, `decide` accepts NO probability, confidence, model score, belief, or
calibration value. The verdict is determined entirely by capability + grant scope
+ epoch currency + policy. This is the faithful, domain-general version of the
existing `decide_trade` (which excludes probability) — the quant firm's governance
surface is an *adapter* over this, not a reimplementation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Optional

from .authority import AuthorityGrant
from .authorization import AuthorizationRequest
from .governance_constraints import GovernanceConstraints
from .identity import AgentIdentity
from .scope import AuthorizationScope


@dataclass(frozen=True)
class AuthorizationDecision:
    """The single permission-bearing artifact. Produced only by decide()."""

    KIND: ClassVar[str] = "authorization_decision"

    verdict: str                       # "AUTO" | "HUMAN" | "BLOCKED"
    capability: str
    request_ref: str                   # hash of the AuthorizationRequest
    grant_ref: str                    # hash of the governing AuthorityGrant
    scope_ref: str                    # hash of the AuthorizationScope
    epoch: int
    reason: str = ""

    def state(self) -> dict:
        # Deliberately contains NO epistemic field (no p / confidence / score).
        return {
            "kind": self.KIND,
            "verdict": self.verdict,
            "capability": self.capability,
            "request_ref": self.request_ref,
            "grant_ref": self.grant_ref,
            "scope_ref": self.scope_ref,
            "epoch": self.epoch,
            "reason": self.reason,
        }

    def compute_hash(self) -> str:
        from fleet.crypto.foundation import canonical_bytes, sha256
        return sha256(canonical_bytes(self.state()))


def decide(
    *,
    identity: AgentIdentity,
    grant: Optional[AuthorityGrant],
    authorization_scope: AuthorizationScope,
    request: AuthorizationRequest,
    constraints: GovernanceConstraints,
    current_epoch: int,
    now: int,
    trusted_issuer_pubkey_pem: str,
) -> AuthorizationDecision:
    """Pure deterministic authorization. NEVER reads an epistemic value.

    Returns an AuthorizationDecision with verdict AUTO / HUMAN / BLOCKED. The only
    inputs are identity, a valid current grant, the referenced scope, the request,
    deterministic policy constraints, governed state (epoch, clock), and the
    TRUSTED governance issuer public key.

    `trusted_issuer_pubkey_pem` is the trust anchor: the verifier (not the grant
    bearer) pins which key may mint authority. The grant may carry an embedded
    `signer_pubkey_pem` for descriptive purposes, but `decide()` must verify
    against the caller-supplied trusted key — otherwise an attacker could embed
    their own pubkey and self-sign a valid-looking grant. The substrate never
    imports or holds the governance key; the caller (a governance/authority
    runtime) provides it, keeping `fleet.epistemic` a validation layer, not a
    cryptographic/governance runtime.
    """
    req_hash = request.compute_hash()
    scope_hash = authorization_scope.compute_hash()

    # 0b. There must be a grant at all. decide() never manufactures one from
    #     epistemic objects, a request alone, or thin air. Check before any grant
    #     attribute access.
    if grant is None:
        return AuthorizationDecision(
            verdict="BLOCKED", capability=request.capability, request_ref=req_hash,
            grant_ref="", scope_ref=scope_hash, epoch=current_epoch, reason="no_grant",
        )

    grant_hash = grant.compute_hash()

    def blocked(reason: str) -> AuthorizationDecision:
        return AuthorizationDecision(
            verdict="BLOCKED", capability=request.capability, request_ref=req_hash,
            grant_ref=grant_hash, scope_ref=scope_hash, epoch=current_epoch, reason=reason,
        )

    # 0. The trust anchor must be supplied; we never mint or self-trust a key.
    if not trusted_issuer_pubkey_pem:
        return blocked("no_trusted_issuer")
        return blocked("no_grant")

    # 1. The grant must be a genuine externally-signed permission, verified
    #    against the TRUSTED issuer key (not the grant's self-described key).
    if not grant.signature or not grant.verify_grant(issuer_pubkey_pem=trusted_issuer_pubkey_pem):
        return blocked("invalid_grant_signature")

    # 2. R3 epoch-supersession (primary) + TTL backstop.
    if not grant.is_current(current_epoch, now):
        return blocked("stale_grant")

    # 3. The grant is bound to this identity; it cannot be transferred.
    if grant.agent_id != identity.agent_id:
        return blocked("agent_mismatch")

    # 4. The grant must reference exactly the scope being exercised.
    if grant.authorization_scope_hash != scope_hash:
        return blocked("scope_mismatch")

    # 5. The requested capability must be within the granted scope.
    if request.capability not in authorization_scope.actions:
        return blocked("capability_not_granted")

    # 6. Deterministic policy read (no probability/confidence/score involved).
    policy = constraints.decision_for(request.capability)
    if policy == "BLOCKED":
        return blocked("policy_denied")

    return AuthorizationDecision(
        verdict=policy, capability=request.capability, request_ref=req_hash,
        grant_ref=grant_hash, scope_ref=scope_hash, epoch=current_epoch,
        reason="granted",
    )
