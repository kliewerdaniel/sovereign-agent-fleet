"""Phase 2 — Epistemic Contract tests (contract increment only).

These tests prove the contract was introduced WITHOUT smuggling authority into the
epistemic kernel, and that the decision boundary is deterministic and
epistemic-score-proof. They do NOT wire the financial firm in (that is a later
phase) and they do NOT move any financial object into fleet.epistemic.

The decisive invariant under test:

    an agent may have sophisticated epistemic standing (Belief/calibration)
    WITHOUT acquiring authority, and an authorized agent is governed WITHOUT its
    epistemic score ever becoming a permission.
"""
from __future__ import annotations

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
    decide,
)


# ---------------------------------------------------------------------------
# Helpers — mint a signed AuthorityGrant the way governance would (externally).
# ---------------------------------------------------------------------------
def _gov_keypair():
    k = Ed25519PrivateKey.generate()
    pem = k.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return k, pem


def _sign_grant(grant: AuthorityGrant, gov_key: Ed25519PrivateKey) -> AuthorityGrant:
    body = canonical_bytes(grant.state())
    sig = gov_key.sign(body).hex()
    d = {k: v for k, v in grant.state().items() if k != "kind"}
    return AuthorityGrant(**{**d, "signature": sig})


def _make_grant(gov_key, gov_pem, agent_id, scope_hash, epoch, granted=True):
    g = AuthorityGrant(
        grant_id="g1", agent_id=agent_id, authorization_scope_hash=scope_hash,
        epoch=epoch, issued_at=100, expires_at=10_000_000, governance_role="CRO",
        signer_pubkey_pem=gov_pem,
    )
    return _sign_grant(g, gov_key) if granted else g


# ---------------------------------------------------------------------------
# 1. Contract construction — five independent scopes, identity, no grant inside.
# ---------------------------------------------------------------------------
def test_contract_bundles_five_scopes_and_identity():
    ident = AgentIdentity(
        agent_id="researcher-1", role="researcher", capabilities=("quant_compute",),
        cert_seq=1, issued_at=0, expires_at=10_000_000,
        pubkey_pem="x", root_sig="y",
    )
    contract = EpistemicContract(
        identity=ident,
        epistemic_scope=EpistemicScope(proposition_domains=("market_probability",)),
        evidence_scope=EvidenceScope(produces=("inference",)),
        proposal_scope=ProposalScope(action_descriptors=("submit_for_validation",)),
        capability_scope=CapabilityScope(capabilities=("quant_compute",)),
        authorization_scope=AuthorizationScope(actions=(), governance_role=""),
    )
    assert contract.identity.agent_id == "researcher-1"
    # Five scopes are independently addressable and stored separately.
    assert contract.epistemic_scope.KIND == "epistemic_scope"
    assert contract.capability_scope.KIND == "capability_scope"
    assert contract.authorization_scope.KIND == "authorization_scope"
    # The contract does NOT carry a live grant; only a reference (or none).
    assert contract.authority_grant_ref is None


def test_scopes_are_not_merged_into_one_authority_blob():
    es = EpistemicScope(proposition_domains=("m",))
    cs = CapabilityScope(capabilities=("run_backtest",))
    az = AuthorizationScope(actions=("exchange.trade_execute",))
    # Each scope owns exactly one dimension; none of them carries another's power.
    # Epistemic scope holds no capability; capability scope holds no authorization action
    # that doubles as permission; authorization scope is merely a descriptor, not a grant.
    assert not hasattr(es, "capabilities")
    assert not hasattr(es, "actions")
    assert not hasattr(cs, "actions")  # capability != authorization action
    # AuthorizationScope describes what COULD be granted; it is not a grant itself.
    assert az.actions == ("exchange.trade_execute",)
    # Sanity: the three are distinct objects with distinct kinds.
    assert {es.KIND, cs.KIND, az.KIND} == {
        "epistemic_scope", "capability_scope", "authorization_scope"
    }


# ---------------------------------------------------------------------------
# 2. Epoch supersession (R3) — stale grants are structurally rejected.
# ---------------------------------------------------------------------------
def test_grant_with_current_epoch_is_valid_and_stale_is_rejected():
    gov_key, gov_pem = _gov_keypair()
    az = AuthorizationScope(actions=("risk.halt",), governance_role="CRO")
    ident = AgentIdentity(agent_id="cro-1", role="human", capabilities=("risk.halt",),
                          cert_seq=1, issued_at=0, expires_at=10_000_000,
                          pubkey_pem="x", root_sig="y")

    grant = _make_grant(gov_key, gov_pem, "cro-1", az.compute_hash(), epoch=5)
    assert grant.is_current(current_epoch=5, now=200) is True
    # Epoch advanced -> superseded regardless of TTL.
    assert grant.is_current(current_epoch=6, now=200) is False
    # TTL passed -> rejected even at same epoch.
    assert grant.is_current(current_epoch=5, now=20_000_000) is False


# ---------------------------------------------------------------------------
# 3. Externally-issued grant — agent cannot self-grant or forge.
# ---------------------------------------------------------------------------
def test_agent_cannot_self_sign_grant():
    gov_key, gov_pem = _gov_keypair()
    attacker_key = Ed25519PrivateKey.generate()
    attacker_pem = attacker_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    az = AuthorizationScope(actions=("exchange.trade_execute",))
    # Attacker forges a grant signed with their OWN key, claiming gov pubkey.
    forged = AuthorityGrant(
        grant_id="f", agent_id="attacker", authorization_scope_hash=az.compute_hash(),
        epoch=1, issued_at=0, expires_at=10_000_000,
        signer_pubkey_pem=gov_pem,
    )
    forged = _sign_grant(forged, attacker_key)  # signed by attacker, NOT governance
    # Verification against the REAL governance pubkey must reject it.
    assert forged.verify_grant(issuer_pubkey_pem=gov_pem) is False


def test_grant_is_bound_to_identity_cannot_be_transferred():
    gov_key, gov_pem = _gov_keypair()
    az = AuthorizationScope(actions=("risk.halt",))
    grant = _make_grant(gov_key, gov_pem, "cro-1", az.compute_hash(), epoch=1)
    # Same scope hash, but a different agent tries to use it.
    other = AgentIdentity(agent_id="someone-else", role="human", capabilities=(),
                          cert_seq=1, issued_at=0, expires_at=10_000_000,
                          pubkey_pem="x", root_sig="y")
    req = AuthorizationRequest(producer="someone-else", capability="risk.halt",
                              action_descriptor="halt", proposal_ref="p")
    dec = decide(identity=other, grant=grant, authorization_scope=az, request=req,
                 constraints=GovernanceConstraints(allowlist=("risk.halt",)),
                 current_epoch=1, now=200, trusted_issuer_pubkey_pem=gov_pem)
    assert dec.verdict == "BLOCKED"
    assert dec.reason == "agent_mismatch"


# ---------------------------------------------------------------------------
# 4. The decisive gate: epistemic score NEVER becomes authorization.
# ---------------------------------------------------------------------------
def test_high_calibration_belief_grants_no_authority():
    # A researcher with excellent epistemic standing + a strong Belief.
    prop = Proposition(domain="market_probability", subject="KXIN", predicate="P_yes")
    strong_belief = Belief(producer="researcher-1", proposition=prop,
                           estimate=Uncertainty.point(0.97), evidence_refs=[])

    gov_key, gov_pem = _gov_keypair()
    # ...but the researcher holds NO trade_execute grant.
    ident = AgentIdentity(agent_id="researcher-1", role="researcher",
                          capabilities=("quant_compute",), cert_seq=1, issued_at=0,
                          expires_at=10_000_000, pubkey_pem="x", root_sig="y")
    az = AuthorizationScope(actions=(), governance_role="")  # nothing granted
    grant = _make_grant(gov_key, gov_pem, "researcher-1", az.compute_hash(), epoch=1)
    req = AuthorizationRequest(producer="researcher-1", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    dec = decide(identity=ident, grant=grant, authorization_scope=az, request=req,
                 constraints=GovernanceConstraints(allowlist=("exchange.trade_execute",)),
                 current_epoch=1, now=200, trusted_issuer_pubkey_pem=gov_pem)
    # The belief's 0.97 probability is irrelevant; no grant => BLOCKED.
    assert dec.verdict == "BLOCKED"
    assert dec.reason == "capability_not_granted"


def test_authorization_decision_carries_no_epistemic_field():
    # AuthorizationDecision.state() must contain no probability/confidence/score.
    d = AuthorizationDecision(verdict="AUTO", capability="x", request_ref="r",
                             grant_ref="g", scope_ref="s", epoch=1)
    for forbidden in ("p", "probability", "confidence", "score", "calibration",
                      "belief", "estimate"):
        assert forbidden not in d.state(), \
            f"AuthorizationDecision must not carry epistemic field {forbidden}"


def test_decide_signature_has_no_epistemic_parameter():
    # Static check: decide() must not accept probability/confidence/score args.
    import inspect
    params = set(inspect.signature(decide).parameters)
    for forbidden in ("probability", "confidence", "model_score", "calibration",
                      "belief", "recommendation"):
        assert forbidden not in params, \
            f"decide() must not accept epistemic input {forbidden}"


# ---------------------------------------------------------------------------
# 5. Deterministic decision ladder (mirrors financial decide_trade, generalized).
# ---------------------------------------------------------------------------
def test_authorized_request_decides_auto():
    gov_key, gov_pem = _gov_keypair()
    az = AuthorizationScope(actions=("exchange.trade_execute",), governance_role="PM")
    ident = AgentIdentity(agent_id="pm-1", role="human",
                          capabilities=("exchange.trade_execute",), cert_seq=1,
                          issued_at=0, expires_at=10_000_000, pubkey_pem="x",
                          root_sig="y")
    grant = _make_grant(gov_key, gov_pem, "pm-1", az.compute_hash(), epoch=2)
    req = AuthorizationRequest(producer="pm-1", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    dec = decide(identity=ident, grant=grant, authorization_scope=az, request=req,
                 constraints=GovernanceConstraints(allowlist=("exchange.trade_execute",)),
                 current_epoch=2, now=200, trusted_issuer_pubkey_pem=gov_pem)
    assert dec.verdict == "AUTO"


def test_authorized_but_human_required():
    gov_key, gov_pem = _gov_keypair()
    az = AuthorizationScope(actions=("exchange.trade_execute",))
    ident = AgentIdentity(agent_id="pm-1", role="human",
                          capabilities=("exchange.trade_execute",), cert_seq=1,
                          issued_at=0, expires_at=10_000_000, pubkey_pem="x",
                          root_sig="y")
    grant = _make_grant(gov_key, gov_pem, "pm-1", az.compute_hash(), epoch=2)
    req = AuthorizationRequest(producer="pm-1", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    dec = decide(identity=ident, grant=grant, authorization_scope=az, request=req,
                 constraints=GovernanceConstraints(
                     allowlist=("exchange.trade_execute",),
                     require_human_approval=True),
                 current_epoch=2, now=200, trusted_issuer_pubkey_pem=gov_pem)
    assert dec.verdict == "HUMAN"


# ---------------------------------------------------------------------------
# 6. ADVERSARIAL — the pressure points the contract must hold.
# ---------------------------------------------------------------------------
def test_unsigned_grant_is_rejected():
    gov_key, gov_pem = _gov_keypair()
    az = AuthorizationScope(actions=("exchange.trade_execute",))
    ident = AgentIdentity(agent_id="pm-1", role="human",
                          capabilities=("exchange.trade_execute",), cert_seq=1,
                          issued_at=0, expires_at=10_000_000, pubkey_pem="x",
                          root_sig="y")
    # Grant with empty signature (never signed by governance).
    grant = AuthorityGrant(grant_id="g", agent_id="pm-1",
                           authorization_scope_hash=az.compute_hash(), epoch=1,
                           issued_at=0, expires_at=10_000_000, signer_pubkey_pem=gov_pem)
    req = AuthorizationRequest(producer="pm-1", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    dec = decide(identity=ident, grant=grant, authorization_scope=az, request=req,
                 constraints=GovernanceConstraints(allowlist=("exchange.trade_execute",)),
                 current_epoch=1, now=200, trusted_issuer_pubkey_pem=gov_pem)
    assert dec.verdict == "BLOCKED" and dec.reason == "invalid_grant_signature"


def test_grant_scope_mismatch_is_rejected():
    gov_key, gov_pem = _gov_keypair()
    az = AuthorizationScope(actions=("exchange.trade_execute",))
    ident = AgentIdentity(agent_id="pm-1", role="human",
                          capabilities=("exchange.trade_execute",), cert_seq=1,
                          issued_at=0, expires_at=10_000_000, pubkey_pem="x",
                          root_sig="y")
    # Grant references a DIFFERENT scope than the one being exercised.
    other_scope = AuthorizationScope(actions=("risk.halt",))
    grant = _make_grant(gov_key, gov_pem, "pm-1", other_scope.compute_hash(), epoch=1)
    req = AuthorizationRequest(producer="pm-1", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    dec = decide(identity=ident, grant=grant, authorization_scope=az, request=req,
                 constraints=GovernanceConstraints(allowlist=("exchange.trade_execute",)),
                 current_epoch=1, now=200, trusted_issuer_pubkey_pem=gov_pem)
    assert dec.verdict == "BLOCKED" and dec.reason == "scope_mismatch"


def test_probability_cannot_be_smuggled_into_decision():
    # Even if a caller tried to attach extra epistemic values to the request, the
    # AuthorizationRequest schema has no such field and decide() ignores nothing.
    req = AuthorizationRequest(producer="pm-1", capability="exchange.trade_execute",
                              action_descriptor="BUY", proposal_ref="p")
    assert "p_yes" not in req.state()
    assert "confidence" not in req.state()


def test_phase1_objects_still_carry_no_authority():
    # Regression: Phase 1 guarantees still hold after Phase 2 added.
    from fleet.epistemic import Recommendation
    r = Recommendation(producer="pm")
    assert r.authority == "NONE"
    assert r.state()["authority"] == "NONE"


def test_contract_can_be_serialized_for_ledger():
    ident = AgentIdentity(agent_id="a", role="tool", capabilities=("c",),
                          cert_seq=1, issued_at=0, expires_at=10_000_000,
                          pubkey_pem="x", root_sig="y")
    contract = EpistemicContract(
        identity=ident,
        epistemic_scope=EpistemicScope(),
        evidence_scope=EvidenceScope(),
        proposal_scope=ProposalScope(),
        capability_scope=CapabilityScope(),
        authorization_scope=AuthorizationScope(),
    )
    h = contract.compute_hash()
    assert isinstance(h, str) and len(h) == 64
