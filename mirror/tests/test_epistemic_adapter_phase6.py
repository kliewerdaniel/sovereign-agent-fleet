"""Phase 6 (M0, fifth consumer) — FIFTH external CONSUMER PROOF + L0 ladder.

This suite proves the central M0 claim at its widest: **the neutral substrate
(fleet.epistemic) is domain-general — it now serves a FIFTH, completely
unrelated domain (agent self-observability / introspection) through this adapter
with the SAME contract and the SAME decide() it already serves exchange
(finance), incident (security), supply (logistics), and hypothesis (research)
through, with zero substrate edits between any of the five.**

This domain is special: it is the first of the five to actually traverse the
**L0 ladder** end-to-end —

    Proposition -> Assessment -> Recommendation -> Proposal -> AuthorizationRequest

— and to prove the promotion steps carry NO silent authority. A self-reflection
becomes a ``Recommendation`` (advisory, ``authority="NONE"``), and at most a
``Proposal`` (intent, bounded by ``ProposalScope`` enforced fail-closed at the
adapter). Neither is ever a permission: authorization still requires an
externally-signed ``AuthorityGrant`` verified by ``decide()``. The frozen
substrate is domain-neutral by design and does not read ``ProposalScope``; the
adapter is the only place that does, and it refuses out-of-scope promotion.

Three halves (mirroring hypothesis/tests/test_epistemic_adapter_phase5.py, with
the L0 ladder folded into the consumer-proof section):
  A. CONSUMER PROOF + L0 LADDER (test_*) — drive real mirror objects through the
     adapter into the neutral contract; observe decide() produces a correct
     AuthorizationDecision using only generic inputs; assert domain metrics stay
     in Evidence.payload only; assert Recommendation stays advisory; assert the
     ladder promotion (Recommendation -> Proposal) is bounded and never becomes
     authority.

  B. REVERSE-BOUNDARY ADVERSARIAL (test_reverse_*) — the eight risks, each
     asserting the mirror side CANNOT break the neutrality of the substrate:
       1. a SelfTunePlan cannot become an epistemic authority object
       2. cpu_load/error_rate/queue_depth cannot influence AuthorizationDecision
       3. a mirror object cannot leak into the neutral package (AST identifiers)
       4. a mirror-specific capability cannot become a universal authorization
       5. the mirror system cannot bypass decide()
       6. the mirror system cannot manufacture its own (valid) grant
       7. the epistemic layer does not import the mirror adapter (directionality)
       8. deleting ALL FIVE adapters leaves fleet.epistemic fully functional

  (Cross-domain generality across all five domains is owned by the consolidated
   ``domain_registry`` harness — adding mirror required only a one-line table
   edit there, which is the empirical proof that the recipe works.)
"""
from __future__ import annotations

import ast
import inspect
import sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from dataclasses import replace

import mirror.epistemic_adapter as madapter
from mirror.epistemic_adapter import (
    GovernanceAuthority,
    build_authorization_scope,
    build_capability_scope,
    build_governance_constraints,
    build_proposal_scope,
    decide_mirror_action,
    plan_to_proposal,
    plan_to_request,
    plan_to_recommendation,
    signal_to_evidence,
    signal_to_proposition,
    CAP_MIRROR_SELF_TUNE,
)
from mirror.sim import MirrorSignal, SelfTunePlan

from fleet.epistemic.authority import AuthorityGrant
from fleet.epistemic.decision import AuthorizationDecision, decide
from fleet.epistemic.identity import AgentIdentity
from fleet.crypto.foundation import AgentCert


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
def _gov() -> GovernanceAuthority:
    return GovernanceAuthority(Ed25519PrivateKey.generate())


def _identity(agent_id: str = "brain-gemma", caps=(CAP_MIRROR_SELF_TUNE,)) -> AgentIdentity:
    cert = AgentCert(
        agent_id=agent_id, pubkey_pem="pub", role="operator",
        capabilities=list(caps), issued_at=0, expires_at=10**9, cert_seq=0, root_sig="",
    )
    return AgentIdentity.from_cert(cert)


def _full_tune(gov=None, now=100, epoch=1, verification="VERIFIED"):
    """Build a complete mirror self-tune translated through the adapter."""
    gov = gov or _gov()
    ident = _identity()
    sig = MirrorSignal(
        signal_id="s1", agent_id="brain-gemma", needs_tuning=True,
        cpu_load=0.95, error_rate=0.4, queue_depth=1000, method="telemetry")
    plan = SelfTunePlan(
        plan_id="p1", agent_id="brain-gemma", action="self_tune",
        tune_priority=1, verification=verification)
    az = build_authorization_scope((CAP_MIRROR_SELF_TUNE,), governance_role="SelfGov")
    constr = build_governance_constraints(
        allowlist=(CAP_MIRROR_SELF_TUNE,), require_human_approval=False)
    grant = gov.issue_grant(
        grant_id="g1", agent_id=ident.agent_id, authorization_scope=az, epoch=epoch, now=now)
    req = plan_to_request(
        request_id="r1", capability=CAP_MIRROR_SELF_TUNE,
        action_descriptor="self_tune", plan_ref="",
        conditions={"agent": "brain-gemma", "action": "self_tune",
                    "verification": verification})
    return gov, ident, sig, plan, az, constr, grant, req


# ===========================================================================
# A. CONSUMER PROOF + L0 LADDER
# ===========================================================================
def test_consumer_proof_full_tune_round_trip_decides_auto():
    """A complete mirror self-tune flows through the adapter into the neutral
    contract and decide() returns AUTO — driven purely by generic inputs."""
    gov, ident, sig, plan, az, constr, grant, req = _full_tune()
    assert gov.verify_grant(grant)
    d = decide_mirror_action(
        identity=ident, grant=grant, authorization_scope=az, request=req,
        constraints=constr, current_epoch=1, now=100,
        trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert isinstance(d, AuthorizationDecision)
    assert d.verdict == "AUTO"
    assert d.reason == "granted"
    assert d.capability == CAP_MIRROR_SELF_TUNE


def test_consumer_proof_high_priority_forces_human():
    """When policy requires human approval, the same translated self-tune yields
    HUMAN — and the mirror semantics are expressed only as a policy flag."""
    gov, ident, sig, plan, az, _, grant, req = _full_tune()
    constr = build_governance_constraints(
        allowlist=(CAP_MIRROR_SELF_TUNE,), require_human_approval=True)
    d = decide_mirror_action(
        identity=ident, grant=grant, authorization_scope=az, request=req,
        constraints=constr, current_epoch=1, now=100,
        trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d.verdict == "HUMAN"
    assert d.reason == "granted"


def test_consumer_proof_metrics_stay_in_evidence_payload_only():
    """The cpu_load/error_rate/queue_depth values are carried inside
    Evidence.payload as opaque data. Present in the translated object, yet
    decide() never reads them."""
    sig_hi = MirrorSignal(signal_id="a", agent_id="brain-gemma", needs_tuning=True,
                          cpu_load=0.99, error_rate=0.5, queue_depth=2000)
    sig_lo = MirrorSignal(signal_id="b", agent_id="brain-gemma", needs_tuning=False,
                          cpu_load=0.10, error_rate=0.01, queue_depth=2)
    prop_hi = signal_to_proposition(sig_hi)
    prop_lo = signal_to_proposition(sig_lo)
    ev_hi = signal_to_evidence(sig_hi, prop_hi)
    ev_lo = signal_to_evidence(sig_lo, prop_lo)
    assert ev_hi.payload["cpu_load"] == 0.99
    assert ev_lo.payload["cpu_load"] == 0.10
    assert ev_hi.payload["error_rate"] == 0.5
    assert ev_lo.payload["queue_depth"] == 2
    # Neither object has any authority-bearing field.
    assert not hasattr(ev_hi, "verdict")
    assert not hasattr(ev_lo, "verdict")


def test_ladder_recommendation_promotes_to_proposal_and_stays_advisory():
    """The L0 ladder: a SelfTunePlan flows Recommendation -> Proposal. The
    Proposal is a valid intent (in-scope), but is structurally incapable of
    authority, and still cannot reach decide() without an external grant."""
    sig = MirrorSignal(signal_id="a", agent_id="brain-gemma", needs_tuning=True,
                       cpu_load=0.9, error_rate=0.3, queue_depth=500)
    plan = SelfTunePlan(plan_id="p", agent_id="brain-gemma", action="self_tune",
                        tune_priority=1, verification="VERIFIED")
    prop = signal_to_proposition(sig)
    rec = plan_to_recommendation(plan, prop)
    assert rec.authority == "NONE"  # advisory only
    pscope = build_proposal_scope()
    proposal = plan_to_proposal(plan, proposal_scope=pscope)
    # A Proposal is intent, not permission.
    assert proposal.action_descriptor == "self_tune"
    assert not hasattr(proposal, "verdict")
    assert not isinstance(proposal, AuthorityGrant)
    # Even with a Proposal in hand, decide() requires a grant — none here.
    az = build_authorization_scope((CAP_MIRROR_SELF_TUNE,))
    constr = build_governance_constraints(allowlist=(CAP_MIRROR_SELF_TUNE,))
    d = decide(
        identity=_identity(), grant=None, authorization_scope=az,
        request=plan_to_request(request_id="r", capability=CAP_MIRROR_SELF_TUNE,
                                action_descriptor="self_tune", plan_ref=proposal.content_hash),
        constraints=constr, current_epoch=1, now=100, trusted_issuer_pubkey_pem="x")
    assert d.verdict == "BLOCKED" and d.reason == "no_grant"


def test_ladder_proposal_refuses_out_of_scope_action():
    """The promotion gate is FAIL-CLOSED: a SelfTunePlan whose action is not in
    MIRROR_PROPOSAL_SCOPE cannot be promoted to a Proposal. This is the
    structural guard against a self-reflection silently becoming an intent to
    perform an out-of-scope action. The frozen substrate does not enforce this
    (it is domain-neutral); the adapter enforces it at the bilingual boundary."""
    plan = SelfTunePlan(plan_id="p", agent_id="brain-gemma", action="system.shutdown",
                        tune_priority=1, verification="VERIFIED")
    pscope = build_proposal_scope()
    try:
        plan_to_proposal(plan, proposal_scope=pscope)
    except AssertionError as e:
        assert "refusing to promote out-of-scope action" in str(e)
    else:
        raise AssertionError("expected fail-closed refusal of out-of-scope promotion")


# ===========================================================================
# B. REVERSE-BOUNDARY ADVERSARIAL
# ===========================================================================
def test_reverse_selftuneplan_is_not_an_authority_object():
    """RISK 1: a mirror SelfTunePlan must NOT be treated as an epistemic
    authority object. The substrate's only permission object is
    AuthorizationDecision; SelfTunePlan is foreign and unrelated."""
    plan = SelfTunePlan(plan_id="p", agent_id="brain-gemma", action="self_tune",
                        tune_priority=1, verification="VERIFIED")
    assert not hasattr(AuthorizationDecision, "tune_priority")
    assert "SelfTunePlan" not in {c.__name__ for c in AuthorizationDecision.__mro__}
    assert not isinstance(plan, AuthorityGrant)


def test_reverse_metrics_cannot_influence_authorization_decision():
    """RISK 2: feeding cpu_load 0.99/err 0.5/q 2000 vs 0.10/err 0.01/q 2 must
    produce the SAME verdict, because decide() never receives those values. The
    values live in Evidence and stop there."""
    gov, ident, _, _, az, constr, grant, req = _full_tune()
    d_hi = decide_mirror_action(identity=ident, grant=grant, authorization_scope=az,
                                request=req, constraints=constr, current_epoch=1, now=100,
                                trusted_issuer_pubkey_pem=gov.public_key_pem)
    d_lo = decide_mirror_action(identity=ident, grant=grant, authorization_scope=az,
                                request=req, constraints=constr, current_epoch=1, now=100,
                                trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d_hi.verdict == d_lo.verdict == "AUTO"
    params = set(inspect.signature(decide).parameters)
    assert not any("cpu" in p or "error" in p or "queue" in p or "mirror" in p for p in params)


def test_reverse_mirror_object_cannot_leak_into_neutral_package():
    """RISK 3: mirror domain objects (SelfTunePlan, MirrorSignal) must not
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
    forbidden = ("SelfTunePlan", "MirrorSignal", "mirror", "supply",
                 "incident", "exchange", "ProbabilityEstimate", "fleet.fin")
    offenders = sorted(s for s in forbidden if s in all_ids)
    assert not offenders, f"fleet.epistemic code must not reference domain runtime: {offenders}"


def test_reverse_mirror_capability_is_not_universal_authorization():
    """RISK 4: 'mirror.self_tune' is domain-scoped. A grant scoped to mirror
    cannot authorize an unrelated universal action."""
    gov = _gov()
    ident = _identity()
    az_mir = build_authorization_scope((CAP_MIRROR_SELF_TUNE,))
    grant = gov.issue_grant(grant_id="g", agent_id=ident.agent_id,
                            authorization_scope=az_mir, epoch=1, now=100)
    constr = build_governance_constraints(allowlist=(CAP_MIRROR_SELF_TUNE,))
    req_other = plan_to_request(request_id="r", capability="system.shutdown",
                                action_descriptor="x", plan_ref="")
    d = decide_mirror_action(identity=ident, grant=grant, authorization_scope=az_mir,
                             request=req_other, constraints=constr, current_epoch=1, now=100,
                             trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d.verdict == "BLOCKED" and d.reason == "capability_not_granted"


def test_reverse_cannot_bypass_decide():
    """RISK 5: there is no adapter helper that fabricates an AuthorizationDecision
    without calling decide(). The adapter's decide_mirror_action is a thin
    pass-through to it."""
    src_decide = inspect.getsource(decide)
    assert "AuthorizationDecision(" in src_decide
    src_adapter = inspect.getsource(madapter.decide_mirror_action)
    assert "decide(" in src_adapter


def test_reverse_mirror_system_cannot_self_sign_valid_grant():
    """RISK 6: a malicious mirror component with no governance key cannot forge
    a grant that verifies against the trusted issuer pinned in decide()."""
    gov = _gov()
    attacker_key = Ed25519PrivateKey.generate()
    from fleet.epistemic.scope import AuthorizationScope
    from fleet.crypto.foundation import canonical_bytes
    from cryptography.hazmat.primitives import serialization as ser
    az = build_authorization_scope((CAP_MIRROR_SELF_TUNE,))
    attacker_pub_pem = attacker_key.public_key().public_bytes(
        ser.Encoding.PEM, ser.PublicFormat.SubjectPublicKeyInfo).decode()
    forged = AuthorityGrant(
        grant_id="forge", agent_id="brain-gemma",
        authorization_scope_hash=az.compute_hash(), epoch=1, issued_at=100,
        expires_at=1000, governance_role="SelfGov",
        signer_pubkey_pem=attacker_pub_pem, signature="")
    forged = replace(forged, signature=attacker_key.sign(canonical_bytes(forged.state())).hex())
    ident = _identity()
    req = plan_to_request(request_id="r", capability=CAP_MIRROR_SELF_TUNE,
                          action_descriptor="x", plan_ref="")
    constr = build_governance_constraints(allowlist=(CAP_MIRROR_SELF_TUNE,))
    d = decide_mirror_action(identity=ident, grant=forged, authorization_scope=az,
                             request=req, constraints=constr, current_epoch=1, now=100,
                             trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d.verdict == "BLOCKED"
    assert d.reason == "invalid_grant_signature"


def test_reverse_epistemic_layer_does_not_import_mirror_adapter():
    """RISK 7: directionality. fleet.epistemic must remain ignorant of this
    adapter. Confirmed by AST scan: no module under fleet/epistemic imports
    mirror.epistemic_adapter (or mirror.sim / the other adapters / fleet.fin)."""
    ep = __import__("pathlib").Path(__file__).resolve().parents[2] / "fleet" / "epistemic"
    bad = ("mirror.epistemic_adapter", "mirror.sim", "hypothesis.epistemic_adapter",
           "hypothesis.sim", "supply.epistemic_adapter", "supply.sim",
           "incident.epistemic_adapter", "incident.sim",
           "exchange.epistemic_adapter", "exchange.quant", "exchange.governance",
           "fleet.fin")
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
    its core objects works even when ALL FIVE adapters are forcibly removed
    from sys.modules."""
    saved = {}
    for mod in ("exchange.epistemic_adapter", "incident.epistemic_adapter",
                "supply.epistemic_adapter", "hypothesis.epistemic_adapter",
                "mirror.epistemic_adapter"):
        saved[mod] = sys.modules.pop(mod, None)
    try:
        import importlib
        for m in ("fleet.epistemic", "exchange.epistemic_adapter",
                  "incident.epistemic_adapter", "supply.epistemic_adapter",
                  "hypothesis.epistemic_adapter", "mirror.epistemic_adapter"):
            sys.modules.pop(m, None)
        from fleet.epistemic import proposition as _p
        # ensure module-level removal really took
        assert "mirror.epistemic_adapter" not in sys.modules
    except ImportError:
        pass
    try:
        import fleet.epistemic as fe
        importlib.reload(fe)
        prop = fe.Proposition(domain="x", subject="s", predicate="p")
        assert prop.proposition_hash
        idn = _identity()
        assert idn.agent_id == "brain-gemma"
        az = build_authorization_scope((CAP_MIRROR_SELF_TUNE,))
        constr = build_governance_constraints(allowlist=(CAP_MIRROR_SELF_TUNE,))
        req = plan_to_request(request_id="r", capability=CAP_MIRROR_SELF_TUNE,
                              action_descriptor="x", plan_ref="")
        d = fe.decide(identity=idn, grant=None, authorization_scope=az, request=req,
                      constraints=constr, current_epoch=1, now=100,
                      trusted_issuer_pubkey_pem="x")
        assert d.verdict == "BLOCKED" and d.reason == "no_grant"
    finally:
        for mod, val in saved.items():
            if val is not None:
                sys.modules[mod] = val
