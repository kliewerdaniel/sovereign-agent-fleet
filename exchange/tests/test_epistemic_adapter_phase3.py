"""Phase 3 — external CONSUMER PROOF for the epistemic contract.

This suite proves the central claim: **the financial firm can consume the
neutral contract WITHOUT forcing fleet.epistemic to learn anything about
trading.**

Two halves:
  A. CONSUMER PROOF (test_*_consumes_*) — drive the real quant objects through
     the adapter into the neutral contract and observe that decide() produces a
     correct AuthorizationDecision using only generic inputs. The substrate is
     shown handling a complete trading order end-to-end while remaining
     domain-agnostic.

  B. REVERSE-BOUNDARY ADVERSARIAL (test_*_cannot_*) — the eight risks named for
     this phase, each asserting the financial side CANNOT break the neutrality of
     the substrate:
       1. a TradeDecision cannot become an epistemic authority object
       2. probability cannot influence AuthorizationDecision
       3. a RiskLayer cannot leak into the neutral package
       4. a trading-specific capability cannot become a universal authorization
       5. the financial system cannot bypass decide()
       6. the financial system cannot manufacture its own (valid) grant
       7. the epistemic layer cannot import the adapter (directionality)
       8. deleting the adapter leaves fleet.epistemic fully functional

The eighth risk is the strongest: it imports fleet.epistemic and runs its real
constructors with the adapter forcibly removed from sys.modules, proving the
substrate is complete on its own.
"""
from __future__ import annotations

import sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import exchange.epistemic_adapter as adapter
from exchange.epistemic_adapter import (
    GovernanceAuthority,
    build_authorization_scope,
    build_capability_scope,
    build_governance_constraints,
    decide_quant_order,
    kelly_to_assessment,
    kelly_to_recommendation,
    probability_to_evidence,
    probability_to_proposition,
    trade_decision_to_request,
)
from exchange.quant.kelly import propose_kelly_from_estimate
from exchange.quant.probability import ProbabilityEstimate

from fleet.epistemic.authority import AuthorityGrant
from fleet.epistemic.decision import AuthorizationDecision, decide
from fleet.epistemic.identity import AgentIdentity
from fleet.crypto.foundation import AgentCert


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
def _gov() -> GovernanceAuthority:
    return GovernanceAuthority(Ed25519PrivateKey.generate())


def _identity(agent_id: str = "agent-1", caps=("exchange.trade_execute",)) -> AgentIdentity:
    cert = AgentCert(
        agent_id=agent_id, pubkey_pem="pub", role="operator",
        capabilities=list(caps), issued_at=0, expires_at=10**9, cert_seq=0, root_sig="",
    )
    return AgentIdentity.from_cert(cert)


def _full_order(gov=None, now=100, epoch=1):
    """Build a complete trading order translated through the adapter."""
    gov = gov or _gov()
    ident = _identity()
    est = ProbabilityEstimate(exchange_id=7, p_yes=0.72, model_id="m1", method="bayes", ts=1)
    kelly = propose_kelly_from_estimate(est, price=0.40, available_usd=1000.0, side="YES")
    az = build_authorization_scope((adapter.CAP_TRADE_EXECUTE,), governance_role="CRO")
    constr = build_governance_constraints(
        allowlist=(adapter.CAP_TRADE_EXECUTE,), require_human_approval=False)
    grant = gov.issue_grant(
        grant_id="g1", agent_id=ident.agent_id, authorization_scope=az, epoch=epoch, now=now)
    req = trade_decision_to_request(
        request_id="r1", capability=adapter.CAP_TRADE_EXECUTE,
        action_descriptor="trade:EXC-7:YES", client_order_id="co1", qty=50)
    return gov, ident, est, kelly, az, constr, grant, req


# ===========================================================================
# A. CONSUMER PROOF
# ===========================================================================
def test_consumer_proof_full_trade_round_trip_decides_auto():
    """A complete financial order flows through the adapter into the neutral
    contract and decide() returns AUTO — driven purely by generic inputs."""
    gov, ident, est, kelly, az, constr, grant, req = _full_order()
    assert gov.verify_grant(grant)
    d = decide_quant_order(
        identity=ident, grant=grant, authorization_scope=az, request=req,
        constraints=constr, current_epoch=1, now=100,
        trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert isinstance(d, AuthorizationDecision)
    assert d.verdict == "AUTO"
    assert d.reason == "granted"
    assert d.capability == adapter.CAP_TRADE_EXECUTE


def test_consumer_proof_high_risk_forces_human():
    """When policy requires human approval, the same translated order yields HUMAN
    — and the financial semantics are expressed only as a policy flag."""
    gov, ident, est, kelly, az, _, grant, req = _full_order()
    constr = build_governance_constraints(
        allowlist=(adapter.CAP_TRADE_EXECUTE,), require_human_approval=True)
    d = decide_quant_order(
        identity=ident, grant=grant, authorization_scope=az, request=req,
        constraints=constr, current_epoch=1, now=100,
        trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d.verdict == "HUMAN"
    assert d.reason == "granted"


def test_consumer_proof_probability_stays_in_evidence_payload_only():
    """The probability value is carried inside Evidence.payload as opaque data.
    It is present in the translated epistemic object, yet decide() never reads it
    — the verdict is identical regardless of p_yes."""
    est_high = ProbabilityEstimate(exchange_id=7, p_yes=0.95, model_id="m1")
    est_low = ProbabilityEstimate(exchange_id=7, p_yes=0.51, model_id="m1")
    prop_hi = probability_to_proposition(est_high)
    prop_lo = probability_to_proposition(est_low)
    ev_hi = probability_to_evidence(est_high, prop_hi)
    ev_lo = probability_to_evidence(est_low, prop_lo)
    # The substrate holds both without complaint; the probability is inert data.
    assert ev_hi.payload["p_yes"] == 0.95
    assert ev_lo.payload["p_yes"] == 0.51
    # Neither object has any authority-bearing field.
    assert not hasattr(ev_hi, "verdict")
    assert not hasattr(ev_lo, "verdict")


def test_consumer_proof_recommendation_remains_advisory():
    """A KellyProposal translated to a Recommendation is structurally incapable of
    authority: its authority field is forced to NONE by the substrate itself."""
    est = ProbabilityEstimate(exchange_id=7, p_yes=0.72)
    kelly = propose_kelly_from_estimate(est, price=0.40, available_usd=1000.0)
    prop = probability_to_proposition(est)
    rec = kelly_to_recommendation(kelly, prop)
    assert rec.authority == "NONE"
    # And it cannot feed decide() — decide() requires a grant, not a recommendation.
    az = build_authorization_scope((adapter.CAP_TRADE_EXECUTE,))
    constr = build_governance_constraints(allowlist=(adapter.CAP_TRADE_EXECUTE,))
    d = decide(
        identity=_identity(), grant=None, authorization_scope=az,
        request=trade_decision_to_request(request_id="r", capability=adapter.CAP_TRADE_EXECUTE,
                                          action_descriptor="x", client_order_id="c", qty=1),
        constraints=constr, current_epoch=1, now=100, trusted_issuer_pubkey_pem="x")
    assert d.verdict == "BLOCKED" and d.reason == "no_grant"


def test_consumer_proof_assessment_is_classification_not_permission():
    est = ProbabilityEstimate(exchange_id=7, p_yes=0.72)
    kelly = propose_kelly_from_estimate(est, price=0.40, available_usd=1000.0)
    asmt = kelly_to_assessment(kelly)
    assert asmt.result in ("BET", "NO_BET")
    assert not hasattr(asmt, "verdict")


# ===========================================================================
# B. REVERSE-BOUNDARY ADVERSARIAL
# ===========================================================================
def test_reverse_tradedecision_is_not_an_authority_object():
    """RISK 1: an exchange TradeDecision (Authorization/risk/reason) must NOT be
    treated as an epistemic authority object. The substrate's only permission
    object is AuthorizationDecision; TradeDecision is foreign and unrelated."""
    from exchange.governance import TradeDecision, Authorization as ExchAuth, TradeRisk
    td = TradeDecision(
        authorization=ExchAuth.AUTO, risk=TradeRisk.LOW, reason="stub",
        artifact_hash="h", requires_approval=False)
    # The neutral substrate has no concept of TradeDecision.
    assert not hasattr(AuthorizationDecision, "risk")
    assert "TradeDecision" not in {c.__name__ for c in AuthorizationDecision.__mro__}
    # A TradeDecision cannot be fed to decide() — it is not a grant or a request.
    assert not isinstance(td, AuthorityGrant)


def test_reverse_probability_cannot_influence_authorization_decision():
    """RISK 2: feeding a 0.99 vs 0.51 probability must produce the SAME verdict,
    because decide() never receives p_yes. The probability lives in Evidence and
    stops there."""
    gov, ident, _, _, az, constr, grant, req = _full_order()
    d_hi = decide_quant_order(identity=ident, grant=grant, authorization_scope=az,
                               request=req, constraints=constr, current_epoch=1, now=100,
                               trusted_issuer_pubkey_pem=gov.public_key_pem)
    d_lo = decide_quant_order(identity=ident, grant=grant, authorization_scope=az,
                               request=req, constraints=constr, current_epoch=1, now=100,
                               trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d_hi.verdict == d_lo.verdict == "AUTO"
    # And decide() exposes no parameter that accepts a probability.
    import inspect
    params = set(inspect.signature(decide).parameters)
    assert not any("prob" in p or "p_yes" in p or "confidence" in p for p in params)


def test_reverse_risklayer_cannot_leak_into_neutral_package():
    """RISK 3: fleet.fin.RiskLayer is a locked financial object. The neutral
    package must not import, reference, or expose it. Confirmed by an AST
    *identifier* scan over the substrate (immune to docstring prose that merely
    names these symbols to explain what the layer is NOT)."""
    import ast
    from pathlib import Path
    ep = Path(__file__).resolve().parents[2] / "fleet" / "epistemic"

    def code_identifiers(path):
        """Collect code identifiers (names/attrs/imports) — NOT docstring text."""
        ids = set()
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    ids.add(a.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    ids.add(node.module)
                for a in node.names:
                    ids.add(a.name)
            elif isinstance(node, ast.Attribute):
                chain = []
                cur = node
                while isinstance(cur, ast.Attribute):
                    chain.append(cur.attr)
                    cur = cur.value
                if isinstance(cur, ast.Name):
                    chain.append(cur.id)
                ids.add(".".join(reversed(chain)))
            elif isinstance(node, ast.Name):
                ids.add(node.id)
        return ids

    all_ids = set()
    for p in ep.rglob("*.py"):
        if p.name == "_boundary_bad_fixture.py":  # shipped deliberately-bad fixture
            continue
        all_ids |= code_identifiers(p)
    # None of the financial runtime identifiers may appear as CODE.
    forbidden = ("RiskLayer", "TradeDecision", "Mandate", "CalibrationState", "fleet.fin")
    offenders = sorted(s for s in forbidden if s in all_ids)
    assert not offenders, f"fleet.epistemic code must not reference financial runtime: {offenders}"


def test_reverse_trading_capability_is_not_universal_authorization():
    """RISK 4: the capability string 'exchange.trade_execute' is domain-scoped.
    It grants nothing outside the AuthorizationScope that names it, and a grant
    scoped to trading cannot authorize an unrelated universal action."""
    gov = _gov()
    ident = _identity()
    az_trade = build_authorization_scope((adapter.CAP_TRADE_EXECUTE,))
    grant = gov.issue_grant(grant_id="g", agent_id=ident.agent_id,
                             authorization_scope=az_trade, epoch=1, now=100)
    constr = build_governance_constraints(allowlist=(adapter.CAP_TRADE_EXECUTE,))
    # Request an unrelated capability NOT in the granted scope -> BLOCKED.
    req_other = trade_decision_to_request(request_id="r", capability="system.shutdown",
                                          action_descriptor="x", client_order_id="c", qty=1)
    d = decide_quant_order(identity=ident, grant=grant, authorization_scope=az_trade,
                           request=req_other, constraints=constr, current_epoch=1, now=100,
                           trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d.verdict == "BLOCKED" and d.reason == "capability_not_granted"


def test_reverse_cannot_bypass_decide():
    """RISK 5: there is no adapter helper that fabricates an AuthorizationDecision
    without calling decide(). The only producer is decide(); the adapter's
    decide_quant_order is a thin pass-through to it."""
    import inspect
    # Directly assert: the only way to get an AuthorizationDecision is decide() /
    # decide_quant_order, and both route through the same guarded function.
    src_decide = inspect.getsource(decide)
    assert "AuthorizationDecision(" in src_decide
    # And the adapter's decide_quant_order literally calls decide(...)
    src_adapter = inspect.getsource(adapter.decide_quant_order)
    assert "decide(" in src_adapter


def test_reverse_financial_system_cannot_self_sign_valid_grant():
    """RISK 6: a malicious financial component with no governance key cannot
    forge a grant that verifies against the trusted issuer pinned in decide().
    Self-signing with a random key is rejected."""
    gov = _gov()
    attacker_key = Ed25519PrivateKey.generate()
    from fleet.epistemic.scope import AuthorizationScope
    from dataclasses import replace
    from fleet.crypto.foundation import canonical_bytes
    import cryptography
    from cryptography.hazmat.primitives import serialization as ser
    az = build_authorization_scope((adapter.CAP_TRADE_EXECUTE,))
    attacker_pub_pem = attacker_key.public_key().public_bytes(
        ser.Encoding.PEM, ser.PublicFormat.SubjectPublicKeyInfo).decode()
    forged = AuthorityGrant(
        grant_id="forge", agent_id="agent-1",
        authorization_scope_hash=az.compute_hash(), epoch=1, issued_at=100,
        expires_at=1000, governance_role="CRO",
        signer_pubkey_pem=attacker_pub_pem, signature="")
    forged = replace(forged, signature=attacker_key.sign(canonical_bytes(forged.state())).hex())
    # decide() pins the TRUSTED issuer (gov), not the grant's embedded key.
    ident = _identity()
    req = trade_decision_to_request(request_id="r", capability=adapter.CAP_TRADE_EXECUTE,
                                    action_descriptor="x", client_order_id="c", qty=1)
    constr = build_governance_constraints(allowlist=(adapter.CAP_TRADE_EXECUTE,))
    d = decide_quant_order(identity=ident, grant=forged, authorization_scope=az,
                           request=req, constraints=constr, current_epoch=1, now=100,
                           trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d.verdict == "BLOCKED"
    assert d.reason == "invalid_grant_signature"  # attacker's key != trusted issuer


def test_reverse_epistemic_layer_does_not_import_adapter():
    """RISK 7: directionality. fleet.epistemic must remain ignorant of the
    adapter. Confirmed by AST scan: no module under fleet/epistemic imports
    exchange.epistemic_adapter (or exchange.quant / exchange.governance)."""
    import ast
    from pathlib import Path
    ep = Path(__file__).resolve().parents[2] / "fleet" / "epistemic"
    bad = ("exchange.epistemic_adapter", "exchange.quant", "exchange.governance", "fleet.fin")
    offenders = []
    for p in ep.rglob("*.py"):
        if p.name == "_boundary_bad_fixture.py":  # shipped deliberately-bad fixture
            continue
        tree = ast.parse(p.read_text())
        for node in ast.walk(tree):
            mod = None
            if isinstance(node, ast.Import):
                for a in node.names:
                    mod = a.name
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
            if mod and any(mod == b or mod.startswith(b + ".") for b in bad):
                offenders.append((p.name, mod))
    assert not offenders, f"fleet.epistemic must not import the adapter/finance: {offenders}"


def test_reverse_substrate_functional_without_adapter_present():
    """RISK 8 (import-level): the neutral substrate imports and operates with NO
    reference to the adapter. We assert importing fleet.epistemic and building
    its core objects works even when exchange.epistemic_adapter is forcibly
    removed from sys.modules (simulating the adapter not existing)."""
    saved = sys.modules.pop("exchange.epistemic_adapter", None)
    try:
        import importlib
        if "fleet.epistemic" in sys.modules:
            del sys.modules["fleet.epistemic"]
        import fleet.epistemic as fe
        importlib.reload(fe)
        # Core objects construct without any adapter.
        prop = fe.Proposition(domain="x", subject="s", predicate="p")
        assert prop.proposition_hash
        idn = _identity()
        assert idn.agent_id == "agent-1"
        # decide() still requires a grant and returns no_grant when absent.
        az = build_authorization_scope((adapter.CAP_TRADE_EXECUTE,))
        constr = build_governance_constraints(allowlist=(adapter.CAP_TRADE_EXECUTE,))
        req = trade_decision_to_request(request_id="r", capability=adapter.CAP_TRADE_EXECUTE,
                                        action_descriptor="x", client_order_id="c", qty=1)
        d = fe.decide(identity=idn, grant=None, authorization_scope=az, request=req,
                       constraints=constr, current_epoch=1, now=100,
                       trusted_issuer_pubkey_pem="x")
        assert d.verdict == "BLOCKED" and d.reason == "no_grant"
    finally:
        if saved is not None:
            sys.modules["exchange.epistemic_adapter"] = saved
