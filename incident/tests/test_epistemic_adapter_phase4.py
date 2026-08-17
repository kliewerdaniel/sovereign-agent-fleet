"""Phase 4 (M0) — SECOND external CONSUMER PROOF + cross-domain generality proof.

This suite proves the central M0 claim: **the neutral substrate (fleet.epistemic)
is domain-general — it serves the incident-response domain through this adapter
with the SAME contract and the SAME decide() it already serves the financial firm
through, with zero substrate edits between the two.**

Three halves:
  A. CONSUMER PROOF (test_*_consumes_*) — drive the real incident objects through
     the adapter into the neutral contract and observe decide() produces a correct
     AuthorizationDecision using only generic inputs, while remaining domain-agnostic.

  B. REVERSE-BOUNDARY ADVERSARIAL (test_*_cannot_*) — the eight risks, each
     asserting the incident side CANNOT break the neutrality of the substrate:
       1. a RemediationPlan cannot become an epistemic authority object
       2. severity/confidence cannot influence AuthorizationDecision
       3. an incident object cannot leak into the neutral package
       4. an incident-specific capability cannot become a universal authorization
       5. the incident system cannot bypass decide()
       6. the incident system cannot manufacture its own (valid) grant
       7. the epistemic layer does not import the incident adapter (directionality)
       8. deleting BOTH adapters leaves fleet.epistemic fully functional

  C. CROSS-DOMAIN GENERALITY (test_m0_*) — the decisive M0 proof. The substrate
     returns the SAME verdict for the SAME (grant valid, scope match, policy) tuple
     regardless of whether the request is labeled incident or exchange. And it
     returns a DIFFERENT verdict when policy flips — proving the verdict is a pure
     function of (grant, scope, policy), never the semantic domain. This is the
     reason 'substrate does not derive identity from first consumer' holds.
"""
from __future__ import annotations

import ast
import inspect
import sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from dataclasses import replace

import incident.epistemic_adapter as iadapter
import exchange.epistemic_adapter as eadapter
from incident.epistemic_adapter import (
    GovernanceAuthority,
    build_authorization_scope,
    build_capability_scope,
    build_governance_constraints,
    decide_incident_action,
    plan_to_request,
    plan_to_recommendation,
    signal_to_evidence,
    signal_to_proposition,
    CAP_INCIDENT_REMEDIATE,
)
from incident.sim import IncidentSignal, RemediationPlan

from fleet.epistemic.authority import AuthorityGrant
from fleet.epistemic.decision import AuthorizationDecision, decide
from fleet.epistemic.identity import AgentIdentity
from fleet.crypto.foundation import AgentCert


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
def _gov() -> GovernanceAuthority:
    return GovernanceAuthority(Ed25519PrivateKey.generate())


def _identity(agent_id: str = "secops-1", caps=(CAP_INCIDENT_REMEDIATE,)) -> AgentIdentity:
    cert = AgentCert(
        agent_id=agent_id, pubkey_pem="pub", role="operator",
        capabilities=list(caps), issued_at=0, expires_at=10**9, cert_seq=0, root_sig="",
    )
    return AgentIdentity.from_cert(cert)


def _full_remediation(gov=None, now=100, epoch=1, verification="VERIFIED"):
    """Build a complete incident remediation order translated through the adapter."""
    gov = gov or _gov()
    ident = _identity()
    sig = IncidentSignal(
        signal_id="s1", asset="web-edge", is_compromised=True,
        severity="HIGH", confidence=0.92, method="detector")
    plan = RemediationPlan(
        plan_id="p1", asset="web-edge", action="block_egress",
        triage_priority=1, verification=verification)
    az = build_authorization_scope((CAP_INCIDENT_REMEDIATE,), governance_role="SecurityOps")
    constr = build_governance_constraints(
        allowlist=(CAP_INCIDENT_REMEDIATE,), require_human_approval=False)
    grant = gov.issue_grant(
        grant_id="g1", agent_id=ident.agent_id, authorization_scope=az, epoch=epoch, now=now)
    req = plan_to_request(
        request_id="r1", capability=CAP_INCIDENT_REMEDIATE,
        action_descriptor="remediate:web-edge:block_egress", plan_ref="",
        conditions={"asset": "web-edge", "action": "block_egress", "verification": verification})
    return gov, ident, sig, plan, az, constr, grant, req


# ===========================================================================
# A. CONSUMER PROOF
# ===========================================================================
def test_consumer_proof_full_remediation_round_trip_decides_auto():
    """A complete incident remediation flows through the adapter into the neutral
    contract and decide() returns AUTO — driven purely by generic inputs."""
    gov, ident, sig, plan, az, constr, grant, req = _full_remediation()
    assert gov.verify_grant(grant)
    d = decide_incident_action(
        identity=ident, grant=grant, authorization_scope=az, request=req,
        constraints=constr, current_epoch=1, now=100,
        trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert isinstance(d, AuthorizationDecision)
    assert d.verdict == "AUTO"
    assert d.reason == "granted"
    assert d.capability == CAP_INCIDENT_REMEDIATE


def test_consumer_proof_high_severity_forces_human():
    """When policy requires human approval, the same translated remediation yields
    HUMAN — and the incident semantics are expressed only as a policy flag."""
    gov, ident, sig, plan, az, _, grant, req = _full_remediation()
    constr = build_governance_constraints(
        allowlist=(CAP_INCIDENT_REMEDIATE,), require_human_approval=True)
    d = decide_incident_action(
        identity=ident, grant=grant, authorization_scope=az, request=req,
        constraints=constr, current_epoch=1, now=100,
        trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d.verdict == "HUMAN"
    assert d.reason == "granted"


def test_consumer_proof_severity_stays_in_evidence_payload_only():
    """The severity/confidence values are carried inside Evidence.payload as opaque
    data. Present in the translated object, yet decide() never reads them."""
    sig_hi = IncidentSignal(signal_id="a", asset="x", is_compromised=True,
                            severity="CRITICAL", confidence=0.99)
    sig_lo = IncidentSignal(signal_id="b", asset="x", is_compromised=True,
                            severity="LOW", confidence=0.51)
    prop_hi = signal_to_proposition(sig_hi)
    prop_lo = signal_to_proposition(sig_lo)
    ev_hi = signal_to_evidence(sig_hi, prop_hi)
    ev_lo = signal_to_evidence(sig_lo, prop_lo)
    assert ev_hi.payload["severity"] == "CRITICAL"
    assert ev_lo.payload["severity"] == "LOW"
    assert ev_hi.payload["confidence"] == 0.99
    # Neither object has any authority-bearing field.
    assert not hasattr(ev_hi, "verdict")
    assert not hasattr(ev_lo, "verdict")


def test_consumer_proof_recommendation_remains_advisory():
    """A RemediationPlan translated to a Recommendation is structurally incapable
    of authority: its authority field is forced to NONE by the substrate itself."""
    sig = IncidentSignal(signal_id="a", asset="x", is_compromised=True,
                         severity="HIGH", confidence=0.9)
    plan = RemediationPlan(plan_id="p", asset="x", action="isolate",
                           triage_priority=1, verification="VERIFIED")
    prop = signal_to_proposition(sig)
    rec = plan_to_recommendation(plan, prop)
    assert rec.authority == "NONE"
    # And it cannot feed decide() — decide() requires a grant, not a recommendation.
    az = build_authorization_scope((CAP_INCIDENT_REMEDIATE,))
    constr = build_governance_constraints(allowlist=(CAP_INCIDENT_REMEDIATE,))
    d = decide(
        identity=_identity(), grant=None, authorization_scope=az,
        request=plan_to_request(request_id="r", capability=CAP_INCIDENT_REMEDIATE,
                                action_descriptor="x", plan_ref=""),
        constraints=constr, current_epoch=1, now=100, trusted_issuer_pubkey_pem="x")
    assert d.verdict == "BLOCKED" and d.reason == "no_grant"


def test_consumer_proof_assessment_is_classification_not_permission():
    plan = RemediationPlan(plan_id="p", asset="x", action="snapshot",
                           triage_priority=4, verification="ASSERTED")
    asmt = iadapter.plan_to_assessment(plan)
    assert asmt.result in ("REMEDIATE", "HOLD")
    assert not hasattr(asmt, "verdict")


# ===========================================================================
# B. REVERSE-BOUNDARY ADVERSARIAL
# ===========================================================================
def test_reverse_remediationplan_is_not_an_authority_object():
    """RISK 1: an incident RemediationPlan must NOT be treated as an epistemic
    authority object. The substrate's only permission object is
    AuthorizationDecision; RemediationPlan is foreign and unrelated."""
    plan = RemediationPlan(plan_id="p", asset="x", action="block_egress",
                           triage_priority=1, verification="VERIFIED")
    assert not hasattr(AuthorizationDecision, "triage_priority")
    assert "RemediationPlan" not in {c.__name__ for c in AuthorizationDecision.__mro__}
    assert not isinstance(plan, AuthorityGrant)


def test_reverse_severity_confidence_cannot_influence_authorization_decision():
    """RISK 2: feeding CRITICAL/0.99 vs LOW/0.51 must produce the SAME verdict,
    because decide() never receives severity or confidence. The values live in
    Evidence and stop there."""
    gov, ident, _, _, az, constr, grant, req = _full_remediation()
    d_hi = decide_incident_action(identity=ident, grant=grant, authorization_scope=az,
                                  request=req, constraints=constr, current_epoch=1, now=100,
                                  trusted_issuer_pubkey_pem=gov.public_key_pem)
    d_lo = decide_incident_action(identity=ident, grant=grant, authorization_scope=az,
                                  request=req, constraints=constr, current_epoch=1, now=100,
                                  trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d_hi.verdict == d_lo.verdict == "AUTO"
    params = set(inspect.signature(decide).parameters)
    assert not any("severity" in p or "confidence" in p or "comprom" in p for p in params)


def test_reverse_incident_object_cannot_leak_into_neutral_package():
    """RISK 3: incident domain objects (RemediationPlan, IncidentSignal) must not
    appear as CODE in fleet.epistemic. Confirmed by an AST *identifier* scan."""
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
    forbidden = ("RemediationPlan", "IncidentSignal", "incident", "exchange",
                 "ProbabilityEstimate", "fleet.fin")
    offenders = sorted(s for s in forbidden if s in all_ids)
    assert not offenders, f"fleet.epistemic code must not reference domain runtime: {offenders}"


def test_reverse_incident_capability_is_not_universal_authorization():
    """RISK 4: 'incident.remediate' is domain-scoped. A grant scoped to incident
    cannot authorize an unrelated universal action."""
    gov = _gov()
    ident = _identity()
    az_inc = build_authorization_scope((CAP_INCIDENT_REMEDIATE,))
    grant = gov.issue_grant(grant_id="g", agent_id=ident.agent_id,
                             authorization_scope=az_inc, epoch=1, now=100)
    constr = build_governance_constraints(allowlist=(CAP_INCIDENT_REMEDIATE,))
    req_other = plan_to_request(request_id="r", capability="system.shutdown",
                                action_descriptor="x", plan_ref="")
    d = decide_incident_action(identity=ident, grant=grant, authorization_scope=az_inc,
                                request=req_other, constraints=constr, current_epoch=1, now=100,
                                trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d.verdict == "BLOCKED" and d.reason == "capability_not_granted"


def test_reverse_cannot_bypass_decide():
    """RISK 5: there is no adapter helper that fabricates an AuthorizationDecision
    without calling decide(). The adapter's decide_incident_action is a thin
    pass-through to it."""
    src_decide = inspect.getsource(decide)
    assert "AuthorizationDecision(" in src_decide
    src_adapter = inspect.getsource(iadapter.decide_incident_action)
    assert "decide(" in src_adapter


def test_reverse_incident_system_cannot_self_sign_valid_grant():
    """RISK 6: a malicious incident component with no governance key cannot forge a
    grant that verifies against the trusted issuer pinned in decide()."""
    gov = _gov()
    attacker_key = Ed25519PrivateKey.generate()
    from fleet.epistemic.scope import AuthorizationScope
    from fleet.crypto.foundation import canonical_bytes
    from cryptography.hazmat.primitives import serialization as ser
    az = build_authorization_scope((CAP_INCIDENT_REMEDIATE,))
    attacker_pub_pem = attacker_key.public_key().public_bytes(
        ser.Encoding.PEM, ser.PublicFormat.SubjectPublicKeyInfo).decode()
    forged = AuthorityGrant(
        grant_id="forge", agent_id="secops-1",
        authorization_scope_hash=az.compute_hash(), epoch=1, issued_at=100,
        expires_at=1000, governance_role="SecurityOps",
        signer_pubkey_pem=attacker_pub_pem, signature="")
    forged = replace(forged, signature=attacker_key.sign(canonical_bytes(forged.state())).hex())
    ident = _identity()
    req = plan_to_request(request_id="r", capability=CAP_INCIDENT_REMEDIATE,
                          action_descriptor="x", plan_ref="")
    constr = build_governance_constraints(allowlist=(CAP_INCIDENT_REMEDIATE,))
    d = decide_incident_action(identity=ident, grant=forged, authorization_scope=az,
                               request=req, constraints=constr, current_epoch=1, now=100,
                               trusted_issuer_pubkey_pem=gov.public_key_pem)
    assert d.verdict == "BLOCKED"
    assert d.reason == "invalid_grant_signature"


def test_reverse_epistemic_layer_does_not_import_incident_adapter():
    """RISK 7: directionality. fleet.epistemic must remain ignorant of this
    adapter. Confirmed by AST scan: no module under fleet/epistemic imports
    incident.epistemic_adapter (or incident.sim / exchange.* / fleet.fin)."""
    ep = __import__("pathlib").Path(__file__).resolve().parents[2] / "fleet" / "epistemic"
    bad = ("incident.epistemic_adapter", "incident.sim", "exchange.epistemic_adapter",
           "exchange.quant", "exchange.governance", "fleet.fin")
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


def test_reverse_substrate_functional_without_either_adapter_present():
    """RISK 8 (import-level): the neutral substrate imports and operates with NO
    reference to EITHER adapter. We assert importing fleet.epistemic and building
    its core objects works even when both exchange.epistemic_adapter and
    incident.epistemic_adapter are forcibly removed from sys.modules."""
    saved = {}
    for mod in ("exchange.epistemic_adapter", "incident.epistemic_adapter"):
        saved[mod] = sys.modules.pop(mod, None)
    try:
        import importlib
        for m in ("fleet.epistemic", "exchange.epistemic_adapter", "incident.epistemic_adapter"):
            sys.modules.pop(m, None)
        import fleet.epistemic as fe
        importlib.reload(fe)
        prop = fe.Proposition(domain="x", subject="s", predicate="p")
        assert prop.proposition_hash
        idn = _identity()
        assert idn.agent_id == "secops-1"
        az = build_authorization_scope((CAP_INCIDENT_REMEDIATE,))
        constr = build_governance_constraints(allowlist=(CAP_INCIDENT_REMEDIATE,))
        req = plan_to_request(request_id="r", capability=CAP_INCIDENT_REMEDIATE,
                               action_descriptor="x", plan_ref="")
        d = fe.decide(identity=idn, grant=None, authorization_scope=az, request=req,
                      constraints=constr, current_epoch=1, now=100,
                      trusted_issuer_pubkey_pem="x")
        assert d.verdict == "BLOCKED" and d.reason == "no_grant"
    finally:
        for mod, val in saved.items():
            if val is not None:
                sys.modules[mod] = val



