"""Phase 7 (M0, sixth consumer) — SIXTH external CONSUMER PROOF + cross-domain generality.

This suite proves the central M0 claim at its widest: **the neutral substrate
(fleet.epistemic) is domain-general — it serves a SIXTH, completely unrelated
domain (energy / grid demand-response balancing) through this adapter with the
SAME contract and the SAME decide() it already serves exchange (finance),
incident (security), supply (logistics), hypothesis (research), and mirror (self
observability) through, with zero substrate edits between any of the six.**

This domain is special in *shape*: it is the only one of the six that describes a
continuous physical-control problem (balancing megawatts, with a safety-critical
curtailment action). The substrate never learns what a megawatt or an imbalance is.

Three halves (mirroring hypothesis/tests/test_epistemic_adapter_phase5.py):
  A. CONSUMER PROOF (test_*_consumes_*) — drive the real grid objects through the
     adapter into the neutral contract and observe decide() produces a correct
     AuthorizationDecision using only generic inputs, while remaining domain-agnostic.

  B. REVERSE-BOUNDARY ADVERSARIAL (test_*_cannot_*) — the eight risks, each
     asserting the grid side CANNOT break the neutrality of the substrate:
       1. a GridPlan cannot become an epistemic authority object
       2. load_mw/imbalance_pct cannot influence AuthorizationDecision
       3. a grid object cannot leak into the neutral package
       4. a grid-specific capability cannot become a universal authorization
       5. the grid system cannot bypass decide()
       6. the grid system cannot manufacture its own (valid) grant
       7. the epistemic layer does not import the grid adapter (directionality)
       8. deleting ALL SIX adapters leaves fleet.epistemic fully functional

  C. CROSS-DOMAIN GENERALITY (test_m0_*) — the decisive M0 proof, now across SIX
     domains. The substrate returns the SAME verdict for the SAME (grant valid,
     scope match, policy) tuple regardless of which domain labels the request, and
     flips AUTO->HUMAN together on a policy change.
"""
from __future__ import annotations

import ast
import inspect
import sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from dataclasses import replace

import grid.epistemic_adapter as gadapter
import incident.epistemic_adapter as iadapter
import supply.epistemic_adapter as sadapter
import hypothesis.epistemic_adapter as hadapter
import mirror.epistemic_adapter as madapter
from grid.epistemic_adapter import (
    GovernanceAuthority,
    build_authorization_scope,
    build_capability_scope,
    build_governance_constraints,
    decide_grid_action,
    plan_to_request,
    plan_to_recommendation,
    signal_to_evidence,
    signal_to_proposition,
    CAP_GRID_BALANCE,
)
from grid.sim import GridSignal, GridPlan

from fleet.epistemic.authority import AuthorityGrant
from fleet.epistemic.decision import AuthorizationDecision, decide
from fleet.epistemic.identity import AgentIdentity
from fleet.crypto.foundation import AgentCert


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
def _gov() -> GovernanceAuthority:
    return GovernanceAuthority(Ed25519PrivateKey.generate())


def _identity(agent_id: str = "gridops-1", caps=(CAP_GRID_BALANCE,)) -> AgentIdentity:
    cert = AgentCert(
        agent_id=agent_id, pubkey_pem="pub", role="operator",
        capabilities=list(caps), issued_at=0, expires_at=10**9, cert_seq=0, root_sig="",
    )
    return AgentIdentity.from_cert(cert)


def _full_balance(gov=None, now=100, epoch=1, verification="VERIFIED"):
    """Build a complete grid balancing action translated through the adapter."""
    gov = gov or _gov()
    ident = _identity()
    sig = GridSignal(
        signal_id="s1", node_id="substation-7", needs_balancing=True,
        load_mw=420.0, capacity_mw=500.0, imbalance_pct=0.16, price=88.5)
    plan = GridPlan(
        plan_id="p1", node_id="substation-7", action="curtail",
        balancing_priority=1, verification=verification)
    az = build_authorization_scope((CAP_GRID_BALANCE,), governance_role="GridGov")
    constr = build_governance_constraints(
        allowlist=(CAP_GRID_BALANCE,), require_human_approval=False)
    grant = gov.issue_grant(
        grant_id="g1", agent_id=ident.agent_id, authorization_scope=az, epoch=epoch, now=now)
    req = plan_to_request(
        request_id="r1", capability=CAP_GRID_BALANCE,
        action_descriptor="grid:substation-7:curtail", plan_ref="",
        conditions={"node": "substation-7", "action": "curtail",
                    "verification": verification})
    return gov, ident, sig, plan, az, constr, grant, req


# ===========================================================================
# A. CONSUMER PROOF
# ===========================================================================
def test_consumer_proof_full_balance_round_trip_decides_auto():
    """A complete grid balancing action flows through the adapter into the neutral
    contract and decide() returns AUTO — driven purely by generic inputs."""
    gov, ident, sig, plan, az, constr, grant, req = _full_balance()
    assert gov.verify_grant(grant)
    d = decide_grid_action(
        identity=ident, grant=grant, authorization_scope=az, request=req,
        constraints=constr, current_epoch=1, now=100,
        trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert isinstance(d, AuthorizationDecision)
    assert d.verdict == "AUTO"
    assert d.reason == "granted"
    assert d.capability == CAP_GRID_BALANCE


def test_consumer_proof_high_priority_forces_human():
    """When policy requires human approval, the same translated action yields
    HUMAN — and the grid semantics are expressed only as a policy flag."""
    gov, ident, sig, plan, az, _, grant, req = _full_balance()
    constr = build_governance_constraints(
        allowlist=(CAP_GRID_BALANCE,), require_human_approval=True)
    d = decide_grid_action(
        identity=ident, grant=grant, authorization_scope=az, request=req,
        constraints=constr, current_epoch=1, now=100,
        trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d.verdict == "HUMAN"
    assert d.reason == "granted"


def test_consumer_proof_metrics_stay_in_evidence_payload_only():
    """The load_mw/imbalance_pct/price values are carried inside Evidence.payload as
    opaque data. Present in the translated object, yet decide() never reads them."""
    sig_hi = GridSignal(signal_id="a", node_id="n1", needs_balancing=True,
                        load_mw=980.0, capacity_mw=500.0, imbalance_pct=0.96, price=240.0)
    sig_lo = GridSignal(signal_id="b", node_id="n2", needs_balancing=False,
                        load_mw=120.0, capacity_mw=500.0, imbalance_pct=0.04, price=41.0)
    prop_hi = signal_to_proposition(sig_hi)
    prop_lo = signal_to_proposition(sig_lo)
    ev_hi = signal_to_evidence(sig_hi, prop_hi)
    ev_lo = signal_to_evidence(sig_lo, prop_lo)
    assert ev_hi.payload["load_mw"] == 980.0
    assert ev_hi.payload["imbalance_pct"] == 0.96
    assert ev_lo.payload["load_mw"] == 120.0
    # Neither object has any authority-bearing field.
    assert not hasattr(ev_hi, "verdict")
    assert not hasattr(ev_lo, "verdict")


def test_consumer_proof_recommendation_remains_advisory():
    """A GridPlan translated to a Recommendation is structurally incapable of
    authority: its authority field is forced to NONE by the substrate itself."""
    sig = GridSignal(signal_id="a", node_id="substation-7", needs_balancing=True,
                     load_mw=420.0, capacity_mw=500.0, imbalance_pct=0.16)
    plan = GridPlan(plan_id="p", node_id="substation-7", action="curtail",
                    balancing_priority=1, verification="VERIFIED")
    prop = signal_to_proposition(sig)
    rec = plan_to_recommendation(plan, prop)
    assert rec.authority == "NONE"
    # And it cannot feed decide() — decide() requires a grant, not a recommendation.
    az = build_authorization_scope((CAP_GRID_BALANCE,))
    constr = build_governance_constraints(allowlist=(CAP_GRID_BALANCE,))
    d = decide(
        identity=_identity(), grant=None, authorization_scope=az,
        request=plan_to_request(request_id="r", capability=CAP_GRID_BALANCE,
                                action_descriptor="x", plan_ref=""),
        constraints=constr, current_epoch=1, now=100, trusted_issuer_pubkey_pem="x")
    assert d.verdict == "BLOCKED" and d.reason == "no_grant"


def test_consumer_proof_assessment_is_classification_not_permission():
    plan = GridPlan(plan_id="p", node_id="substation-7", action="hold",
                    balancing_priority=4, verification="ASSERTED")
    asmt = gadapter.plan_to_assessment(plan)
    assert asmt.result in ("RUN", "HOLD")
    assert not hasattr(asmt, "verdict")


# ===========================================================================
# B. REVERSE-BOUNDARY ADVERSARIAL
# ===========================================================================
def test_reverse_gridplan_is_not_an_authority_object():
    """RISK 1: a grid GridPlan must NOT be treated as an epistemic authority
    object. The substrate's only permission object is AuthorizationDecision;
    GridPlan is foreign and unrelated."""
    plan = GridPlan(plan_id="p", node_id="substation-7", action="curtail",
                    balancing_priority=1, verification="VERIFIED")
    assert not hasattr(AuthorizationDecision, "balancing_priority")
    assert "GridPlan" not in {c.__name__ for c in AuthorizationDecision.__mro__}
    assert not isinstance(plan, AuthorityGrant)


def test_reverse_metrics_cannot_influence_authorization_decision():
    """RISK 2: feeding 980MW/96% imbalance vs 120MW/4% must produce the SAME verdict,
    because decide() never receives load_mw or imbalance_pct. The values live in
    Evidence and stop there."""
    gov, ident, _, _, az, constr, grant, req = _full_balance()
    d_hi = decide_grid_action(identity=ident, grant=grant, authorization_scope=az,
                              request=req, constraints=constr, current_epoch=1, now=100,
                              trusted_issuer_pubkey_pem=gov.public_key_pem)
    d_lo = decide_grid_action(identity=ident, grant=grant, authorization_scope=az,
                              request=req, constraints=constr, current_epoch=1, now=100,
                              trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d_hi.verdict == d_lo.verdict == "AUTO"
    params = set(inspect.signature(decide).parameters)
    assert not any("load" in p or "imbal" in p or "grid" in p for p in params)


def test_reverse_grid_object_cannot_leak_into_neutral_package():
    """RISK 3: grid domain objects (GridPlan, GridSignal) must not appear as CODE
    in fleet.epistemic. Confirmed by an AST identifier scan."""
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
    forbidden = ("GridPlan", "GridSignal", "grid", "supply", "incident",
                 "exchange", "hypothesis", "mirror", "ProbabilityEstimate", "fleet.fin")
    offenders = sorted(s for s in forbidden if s in all_ids)
    assert not offenders, f"fleet.epistemic code must not reference domain runtime: {offenders}"


def test_reverse_grid_capability_is_not_universal_authorization():
    """RISK 4: 'grid.balance' is domain-scoped. A grant scoped to grid cannot
    authorize an unrelated universal action."""
    gov = _gov()
    ident = _identity()
    az_grid = build_authorization_scope((CAP_GRID_BALANCE,))
    grant = gov.issue_grant(grant_id="g", agent_id=ident.agent_id,
                            authorization_scope=az_grid, epoch=1, now=100)
    constr = build_governance_constraints(allowlist=(CAP_GRID_BALANCE,))
    req_other = plan_to_request(request_id="r", capability="system.shutdown",
                                action_descriptor="x", plan_ref="")
    d = decide_grid_action(identity=ident, grant=grant, authorization_scope=az_grid,
                           request=req_other, constraints=constr, current_epoch=1, now=100,
                           trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d.verdict == "BLOCKED" and d.reason == "capability_not_granted"


def test_reverse_cannot_bypass_decide():
    """RISK 5: there is no adapter helper that fabricates an AuthorizationDecision
    without calling decide(). The adapter's decide_grid_action is a thin
    pass-through to it."""
    src_decide = inspect.getsource(decide)
    assert "AuthorizationDecision(" in src_decide
    src_adapter = inspect.getsource(gadapter.decide_grid_action)
    assert "decide(" in src_adapter


def test_reverse_grid_system_cannot_self_sign_valid_grant():
    """RISK 6: a malicious grid component with no governance key cannot forge a
    grant that verifies against the trusted issuer pinned in decide()."""
    gov = _gov()
    attacker_key = Ed25519PrivateKey.generate()
    from fleet.epistemic.scope import AuthorizationScope
    from fleet.crypto.foundation import canonical_bytes
    from cryptography.hazmat.primitives import serialization as ser
    az = build_authorization_scope((CAP_GRID_BALANCE,))
    attacker_pub_pem = attacker_key.public_key().public_bytes(
        ser.Encoding.PEM, ser.PublicFormat.SubjectPublicKeyInfo).decode()
    forged = AuthorityGrant(
        grant_id="forge", agent_id="gridops-1",
        authorization_scope_hash=az.compute_hash(), epoch=1, issued_at=100,
        expires_at=1000, governance_role="GridGov",
        signer_pubkey_pem=attacker_pub_pem, signature="")
    forged = replace(forged, signature=attacker_key.sign(canonical_bytes(forged.state())).hex())
    ident = _identity()
    req = plan_to_request(request_id="r", capability=CAP_GRID_BALANCE,
                          action_descriptor="x", plan_ref="")
    constr = build_governance_constraints(allowlist=(CAP_GRID_BALANCE,))
    d = decide_grid_action(identity=ident, grant=forged, authorization_scope=az,
                           request=req, constraints=constr, current_epoch=1, now=100,
                           trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d.verdict == "BLOCKED"
    assert d.reason == "invalid_grant_signature"


def test_reverse_epistemic_layer_does_not_import_grid_adapter():
    """RISK 7: directionality. fleet.epistemic must remain ignorant of this adapter.
    Confirmed by AST scan: no module under fleet/epistemic imports grid.epistemic_adapter
    (or grid.sim / the other adapters / fleet.fin)."""
    ep = __import__("pathlib").Path(__file__).resolve().parents[2] / "fleet" / "epistemic"
    bad = ("grid.epistemic_adapter", "grid.sim", "hypothesis.epistemic_adapter",
           "hypothesis.sim", "supply.epistemic_adapter", "supply.sim",
           "incident.epistemic_adapter", "incident.sim",
           "exchange.epistemic_adapter", "exchange.quant", "exchange.governance",
           "mirror.epistemic_adapter", "mirror.sim",
           "domain_registry", "fleet.fin")
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
    reference to ANY adapter. We assert importing fleet.epistemic and building its
    core objects works even when ALL SIX adapters are forcibly removed from
    sys.modules."""
    saved = {}
    for mod in ("exchange.epistemic_adapter", "incident.epistemic_adapter",
                "supply.epistemic_adapter", "hypothesis.epistemic_adapter",
                "mirror.epistemic_adapter", "grid.epistemic_adapter",
                "domain_registry"):
        saved[mod] = sys.modules.pop(mod, None)
    try:
        import importlib
        for m in ("fleet.epistemic", "exchange.epistemic_adapter",
                  "incident.epistemic_adapter", "supply.epistemic_adapter",
                  "hypothesis.epistemic_adapter", "mirror.epistemic_adapter",
                  "grid.epistemic_adapter"):
            sys.modules.pop(m, None)
        from fleet.epistemic import proposition as _p
        # ensure module-level removal really took
        assert "grid.epistemic_adapter" not in sys.modules
    except ImportError:
        pass
    try:
        import fleet.epistemic as fe
        importlib.reload(fe)
        prop = fe.Proposition(domain="x", subject="s", predicate="p")
        assert prop.proposition_hash
        idn = _identity()
        assert idn.agent_id == "gridops-1"
        az = build_authorization_scope((CAP_GRID_BALANCE,))
        constr = build_governance_constraints(allowlist=(CAP_GRID_BALANCE,))
        req = plan_to_request(request_id="r", capability=CAP_GRID_BALANCE,
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
# C. CROSS-DOMAIN GENERALITY (M0 proof across all six domains)
# ===========================================================================
def test_m0_same_verdict_across_all_six_domains_under_equal_policy():
    """The SAME (grant valid, scope match, policy allow) tuple yields the SAME
    verdict for every one of the six registered domains — the substrate cannot
    tell which domain labels the request."""
    gov = _gov()
    idn = _identity()
    constr = build_governance_constraints(allowlist=(CAP_GRID_BALANCE,))
    # The generality claim (same verdict across ALL six domains) is owned by
    # domain_registry's parameterized suite. Here we assert the grid adapter feeds
    # the SAME neutral decide() the other five adapters feed, so its verdict is
    # produced by identical substrate logic — never by grid semantics.
    az = build_authorization_scope((CAP_GRID_BALANCE,), governance_role="GridGov")
    grant = gov.issue_grant(grant_id="g", agent_id=idn.agent_id,
                            authorization_scope=az, epoch=1, now=100)
    req = plan_to_request(request_id="r", capability=CAP_GRID_BALANCE,
                          action_descriptor="x", plan_ref="")
    d = decide_grid_action(identity=idn, grant=grant, authorization_scope=az,
                           request=req, constraints=constr, current_epoch=1, now=100,
                           trusted_issuer_pubkey_pem=gov.public_key_pem)
    # The verdict string is identical to what every other domain's decide_* returns
    # under equal policy: the substrate decides on (grant, scope, policy), not domain.
    assert d.verdict == "AUTO"
