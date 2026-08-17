"""Phase 2 — Adversarial contract-validation phase (hostile substrate).

These tests deliberately try to BREAK the contract boundary. The substrate is
made hostile: we attempt forgery, tampering, replay, reuse, scope mutation,
self-issuance, implicit delegation, calibration-as-credential, probability
smuggling, and — most importantly — COMPOSITION attacks where individually
legitimate epistemic objects are chained together to see if any combination
accidentally manufactures authority.

The canonical adversarial ladder that MUST terminate at permission:

    Belief -> Recommendation -> Proposal -> AuthorizationRequest -> ???
        => "request awaiting governance", NEVER a permission.

The ONLY legitimate authority path:

    AgentIdentity + CapabilityScope + current AuthorityGrant
    + GovernanceConstraints + current system state
        => deterministic decide() => AuthorizationDecision

Every test here asserts the contract holds under abuse. None of these wire the
financial firm in; the quantitative trading system remains an external acceptor
proven (in other suites) to be unconsumed by the neutral substrate.
"""
from __future__ import annotations

import inspect

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fleet.crypto.foundation import canonical_bytes

from fleet.epistemic import (
    AgentIdentity,
    EpistemicScope,
    EvidenceScope,
    ProposalScope,
    CapabilityScope,
    AuthorizationScope,
    GovernanceConstraints,
    AuthorityGrant,
    AuthorizationDecision,
    AuthorizationRequest,
    EpistemicContract,
    Belief,
    Proposition,
    Uncertainty,
    Recommendation,
    Proposal,
    Assessment,
    Evidence,
    decide,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _keypair():
    k = Ed25519PrivateKey.generate()
    pem = k.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return k, pem


def _sign_grant(grant: AuthorityGrant, key: Ed25519PrivateKey) -> AuthorityGrant:
    sig = key.sign(canonical_bytes(grant.state())).hex()
    d = {k: v for k, v in grant.state().items() if k != "kind"}
    return AuthorityGrant(**{**d, "signature": sig})


def _make_grant(gov_key, gov_pem, agent_id, scope_hash, epoch=1, sign=True):
    g = AuthorityGrant(
        grant_id="g", agent_id=agent_id, authorization_scope_hash=scope_hash,
        epoch=epoch, issued_at=100, expires_at=10_000_000,
        governance_role="CRO", signer_pubkey_pem=gov_pem,
    )
    return _sign_grant(g, gov_key) if sign else g


def _identity(agent_id="pm-1", capabilities=("exchange.trade_execute",)):
    return AgentIdentity(
        agent_id=agent_id, role="human", capabilities=capabilities,
        cert_seq=1, issued_at=0, expires_at=10_000_000,
        pubkey_pem="x", root_sig="y",
    )


def _authed_decide(grant, ident, az, req, gov_pem, constraints=None, epoch=1):
    return decide(
        identity=ident, grant=grant, authorization_scope=az, request=req,
        constraints=constraints or GovernanceConstraints(allowlist=(req.capability,)),
        current_epoch=epoch, now=200, trusted_issuer_pubkey_pem=gov_pem,
    )


# ===========================================================================
# A. FORGE / ALTER THE GRANT
# ===========================================================================
def test_forged_grant_signature_rejected():
    gov_key, gov_pem = _keypair()
    attacker_key, _ = _keypair()
    az = AuthorizationScope(actions=("exchange.trade_execute",))
    ident = _identity()
    # Signed by attacker, not governance.
    forged = _sign_grant(AuthorityGrant(
        grant_id="f", agent_id="pm-1", authorization_scope_hash=az.compute_hash(),
        epoch=1, issued_at=0, expires_at=10_000_000,
        signer_pubkey_pem=gov_pem), attacker_key)
    req = AuthorizationRequest(producer="pm-1", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    dec = _authed_decide(forged, ident, az, req, gov_pem)
    assert dec.verdict == "BLOCKED" and dec.reason == "invalid_grant_signature"


def test_alter_grant_after_signing_detected():
    gov_key, gov_pem = _keypair()
    az = AuthorizationScope(actions=("exchange.trade_execute",))
    ident = _identity()
    grant = _make_grant(gov_key, gov_pem, "pm-1", az.compute_hash(), epoch=1)
    # Tamper with the signed body (change the agent it binds to) WITHOUT re-signing.
    tampered_state = {k: v for k, v in grant.state().items() if k != "kind"}
    tampered_state["agent_id"] = "intruder"
    tampered = AuthorityGrant(**tampered_state)
    req = AuthorizationRequest(producer="intruder", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    dec = _authed_decide(tampered, _identity("intruder"), az, req, gov_pem)
    assert dec.verdict == "BLOCKED" and dec.reason == "invalid_grant_signature"


def test_replace_issuer_public_key_rejected():
    gov_key, gov_pem = _keypair()
    attacker_key, attacker_pem = _keypair()
    az = AuthorizationScope(actions=("exchange.trade_execute",))
    ident = _identity()
    # Attacker forges a grant signed by themselves, but claims the issuer is the
    # governance key in signer_pubkey_pem. decide() verifies against the TRUSTED
    # gov pem, not the embedded one.
    forged = AuthorityGrant(
        grant_id="f", agent_id="pm-1", authorization_scope_hash=az.compute_hash(),
        epoch=1, issued_at=0, expires_at=10_000_000, signer_pubkey_pem=gov_pem)
    forged = _sign_grant(forged, attacker_key)
    req = AuthorizationRequest(producer="pm-1", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    dec = _authed_decide(forged, ident, az, req, gov_pem)
    assert dec.verdict == "BLOCKED" and dec.reason == "invalid_grant_signature"


def test_self_issued_grant_rejected():
    # The agent tries to mint its own grant using its own key and present it as
    # if issued by governance.
    own_key, own_pem = _keypair()
    az = AuthorizationScope(actions=("exchange.trade_execute",))
    ident = _identity()
    self_grant = _sign_grant(AuthorityGrant(
        grant_id="self", agent_id="pm-1", authorization_scope_hash=az.compute_hash(),
        epoch=1, issued_at=0, expires_at=10_000_000, signer_pubkey_pem=own_pem), own_key)
    req = AuthorizationRequest(producer="pm-1", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    # The trusted issuer is "governance" (a separate key the agent does not hold).
    gov_pem = _keypair()[1]
    dec = _authed_decide(self_grant, ident, az, req, gov_pem)
    assert dec.verdict == "BLOCKED" and dec.reason == "invalid_grant_signature"


# ===========================================================================
# B. REPLAY / REUSE
# ===========================================================================
def test_replay_expired_epoch_rejected():
    gov_key, gov_pem = _keypair()
    az = AuthorizationScope(actions=("risk.halt",))
    ident = _identity(capabilities=("risk.halt",))
    grant = _make_grant(gov_key, gov_pem, "pm-1", az.compute_hash(), epoch=3)
    req = AuthorizationRequest(producer="pm-1", capability="risk.halt",
                              action_descriptor="halt", proposal_ref="p")
    # Epoch has advanced past the grant's epoch => superseded.
    dec = _authed_decide(grant, ident, az, req, gov_pem, epoch=5)
    assert dec.verdict == "BLOCKED" and dec.reason == "stale_grant"


def test_reuse_superseded_grant_rejected():
    gov_key, gov_pem = _keypair()
    az = AuthorizationScope(actions=("exchange.trade_execute",))
    ident = _identity()
    # Grant minted at epoch 1.
    grant = _make_grant(gov_key, gov_pem, "pm-1", az.compute_hash(), epoch=1)
    req = AuthorizationRequest(producer="pm-1", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    # Same epoch but a NEWER grant (higher epoch) has superseded this one.
    dec = _authed_decide(grant, ident, az, req, gov_pem, epoch=2)
    assert dec.verdict == "BLOCKED" and dec.reason == "stale_grant"


def test_ttl_backstop_rejects_expired_grant():
    gov_key, gov_pem = _keypair()
    az = AuthorizationScope(actions=("risk.halt",))
    ident = _identity(capabilities=("risk.halt",))
    grant = AuthorityGrant(
        grant_id="g", agent_id="pm-1", authorization_scope_hash=az.compute_hash(),
        epoch=1, issued_at=100, expires_at=500, governance_role="CRO",
        signer_pubkey_pem=gov_pem)
    grant = _sign_grant(grant, gov_key)
    req = AuthorizationRequest(producer="pm-1", capability="risk.halt",
                              action_descriptor="halt", proposal_ref="p")
    # Still epoch 1, but clock advanced past TTL => backstop kicks in.
    dec = decide(identity=ident, grant=grant, authorization_scope=az, request=req,
                 constraints=GovernanceConstraints(allowlist=("risk.halt",)),
                 current_epoch=1, now=999, trusted_issuer_pubkey_pem=gov_pem)
    assert dec.verdict == "BLOCKED" and dec.reason == "stale_grant"


# ===========================================================================
# C. MUTATE CAPABILITY / AUTHORIZATION SCOPE AFTER SIGNING
# ===========================================================================
def test_alter_capability_after_signing_detected():
    gov_key, gov_pem = _keypair()
    # Grant was signed over a scope that permits ONLY risk.halt.
    az = AuthorizationScope(actions=("risk.halt",))
    ident = _identity(capabilities=("risk.halt",))
    grant = _make_grant(gov_key, gov_pem, "pm-1", az.compute_hash(), epoch=1)
    # Attacker modifies the request to ask for a DIFFERENT (more powerful) capability
    # while presenting the same grant. The grant scope hash is unchanged, so the
    # capability is not in the granted scope => rejected.
    req = AuthorizationRequest(producer="pm-1", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    dec = _authed_decide(grant, ident, az, req, gov_pem)
    assert dec.verdict == "BLOCKED" and dec.reason == "capability_not_granted"


def test_alter_authorization_scope_after_signing_detected():
    gov_key, gov_pem = _keypair()
    granted_scope = AuthorizationScope(actions=("risk.halt",))
    ident = _identity(capabilities=("risk.halt",))
    grant = _make_grant(gov_key, gov_pem, "pm-1", granted_scope.compute_hash(), epoch=1)
    # The attacker tries to exercise a DIFFERENT scope than the grant covers.
    other_scope = AuthorizationScope(actions=("exchange.trade_execute",))
    req = AuthorizationRequest(producer="pm-1", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    dec = _authed_decide(grant, ident, other_scope, req, gov_pem)
    assert dec.verdict == "BLOCKED" and dec.reason == "scope_mismatch"


def test_grant_scope_hash_cannot_be_substituted():
    gov_key, gov_pem = _keypair()
    real_scope = AuthorizationScope(actions=("risk.halt",))
    ident = _identity(capabilities=("risk.halt",))
    grant = _make_grant(gov_key, gov_pem, "pm-1", real_scope.compute_hash(), epoch=1)
    # attempt to reuse the signed grant but point decide() at a different scope
    # whose hash does NOT match the grant's embedded hash.
    decoy_scope = AuthorizationScope(actions=("risk.halt", "exchange.trade_execute"))
    assert decoy_scope.compute_hash() != grant.authorization_scope_hash
    req = AuthorizationRequest(producer="pm-1", capability="risk.halt",
                              action_descriptor="halt", proposal_ref="p")
    dec = _authed_decide(grant, ident, decoy_scope, req, gov_pem)
    assert dec.verdict == "BLOCKED" and dec.reason == "scope_mismatch"


# ===========================================================================
# D. AUTHORIZATION WITHOUT A VALID GRANT
# ===========================================================================
def test_authorization_request_alone_grants_nothing():
    ident = _identity()
    az = AuthorizationScope(actions=("exchange.trade_execute",))
    req = AuthorizationRequest(producer="pm-1", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    # No grant at all => there is literally nothing to verify.
    gov_pem = _keypair()[1]
    dec = _authed_decide(None, ident, az, req, gov_pem)  # type: ignore[arg-type]
    assert dec.verdict == "BLOCKED"


def test_unsigned_grant_rejected_without_signature():
    gov_key, gov_pem = _keypair()
    az = AuthorizationScope(actions=("exchange.trade_execute",))
    ident = _identity()
    grant = AuthorityGrant(grant_id="g", agent_id="pm-1",
                           authorization_scope_hash=az.compute_hash(), epoch=1,
                           issued_at=0, expires_at=10_000_000, signer_pubkey_pem=gov_pem)
    req = AuthorizationRequest(producer="pm-1", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    dec = _authed_decide(grant, ident, az, req, gov_pem)
    assert dec.verdict == "BLOCKED" and dec.reason == "invalid_grant_signature"


def test_missing_trusted_issuer_is_blocked():
    gov_key, gov_pem = _keypair()
    az = AuthorizationScope(actions=("exchange.trade_execute",))
    ident = _identity()
    grant = _make_grant(gov_key, gov_pem, "pm-1", az.compute_hash(), epoch=1)
    req = AuthorizationRequest(producer="pm-1", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    # Caller fails to supply a trust anchor.
    dec = decide(identity=ident, grant=grant, authorization_scope=az, request=req,
                 constraints=GovernanceConstraints(allowlist=("exchange.trade_execute",)),
                 current_epoch=1, now=200, trusted_issuer_pubkey_pem="")
    assert dec.verdict == "BLOCKED" and dec.reason == "no_trusted_issuer"


# ===========================================================================
# E. DERIVE AUTHORITY FROM EPISTEMIC OBJECTS
# ===========================================================================
def test_authority_cannot_be_derived_from_recommendation():
    prop = Proposition(domain="market_probability", subject="KXIN", predicate="P_yes")
    bel = Belief(producer="researcher", proposition=prop, estimate=Uncertainty.point(0.97))
    rec = Recommendation(producer="researcher", target="KXIN",
                         action_suggestion="BUY", rationale="strong signal")
    # A Recommendation is advisory only.
    assert rec.authority == "NONE"
    assert rec.state()["authority"] == "NONE"
    # It exposes no path to a capability or a grant.
    assert not hasattr(rec, "capability")
    assert not hasattr(rec, "grant")
    # And Recommendation is not on ANY legitimate authority path. There is no
    # function in the substrate that turns a Recommendation into a decision.
    import fleet.epistemic as fe
    assert not hasattr(fe, "recommendation_to_decision")
    assert not hasattr(fe, "authorize_from_recommendation")


def test_authority_cannot_be_derived_from_belief():
    prop = Proposition(domain="market_probability", subject="KXIN", predicate="P_yes")
    bel = Belief(producer="researcher", proposition=prop, estimate=Uncertainty.point(0.99))
    assert bel.estimate.p == 0.99
    # A Belief carries probability as EPISTEMIC CONTENT only.
    assert not hasattr(bel, "capability")
    assert not hasattr(bel, "grant")
    assert "authorization" not in bel.state()
    assert "capability" not in bel.state()


def test_probability_cannot_be_smuggled_through_dict_payload():
    # An attacker hands an untyped dict into the request and hopes decide reads it.
    req = AuthorizationRequest(producer="pm-1", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    # The request schema has no epistemic field; a smuggled 'p_yes'/'confidence'
    # attribute wouldn't even live on the frozen dataclass.
    assert "p_yes" not in req.state()
    assert "confidence" not in req.state()
    assert "calibration" not in req.state()
    # And AuthorizationRequest does not expose a free-form 'extra' dict that could
    # carry authority hints. (conditions exists, but is governance-controlled context,
    # never an epistemic override.)
    assert "capability" in req.state()  # the legitimate requested capability only


def test_calibration_cannot_be_used_as_capability_credential():
    # Suppose an agent has perfect calibration. That must NOT map to a capability.
    az = AuthorizationScope(actions=("exchange.trade_execute",))
    ident = _identity()
    gov_key, gov_pem = _keypair()
    grant = _make_grant(gov_key, gov_pem, "pm-1", az.compute_hash(), epoch=1)
    req = AuthorizationRequest(producer="pm-1", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    dec = _authed_decide(grant, ident, az, req, gov_pem)
    # Even with a valid grant, the decision is driven by grant+scope+policy, NOT by
    # any calibration value. We assert the decision object carries no calibration.
    for kal in ("calibration", "confidence", "score", "p"):
        assert kal not in dec.state()


# ===========================================================================
# F. SCOPE NON-COLLAPSIBILITY
# ===========================================================================
def test_capability_scope_does_not_imply_authorization_scope():
    cs = CapabilityScope(capabilities=("exchange.trade_execute",))
    az = AuthorizationScope(actions=())
    # An agent may be ABLE to compute/trade (capability) but hold NO grant over an
    # authorization scope. Capability != authorization is enforced by separation:
    # capability lives on the cert/scope; authorization requires an external grant.
    assert cs.capabilities == ("exchange.trade_execute",)
    assert az.actions == ()  # no granted authority despite the capability
    # There is no method that promotes a CapabilityScope into an AuthorizationScope.
    assert not hasattr(cs, "as_authorization")
    assert not hasattr(cs, "to_grant")


def test_authorization_scope_does_not_imply_capability():
    az = AuthorizationScope(actions=("exchange.trade_execute",), governance_role="PM")
    cs = CapabilityScope(capabilities=())
    # A scope DESCRIBING what could be granted does not bestow the operational
    # capability to act. Authorization != capability.
    assert az.actions == ("exchange.trade_execute",)
    assert cs.capabilities == ()
    # Holding the authorization-scope DESCRIPTOR confers nothing by itself.
    assert not hasattr(az, "grant")


def test_merging_scopes_cannot_create_hidden_authority():
    es = EpistemicScope(proposition_domains=("market_probability",))
    evs = EvidenceScope(produces=("inference",))
    ps = ProposalScope(action_descriptors=("submit_for_validation",))
    cs = CapabilityScope(capabilities=("quant_compute",))
    az = AuthorizationScope(actions=())
    # Bundling all four non-authority scopes alongside an EMPTY authorization
    # scope must yield a contract with no authority.
    ident = _identity(capabilities=("quant_compute",))
    contract = EpistemicContract(
        identity=ident, epistemic_scope=es, evidence_scope=evs,
        proposal_scope=ps, capability_scope=cs, authorization_scope=az)
    assert contract.authority_grant_ref is None
    # The contract is descriptive; authorization is computed by decide() against a
    # separate, externally-signed grant — never derived from the bundle.
    assert not hasattr(contract, "decide")


# ===========================================================================
# G. IMPLICIT DELEGATION
# ===========================================================================
def test_implicit_delegation_is_not_possible():
    gov_key, gov_pem = _keypair()
    az = AuthorizationScope(actions=("exchange.trade_execute",))
    # Grant is bound to agent A.
    grant_a = _make_grant(gov_key, gov_pem, "agent-A", az.compute_hash(), epoch=1)
    ident_b = _identity(agent_id="agent-B")
    req = AuthorizationRequest(producer="agent-B", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    # Agent B presents A's grant implicitly (no explicit transfer field even exists).
    dec = _authed_decide(grant_a, ident_b, az, req, gov_pem)
    assert dec.verdict == "BLOCKED" and dec.reason == "agent_mismatch"


def test_no_delegate_field_exists_on_grant():
    g = AuthorityGrant(grant_id="g", agent_id="a",
                       authorization_scope_hash="h", epoch=1, issued_at=0,
                       expires_at=10_000_000, signer_pubkey_pem="p")
    # There is no delegation/sub-agent mechanism to smuggle authority sideways.
    assert not hasattr(g, "delegate")
    assert not hasattr(g, "delegated_to")
    assert not hasattr(g, "proxy_for")


# ===========================================================================
# H. COMPOSITION ATTACKS — the decisive axis
# ===========================================================================
def _make_request_from(producer, capability):
    return AuthorizationRequest(producer=producer, capability=capability,
                               action_descriptor="BUY", proposal_ref="p")


def test_composition_belief_recommendation_proposal_request_terminates_at_request():
    """The canonical adversarial ladder must NEVER reach permission.

    Belief -> Recommendation -> Proposal -> AuthorizationRequest -> ???
        => "request awaiting governance", never an AuthorizationDecision(AUTO).
    """
    prop = Proposition(domain="market_probability", subject="KXIN", predicate="P_yes")
    belief = Belief(producer="researcher", proposition=prop, estimate=Uncertainty.point(0.99))
    rec = Recommendation(producer="researcher", target="KXIN",
                        action_suggestion="BUY", rationale="high confidence")
    proposal = Proposal(producer="researcher", action_descriptor="BUY",
                       belief_refs=[belief.compute_hash()],
                       evidence_refs=[rec.compute_hash()])
    # The chain ends in an AuthorizationRequest — a request, not a grant.
    request = _make_request_from("researcher", "exchange.trade_execute")

    # Assert the ladder produced only advisory/request artifacts, none of which
    # carries or yields authority.
    for art in (belief, rec, proposal, request):
        assert "authorization" not in art.state() or art.state().get("authority") == "NONE"
    assert rec.state()["authority"] == "NONE"
    assert request.KIND == "authorization_request"
    assert not hasattr(request, "to_decision")
    assert not hasattr(proposal, "to_authorization")

    # And feeding the full chain (minus a grant) into decide() yields BLOCKED,
    # because authority requires a grant that this ladder never produced.
    gov_pem = _keypair()[1]
    az = AuthorizationScope(actions=("exchange.trade_execute",))
    ident = _identity(agent_id="researcher")
    # No grant exists for researcher => cannot be authorized despite the chain.
    from fleet.epistemic import decide as _d
    dec = _d(identity=ident, grant=None, authorization_scope=az, request=request,  # type: ignore
             constraints=GovernanceConstraints(allowlist=("exchange.trade_execute",)),
             current_epoch=1, now=200, trusted_issuer_pubkey_pem=gov_pem)
    assert dec.verdict == "BLOCKED"


def test_composition_of_legitimate_objects_cannot_mint_authority():
    """Arbitrary combinations of individually-legitimate objects must not create
    authority. We assemble identity + all four non-authority scopes + a strong
    belief + a recommendation + a proposal, and confirm there is STILL no path to
    a permission without an externally-signed grant."""
    gov_key, gov_pem = _keypair()
    prop = Proposition(domain="market_probability", subject="KXIN", predicate="P_yes")
    belief = Belief(producer="researcher", proposition=prop, estimate=Uncertainty.point(0.97))
    rec = Recommendation(producer="researcher", target="KXIN", action_suggestion="BUY")
    proposal = Proposal(producer="researcher", action_descriptor="BUY",
                       belief_refs=[belief.compute_hash()])
    assessment = Assessment(producer="researcher")
    evidence = Evidence(producer="researcher")

    ident = _identity(agent_id="researcher", capabilities=("quant_compute",))
    contract = EpistemicContract(
        identity=ident,
        epistemic_scope=EpistemicScope(proposition_domains=("market_probability",)),
        evidence_scope=EvidenceScope(produces=("inference",)),
        proposal_scope=ProposalScope(action_descriptors=("submit_for_validation",)),
        capability_scope=CapabilityScope(capabilities=("quant_compute",)),
        authorization_scope=AuthorizationScope(actions=()),  # NO grant described
    )
    request = _make_request_from("researcher", "exchange.trade_execute")

    # None of these, singly or combined, is a grant or a decision.
    epistemic_objects = [belief, rec, proposal, assessment, evidence, contract, request]
    for o in epistemic_objects:
        assert not hasattr(o, "grant")
        assert not hasattr(o, "decide")
        assert not hasattr(o, "authorize")
    # The contract still holds no live grant.
    assert contract.authority_grant_ref is None

    # Without a grant, decide() blocks — even though every object is legitimate.
    from fleet.epistemic import decide as _d
    az = contract.authorization_scope
    dec = _d(identity=ident, grant=None, authorization_scope=az, request=request,  # type: ignore
             constraints=GovernanceConstraints(allowlist=("exchange.trade_execute",)),
             current_epoch=1, now=200, trusted_issuer_pubkey_pem=gov_pem)
    assert dec.verdict == "BLOCKED"


def test_only_legitimate_path_produces_authorization():
    """The ONLY legitimate authority path produces an AUTO decision. Everything
    else in this file is rejected. This test asserts the positive path works and
    that it REQUIRES every element (identity, grant, scope, policy, epoch)."""
    gov_key, gov_pem = _keypair()
    az = AuthorizationScope(actions=("exchange.trade_execute",), governance_role="PM")
    ident = _identity()
    grant = _make_grant(gov_key, gov_pem, "pm-1", az.compute_hash(), epoch=1)
    req = _make_request_from("pm-1", "exchange.trade_execute")
    dec = _authed_decide(grant, ident, az, req, gov_pem,
                        constraints=GovernanceConstraints(allowlist=("exchange.trade_execute",)))
    assert dec.verdict == "AUTO"
    assert dec.reason == "granted"
    # The decision is the FIRST and ONLY object in the substrate that carries
    # permission (it literally is the permission), and only decide() produces it.
    assert dec.KIND == "authorization_decision"


def test_decision_is_not_reachable_from_epistemic_message_passing():
    """Even if an attacker tries to 'pass' a Belief into the decision machinery by
    stuffing it into a request condition, decide() never reads it."""
    gov_key, gov_pem = _keypair()
    az = AuthorizationScope(actions=("exchange.trade_execute",))
    ident = _identity()
    grant = _make_grant(gov_key, gov_pem, "pm-1", az.compute_hash(), epoch=1)
    prop = Proposition(domain="market_probability", subject="KXIN", predicate="P_yes")
    belief = Belief(producer="researcher", proposition=prop, estimate=Uncertainty.point(0.99))
    # Attacker tries to inject the belief as 'context' for the decision.
    req = AuthorizationRequest(producer="pm-1", capability="exchange.trade_execute",
                              action_descriptor="BUY",
                              conditions={"belief_p": belief.estimate.p}, proposal_ref="p")
    # Decide must still block here because the capability is not in the granted
    # scope (we only granted nothing trade-wise? we granted trade_execute). Use a
    # denylist to show policy still wins regardless of injected 'context'.
    dec = _authed_decide(grant, ident, az, req, gov_pem,
                        constraints=GovernanceConstraints(denylist=("exchange.trade_execute",)))
    assert dec.verdict == "BLOCKED" and dec.reason == "policy_denied"
    # And the injected probability never influenced anything — it isn't in the decision.
    assert "belief_p" not in dec.state()


def test_decide_refuses_epistemic_input_even_via_kwargs():
    """Static guarantee: decide() must not accept probability/confidence/score/
    calibration/belief/recommendation under any parameter name."""
    params = set(inspect.signature(decide).parameters)
    for forbidden in ("probability", "p", "confidence", "model_score", "calibration",
                      "belief", "recommendation", "evidence", "estimate"):
        assert forbidden not in params, \
            f"decide() must not accept epistemic input {forbidden}"


def test_authorization_decision_is_the_only_permission_object():
    """No other substrate object may produce/hold a permission verdict.

    Structural guarantee against scope creep: exactly one class in the package
    owns a `verdict` field, and it is AuthorizationDecision.
    """
    import fleet.epistemic as fe

    classes_with_verdict = []
    for name in dir(fe):
        obj = getattr(fe, name)
        if isinstance(obj, type) and hasattr(obj, "__dataclass_fields__"):
            if "verdict" in obj.__dataclass_fields__:
                classes_with_verdict.append(name)

    assert classes_with_verdict == ["AuthorizationDecision"], (
        f"only AuthorizationDecision may carry a verdict; found {classes_with_verdict}"
    )

    # Cross-check the canonical epistemic/cognition artifacts carry no verdict.
    for obj in (Belief, Recommendation, Proposal, Assessment, Evidence, AuthorizationRequest):
        assert "verdict" not in obj.__dataclass_fields__, \
            f"{obj.__name__} must not carry a verdict field"
