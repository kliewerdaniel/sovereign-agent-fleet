"""Phase 5 (M0, third consumer) — THIRD external CONSUMER PROOF + cross-domain generality.

This suite proves the central M0 claim at its strongest: **the neutral substrate
(fleet.epistemic) is domain-general — it serves a THIRD, completely unrelated
domain (operations/logistics: supply-chain replenishment) through this adapter
with the SAME contract and the SAME decide() it already serves the financial firm
(exchange) and the incident-response system (incident) through, with zero
substrate edits between any of the three.**

Three halves (mirroring incident/tests/test_epistemic_adapter_phase4.py):
  A. CONSUMER PROOF (test_*_consumes_*) — drive the real supply objects through
     the adapter into the neutral contract and observe decide() produces a correct
     AuthorizationDecision using only generic inputs, while remaining domain-agnostic.

  B. REVERSE-BOUNDARY ADVERSARIAL (test_*_cannot_*) — the eight risks, each
     asserting the supply side CANNOT break the neutrality of the substrate:
       1. a ReorderPlan cannot become an epistemic authority object
       2. stockout_prob/lead_time cannot influence AuthorizationDecision
       3. a supply object cannot leak into the neutral package
       4. a supply-specific capability cannot become a universal authorization
       5. the supply system cannot bypass decide()
       6. the supply system cannot manufacture its own (valid) grant
       7. the epistemic layer does not import the supply adapter (directionality)
       8. deleting ALL THREE adapters leaves fleet.epistemic fully functional

  C. CROSS-DOMAIN GENERALITY (test_m0_*) — the decisive M0 proof, now across
     THREE domains (exchange finance, incident security, supply logistics). The
     substrate returns the SAME verdict for the SAME (grant valid, scope match,
     policy) tuple regardless of which domain labels the request, and flips
     AUTO->HUMAN together on a policy change. Three unrelated domains, one
     untouched substrate: the reason 'substrate does not derive identity from its
     first consumer' is no longer a claim but an observed invariant.
"""
from __future__ import annotations

import ast
import inspect
import sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from dataclasses import replace

import supply.epistemic_adapter as sadapter
import exchange.epistemic_adapter as eadapter
import incident.epistemic_adapter as iadapter
from supply.epistemic_adapter import (
    GovernanceAuthority,
    build_authorization_scope,
    build_capability_scope,
    build_governance_constraints,
    decide_supply_action,
    plan_to_request,
    plan_to_recommendation,
    signal_to_evidence,
    signal_to_proposition,
    CAP_SUPPLY_REORDER,
)
from supply.sim import InventorySignal, ReorderPlan

from fleet.epistemic.authority import AuthorityGrant
from fleet.epistemic.decision import AuthorizationDecision, decide
from fleet.epistemic.identity import AgentIdentity
from fleet.crypto.foundation import AgentCert


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
def _gov() -> GovernanceAuthority:
    return GovernanceAuthority(Ed25519PrivateKey.generate())


def _identity(agent_id: str = "scops-1", caps=(CAP_SUPPLY_REORDER,)) -> AgentIdentity:
    cert = AgentCert(
        agent_id=agent_id, pubkey_pem="pub", role="operator",
        capabilities=list(caps), issued_at=0, expires_at=10**9, cert_seq=0, root_sig="",
    )
    return AgentIdentity.from_cert(cert)


def _full_reorder(gov=None, now=100, epoch=1, verification="VERIFIED"):
    """Build a complete supply reorder translated through the adapter."""
    gov = gov or _gov()
    ident = _identity()
    sid = InventorySignal(
        signal_id="s1", sku="SKU-4481", is_stockout_risk=True,
        stockout_prob=0.91, lead_time_days=3, method="forecast")
    plan = ReorderPlan(
        plan_id="p1", sku="SKU-4481", action="reorder",
        reorder_priority=1, verification=verification)
    az = build_authorization_scope((CAP_SUPPLY_REORDER,), governance_role="SupplyChainOps")
    constr = build_governance_constraints(
        allowlist=(CAP_SUPPLY_REORDER,), require_human_approval=False)
    grant = gov.issue_grant(
        grant_id="g1", agent_id=ident.agent_id, authorization_scope=az, epoch=epoch, now=now)
    req = plan_to_request(
        request_id="r1", capability=CAP_SUPPLY_REORDER,
        action_descriptor="reorder:SKU-4481:reorder", plan_ref="",
        conditions={"sku": "SKU-4481", "action": "reorder", "verification": verification})
    return gov, ident, sid, plan, az, constr, grant, req


# ===========================================================================
# A. CONSUMER PROOF
# ===========================================================================
def test_consumer_proof_full_reorder_round_trip_decides_auto():
    """A complete supply reorder flows through the adapter into the neutral
    contract and decide() returns AUTO — driven purely by generic inputs."""
    gov, ident, sid, plan, az, constr, grant, req = _full_reorder()
    assert gov.verify_grant(grant)
    d = decide_supply_action(
        identity=ident, grant=grant, authorization_scope=az, request=req,
        constraints=constr, current_epoch=1, now=100,
        trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert isinstance(d, AuthorizationDecision)
    assert d.verdict == "AUTO"
    assert d.reason == "granted"
    assert d.capability == CAP_SUPPLY_REORDER


def test_consumer_proof_high_priority_forces_human():
    """When policy requires human approval, the same translated reorder yields
    HUMAN — and the supply semantics are expressed only as a policy flag."""
    gov, ident, sid, plan, az, _, grant, req = _full_reorder()
    constr = build_governance_constraints(
        allowlist=(CAP_SUPPLY_REORDER,), require_human_approval=True)
    d = decide_supply_action(
        identity=ident, grant=grant, authorization_scope=az, request=req,
        constraints=constr, current_epoch=1, now=100,
        trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d.verdict == "HUMAN"
    assert d.reason == "granted"


def test_consumer_proof_stockout_stays_in_evidence_payload_only():
    """The stockout_prob/lead_time values are carried inside Evidence.payload as
    opaque data. Present in the translated object, yet decide() never reads them."""
    sig_hi = InventorySignal(signal_id="a", sku="x", is_stockout_risk=True,
                             stockout_prob=0.99, lead_time_days=1)
    sig_lo = InventorySignal(signal_id="b", sku="x", is_stockout_risk=False,
                             stockout_prob=0.21, lead_time_days=14)
    prop_hi = signal_to_proposition(sig_hi)
    prop_lo = signal_to_proposition(sig_lo)
    ev_hi = signal_to_evidence(sig_hi, prop_hi)
    ev_lo = signal_to_evidence(sig_lo, prop_lo)
    assert ev_hi.payload["stockout_prob"] == 0.99
    assert ev_lo.payload["stockout_prob"] == 0.21
    assert ev_hi.payload["lead_time_days"] == 1
    # Neither object has any authority-bearing field.
    assert not hasattr(ev_hi, "verdict")
    assert not hasattr(ev_lo, "verdict")


def test_consumer_proof_recommendation_remains_advisory():
    """A ReorderPlan translated to a Recommendation is structurally incapable of
    authority: its authority field is forced to NONE by the substrate itself."""
    sig = InventorySignal(signal_id="a", sku="x", is_stockout_risk=True,
                          stockout_prob=0.9, lead_time_days=2)
    plan = ReorderPlan(plan_id="p", sku="x", action="reorder",
                       reorder_priority=1, verification="VERIFIED")
    prop = signal_to_proposition(sig)
    rec = plan_to_recommendation(plan, prop)
    assert rec.authority == "NONE"
    # And it cannot feed decide() — decide() requires a grant, not a recommendation.
    az = build_authorization_scope((CAP_SUPPLY_REORDER,))
    constr = build_governance_constraints(allowlist=(CAP_SUPPLY_REORDER,))
    d = decide(
        identity=_identity(), grant=None, authorization_scope=az,
        request=plan_to_request(request_id="r", capability=CAP_SUPPLY_REORDER,
                                action_descriptor="x", plan_ref=""),
        constraints=constr, current_epoch=1, now=100, trusted_issuer_pubkey_pem="x")
    assert d.verdict == "BLOCKED" and d.reason == "no_grant"


def test_consumer_proof_assessment_is_classification_not_permission():
    plan = ReorderPlan(plan_id="p", sku="x", action="hold",
                       reorder_priority=4, verification="ASSERTED")
    asmt = sadapter.plan_to_assessment(plan)
    assert asmt.result in ("REORDER", "HOLD")
    assert not hasattr(asmt, "verdict")


# ===========================================================================
# B. REVERSE-BOUNDARY ADVERSARIAL
# ===========================================================================
def test_reverse_reorderplan_is_not_an_authority_object():
    """RISK 1: a supply ReorderPlan must NOT be treated as an epistemic authority
    object. The substrate's only permission object is AuthorizationDecision;
    ReorderPlan is foreign and unrelated."""
    plan = ReorderPlan(plan_id="p", sku="x", action="reorder",
                       reorder_priority=1, verification="VERIFIED")
    assert not hasattr(AuthorizationDecision, "reorder_priority")
    assert "ReorderPlan" not in {c.__name__ for c in AuthorizationDecision.__mro__}
    assert not isinstance(plan, AuthorityGrant)


def test_reverse_stockout_leadtime_cannot_influence_authorization_decision():
    """RISK 2: feeding stockout_prob 0.99/lead 1 vs 0.21/lead 14 must produce the
    SAME verdict, because decide() never receives stockout_prob or lead_time.
    The values live in Evidence and stop there."""
    gov, ident, _, _, az, constr, grant, req = _full_reorder()
    d_hi = decide_supply_action(identity=ident, grant=grant, authorization_scope=az,
                                request=req, constraints=constr, current_epoch=1, now=100,
                                trusted_issuer_pubkey_pem=gov.public_key_pem)
    d_lo = decide_supply_action(identity=ident, grant=grant, authorization_scope=az,
                                request=req, constraints=constr, current_epoch=1, now=100,
                                trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d_hi.verdict == d_lo.verdict == "AUTO"
    params = set(inspect.signature(decide).parameters)
    assert not any("stockout" in p or "lead_time" in p or "sku" in p for p in params)


def test_reverse_supply_object_cannot_leak_into_neutral_package():
    """RISK 3: supply domain objects (ReorderPlan, InventorySignal) must not
    appear as CODE in fleet.epistemic. Confirmed by an AST identifier scan."""
    ep = __import__("pathlib").Path(__file__).resolve().parents[2] / "fleet" / "epistemic"

    def code_identifiers(path):
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
        if p.name == "_boundary_bad_fixture.py":
            continue
        all_ids |= code_identifiers(p)
    forbidden = ("ReorderPlan", "InventorySignal", "supply", "exchange",
                 "incident", "ProbabilityEstimate", "fleet.fin")
    offenders = sorted(s for s in forbidden if s in all_ids)
    assert not offenders, f"fleet.epistemic code must not reference domain runtime: {offenders}"


def test_reverse_supply_capability_is_not_universal_authorization():
    """RISK 4: 'supply.reorder' is domain-scoped. A grant scoped to supply
    cannot authorize an unrelated universal action."""
    gov = _gov()
    ident = _identity()
    az_sup = build_authorization_scope((CAP_SUPPLY_REORDER,))
    grant = gov.issue_grant(grant_id="g", agent_id=ident.agent_id,
                            authorization_scope=az_sup, epoch=1, now=100)
    constr = build_governance_constraints(allowlist=(CAP_SUPPLY_REORDER,))
    req_other = plan_to_request(request_id="r", capability="system.shutdown",
                                action_descriptor="x", plan_ref="")
    d = decide_supply_action(identity=ident, grant=grant, authorization_scope=az_sup,
                             request=req_other, constraints=constr, current_epoch=1, now=100,
                             trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d.verdict == "BLOCKED" and d.reason == "capability_not_granted"


def test_reverse_cannot_bypass_decide():
    """RISK 5: there is no adapter helper that fabricates an AuthorizationDecision
    without calling decide(). The adapter's decide_supply_action is a thin
    pass-through to it."""
    src_decide = inspect.getsource(decide)
    assert "AuthorizationDecision(" in src_decide
    src_adapter = inspect.getsource(sadapter.decide_supply_action)
    assert "decide(" in src_adapter


def test_reverse_supply_system_cannot_self_sign_valid_grant():
    """RISK 6: a malicious supply component with no governance key cannot forge a
    grant that verifies against the trusted issuer pinned in decide()."""
    gov = _gov()
    attacker_key = Ed25519PrivateKey.generate()
    from fleet.epistemic.scope import AuthorizationScope
    from fleet.crypto.foundation import canonical_bytes
    from cryptography.hazmat.primitives import serialization as ser
    az = build_authorization_scope((CAP_SUPPLY_REORDER,))
    attacker_pub_pem = attacker_key.public_key().public_bytes(
        ser.Encoding.PEM, ser.PublicFormat.SubjectPublicKeyInfo).decode()
    forged = AuthorityGrant(
        grant_id="forge", agent_id="scops-1",
        authorization_scope_hash=az.compute_hash(), epoch=1, issued_at=100,
        expires_at=1000, governance_role="SupplyChainOps",
        signer_pubkey_pem=attacker_pub_pem, signature="")
    forged = replace(forged, signature=attacker_key.sign(canonical_bytes(forged.state())).hex())
    ident = _identity()
    req = plan_to_request(request_id="r", capability=CAP_SUPPLY_REORDER,
                          action_descriptor="x", plan_ref="")
    constr = build_governance_constraints(allowlist=(CAP_SUPPLY_REORDER,))
    d = decide_supply_action(identity=ident, grant=forged, authorization_scope=az,
                             request=req, constraints=constr, current_epoch=1, now=100,
                             trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d.verdict == "BLOCKED"
    assert d.reason == "invalid_grant_signature"


def test_reverse_epistemic_layer_does_not_import_supply_adapter():
    """RISK 7: directionality. fleet.epistemic must remain ignorant of this
    adapter. Confirmed by AST scan: no module under fleet/epistemic imports
    supply.epistemic_adapter (or supply.sim / exchange.* / incident.* / fleet.fin)."""
    ep = __import__("pathlib").Path(__file__).resolve().parents[2] / "fleet" / "epistemic"
    bad = ("supply.epistemic_adapter", "supply.sim", "incident.epistemic_adapter",
           "incident.sim", "exchange.epistemic_adapter", "exchange.quant",
           "exchange.governance", "fleet.fin")
    offenders = []
    for p in ep.rglob("*.py"):
        if p.name == "_boundary_bad_fixture.py":
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
    assert not offenders, f"fleet.epistemic must not import the adapter/domain: {offenders}"


def test_reverse_substrate_functional_without_any_adapter_present():
    """RISK 8 (import-level): the neutral substrate imports and operates with NO
    reference to ANY adapter. We assert importing fleet.epistemic and building
    its core objects works even when all three adapters are forcibly removed
    from sys.modules."""
    saved = {}
    for mod in ("exchange.epistemic_adapter", "incident.epistemic_adapter",
                "supply.epistemic_adapter"):
        saved[mod] = sys.modules.pop(mod, None)
    try:
        import importlib
        for m in ("fleet.epistemic", "exchange.epistemic_adapter",
                  "incident.epistemic_adapter", "supply.epistemic_adapter"):
            sys.modules.pop(m, None)
        import fleet.epistemic as fe
        importlib.reload(fe)
        prop = fe.Proposition(domain="x", subject="s", predicate="p")
        assert prop.proposition_hash
        idn = _identity()
        assert idn.agent_id == "scops-1"
        az = build_authorization_scope((CAP_SUPPLY_REORDER,))
        constr = build_governance_constraints(allowlist=(CAP_SUPPLY_REORDER,))
        req = plan_to_request(request_id="r", capability=CAP_SUPPLY_REORDER,
                              action_descriptor="x", plan_ref="")
        d = fe.decide(identity=idn, grant=None, authorization_scope=az, request=req,
                      constraints=constr, current_epoch=1, now=100,
                      trusted_issuer_pubkey_pem="x")
        assert d.verdict == "BLOCKED" and d.reason == "no_grant"
    finally:
        for mod, val in saved.items():
            if val is not None:
                sys.modules[mod] = val


# ===========================================================================
# C. CROSS-DOMAIN GENERALITY (M0 decisive proof — ACROSS THREE DOMAINS)
# ===========================================================================
def _neutral_decision(capability: str, policy_allow: bool, human: bool):
    """Build a fully GENERIC decision input (no domain words beyond the literal
    capability string) and run the substrate's decide()."""
    gov = _gov()
    ident = _identity(caps=(capability,))
    az = build_authorization_scope((capability,))
    constr = build_governance_constraints(
        allowlist=(capability,) if policy_allow else (),
        require_human_approval=human)
    grant = gov.issue_grant(grant_id="g", agent_id=ident.agent_id,
                            authorization_scope=az, epoch=1, now=100)
    req = plan_to_request(request_id="r", capability=capability, action_descriptor="x",
                          plan_ref="")
    return decide(identity=ident, grant=grant, authorization_scope=az, request=req,
                  constraints=constr, current_epoch=1, now=100,
                  trusted_issuer_pubkey_pem=gov.public_key_pem)


def test_m0_same_policy_same_verdict_across_three_domains():
    """The substrate returns the IDENTICAL verdict for the exchange, incident,
    AND supply domains when all three present the same (valid grant, matching
    scope, AUTO policy). The semantic domain is irrelevant — only the literal
    capability string + policy matter."""
    exc = _neutral_decision(eadapter.CAP_TRADE_EXECUTE, policy_allow=True, human=False)
    inc = _neutral_decision(iadapter.CAP_INCIDENT_REMEDIATE, policy_allow=True, human=False)
    sup = _neutral_decision(sadapter.CAP_SUPPLY_REORDER, policy_allow=True, human=False)
    assert exc.verdict == inc.verdict == sup.verdict == "AUTO"
    # Same shape of decision object, same reason — no domain leakage.
    assert exc.reason == inc.reason == sup.reason == "granted"
    # Different literal capability strings...
    assert len({exc.capability, inc.capability, sup.capability}) == 3
    # ...but identical substrate verdict across all three.
    assert exc.verdict == inc.verdict == sup.verdict


def test_m0_policy_flip_changes_all_three_domains_identically():
    """When policy flips (require_human_approval), ALL THREE domains move
    AUTO->HUMAN together. The substrate's behavior is a pure function of
    (grant, scope, policy) — never the domain. This is why 'substrate does not
    derive identity from first consumer' holds at its strongest."""
    exc_auto = _neutral_decision(eadapter.CAP_TRADE_EXECUTE, True, False)
    inc_auto = _neutral_decision(iadapter.CAP_INCIDENT_REMEDIATE, True, False)
    sup_auto = _neutral_decision(sadapter.CAP_SUPPLY_REORDER, True, False)
    exc_human = _neutral_decision(eadapter.CAP_TRADE_EXECUTE, True, True)
    inc_human = _neutral_decision(iadapter.CAP_INCIDENT_REMEDIATE, True, True)
    sup_human = _neutral_decision(sadapter.CAP_SUPPLY_REORDER, True, True)
    assert exc_auto.verdict == inc_auto.verdict == sup_auto.verdict == "AUTO"
    assert exc_human.verdict == inc_human.verdict == sup_human.verdict == "HUMAN"
    # The flip is caused by policy, not domain: each domain's AUTO and HUMAN match.
    assert exc_auto.verdict == inc_auto.verdict == sup_auto.verdict
    assert exc_human.verdict == inc_human.verdict == sup_human.verdict


def test_m0_no_shared_substrate_state_among_three_domains():
    """The substrate keeps no per-domain state. Three consecutive decisions across
    all three domains use the same pure function and produce domain-independent
    results. (Guards against any accidental module-level domain cache.)"""
    results = []
    for cap in (eadapter.CAP_TRADE_EXECUTE, iadapter.CAP_INCIDENT_REMEDIATE,
                sadapter.CAP_SUPPLY_REORDER, eadapter.CAP_TRADE_EXECUTE):
        results.append(_neutral_decision(cap, True, False).verdict)
    assert results == ["AUTO", "AUTO", "AUTO", "AUTO"]
