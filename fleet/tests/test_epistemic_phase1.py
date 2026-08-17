"""Phase 1 — neutral epistemic kernel tests (ratified-invariant focused).

These tests assert the invariants the architecture ratified. They do NOT invent
new architecture; they prove the kernel:

    * is content-addressed with the EXISTING crypto foundation (canonical_bytes/sha256)
    * is immutable (semantically-equal objects hash equally; construction is frozen)
    * expresses cognition + intent but NEVER authorization
    * cannot let Recommendation/Proposal/probability/confidence silently become authority
    * respects the Phase 0 import wall (no financial/runtime deps pulled in)

All objects import only fleet.crypto.foundation + stdlib (enforced separately by
fleet/tests/test_boundary_epistemic.py).
"""
from __future__ import annotations

import pytest

from fleet.epistemic import (
    Artifact,
    Proposition,
    Uncertainty,
    Evidence,
    Belief,
    Assessment,
    Recommendation,
    assert_advisory,
    AuthorityPromotionError,
    Proposal,
    AuthorizationRequest,
)


# ---------------------------------------------------------------------------
# 1. canonical deterministic hashing
# ---------------------------------------------------------------------------
def test_artifact_content_hash_is_deterministic_and_derived():
    a = Evidence(producer="feed", evidence_kind="quote", payload={"x": 1})
    b = Evidence(producer="feed", evidence_kind="quote", payload={"x": 1})
    assert a.content_hash == b.content_hash
    # hash is derived solely from canonical state (no id/ts/mem noise)
    assert a.content_hash == sha256_of(a.state())


def test_distinct_state_yields_distinct_hash():
    a = Evidence(producer="feed", evidence_kind="quote", payload={"x": 1})
    b = Evidence(producer="feed", evidence_kind="quote", payload={"x": 2})
    assert a.content_hash != b.content_hash


def sha256_of(d):
    from fleet.crypto.foundation import canonical_bytes, sha256
    return sha256(canonical_bytes(d))


# ---------------------------------------------------------------------------
# 2. immutable artifact behavior
# ---------------------------------------------------------------------------
def test_artifacts_are_frozen():
    from dataclasses import FrozenInstanceError
    e = Evidence(producer="feed", payload={"x": 1})
    # Frozen dataclass: any attribute reassignment is blocked by the interpreter.
    with pytest.raises(FrozenInstanceError):
        e.producer = "other"
    # Identity is content-derived and fixed at construction; equal content hashes
    # equally regardless of object identity.
    e2 = Evidence(producer="feed", payload={"x": 1})
    assert e.content_hash == e2.content_hash
    # Canonical identity is the content-derived hash (never object/memory state).
    assert hash(e.content_hash) == hash(e2.content_hash)


def test_equal_objects_hash_equal_and_are_equal():
    p = Proposition(domain="m", subject="S", predicate="P_yes", params={"h": 1})
    p2 = Proposition(domain="m", subject="S", predicate="P_yes", params={"h": 1})
    assert p == p2
    assert p.proposition_hash == p2.proposition_hash


# ---------------------------------------------------------------------------
# 3. Proposition identity
# ---------------------------------------------------------------------------
def test_proposition_identity_is_param_stable():
    base = dict(domain="market_probability", subject="KXIN", predicate="P_yes")
    a = Proposition(**base, params={"horizon": 10})
    b = Proposition(**base, params={"horizon": 10})
    c = Proposition(**base, params={"horizon": 20})  # different params -> different id
    assert a.proposition_hash == b.proposition_hash
    assert a.proposition_hash != c.proposition_hash


def test_proposition_is_domain_neutral():
    fin = Proposition(domain="market_probability", subject="KXIN", predicate="P_yes")
    inc = Proposition(domain="incident_compromised", subject="host-17", predicate="is_compromised")
    assert fin.proposition_hash != inc.proposition_hash


# ---------------------------------------------------------------------------
# 4. Evidence provenance representation
# ---------------------------------------------------------------------------
def test_evidence_carries_lineage_inputs():
    up = Evidence(producer="sensor", evidence_kind="observation", payload={"v": 5})
    derived = Evidence(producer="model", evidence_kind="inference",
                       payload={"out": 1}, inputs=[up.content_hash])
    assert up.content_hash in derived.inputs
    assert derived.evidence_kind == "inference"


# ---------------------------------------------------------------------------
# 5. Belief -> Proposition relationship
# ---------------------------------------------------------------------------
def test_belief_references_proposition():
    prop = Proposition(domain="market_probability", subject="KXIN", predicate="P_yes")
    bel = Belief(producer="researcher", proposition=prop,
                 estimate=Uncertainty.point(0.71), evidence_refs=[])
    assert bel.proposition.proposition_hash == prop.proposition_hash
    assert bel.estimate.kind == "point"


def test_belief_requires_proposition_and_estimate():
    with pytest.raises(ValueError):
        Belief(producer="x", proposition=None, estimate=None)


# ---------------------------------------------------------------------------
# 6. uncertainty representation
# ---------------------------------------------------------------------------
def test_uncertainty_three_shapes():
    assert Uncertainty.point(0.5).kind == "point"
    assert Uncertainty.interval(0.1, 0.9).kind == "interval"
    assert Uncertainty.entropy(0.3).kind == "entropy"


def test_uncertainty_records_epistemic_vs_aleatoric():
    u = Uncertainty.point(0.5, epistemic=0.1, aleatoric=0.2)
    assert u.epistemic == 0.1 and u.aleatoric == 0.2


def test_uncertainty_is_value_not_engine():
    # The object stores a value; it has no inference/update methods.
    u = Uncertainty.point(0.5)
    assert not hasattr(u, "update")
    assert not hasattr(u, "bayes")


# ---------------------------------------------------------------------------
# 7. Assessment semantics
# ---------------------------------------------------------------------------
def test_assessment_is_not_a_belief():
    a = Assessment(producer="risk", subject="portfolio:EXC",
                   condition={"max_pct": 10}, observed={"pct": 12.3}, result="BREACH")
    assert a.result == "BREACH"
    assert a.KIND == "assessment"
    # an Assessment has no probability field that would make it probabilistic
    assert "p_yes" not in a.state()


def test_assessment_neutral_breach_and_stale():
    breach = Assessment(producer="risk", subject="x", condition={"max": 10},
                        observed={"val": 12}, result="BREACH")
    stale = Assessment(producer="dq", subject="feed", condition={"max_h": 12},
                       observed={"age_h": 17}, result="STALE")
    assert breach.result == "BREACH" and stale.result == "STALE"


# ---------------------------------------------------------------------------
# 8. Recommendation authority = NONE
# ---------------------------------------------------------------------------
def test_recommendation_authority_is_none_structurally():
    r = Recommendation(producer="pm", target="KXIN", action_suggestion="reduce 20%")
    assert r.authority == "NONE"
    assert r.state()["authority"] == "NONE"


def test_recommendation_rejects_non_none_authority():
    with pytest.raises(AuthorityPromotionError):
        Recommendation(producer="pm", authority="APPROVE")


# ---------------------------------------------------------------------------
# 9. Recommendation cannot become Proposal (no implicit conversion)
# ---------------------------------------------------------------------------
def test_recommendation_has_no_promotion_path_to_proposal():
    r = Recommendation(producer="pm", target="KXIN", action_suggestion="reduce 20%")
    # The type-level guard is the ABSENCE of a conversion method.
    assert not hasattr(r, "to_proposal")
    assert not hasattr(r, "as_proposal")
    assert not hasattr(r, "promote")


# ---------------------------------------------------------------------------
# 10. Proposal contains intent but grants no authority
# ---------------------------------------------------------------------------
def test_proposal_has_no_authority_fields():
    p = Proposal(producer="pm", action_descriptor="allocate", target_ref="KXIN",
                 rationale="edge positive")
    assert p.KIND == "proposal"
    for forbidden in ("capability", "authority", "approved", "risk_budget", "grant"):
        assert forbidden not in p.state(), f"Proposal must not carry {forbidden}"


# ---------------------------------------------------------------------------
# 11. AuthorizationRequest grants no authority
# ---------------------------------------------------------------------------
def test_authorization_request_grants_no_authority():
    req = AuthorizationRequest(producer="pm", request_id="r1",
                               capability="exchange.trade_execute",
                               action_descriptor="BUY 100 KXIN",
                               proposal_ref="prop-hash")
    assert req.KIND == "authorization_request"
    # It references a proposal; it does not contain a decision or grant.
    s = req.state()
    assert "proposal_ref" in s
    for forbidden in ("decision", "disposition", "grant", "approved", "authority_grant"):
        assert forbidden not in s, f"AuthorizationRequest must not carry {forbidden}"


# ---------------------------------------------------------------------------
# 12. no probability/confidence field can become an authorization directive
# ---------------------------------------------------------------------------
def test_probability_lives_in_belief_not_in_request():
    prop = Proposition(domain="market_probability", subject="KXIN", predicate="P_yes")
    bel = Belief(producer="researcher", proposition=prop, estimate=Uncertainty.point(0.83))
    req = AuthorizationRequest(producer="pm", capability="exchange.trade_execute",
                               action_descriptor="BUY", proposal_ref="h")
    # probability is sealed inside Belief; the request schema structurally cannot carry it.
    assert "estimate" not in req.state()
    assert bel.estimate.p == 0.83


# ---------------------------------------------------------------------------
# 13. forbidden imports remain rejected (Phase 0 wall intact + new modules)
# ---------------------------------------------------------------------------
def test_epistemic_modules_only_import_crypto_and_stdlib():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "fleet" / "epistemic"
    forbidden = (
        "fleet.cognition", "exchange.quant", "exchange.governance",
        "fleet.fin", "fleet.simenv", "fleet.layers", "fleet.gcp", "fleet.api",
    )
    for path in root.rglob("*.py"):
        if path.name in ("_boundary_bad_fixture.py",):
            continue
        src = path.read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            mod = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name
                    assert mod not in forbidden and not mod.startswith(tuple(f + "." for f in forbidden)), \
                        f"{path.name}: forbidden import {mod}"
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert mod not in forbidden and not mod.startswith(tuple(f + "." for f in forbidden)), \
                    f"{path.name}: forbidden from-import {mod}"


# ---------------------------------------------------------------------------
# 14. epistemic package remains importable without forbidden subsystems
# ---------------------------------------------------------------------------
def test_import_does_not_load_forbidden_subsystems():
    import sys

    forbidden_modules = {
        "fleet.cognition", "exchange.quant", "exchange.governance",
        "fleet.fin", "fleet.simenv", "fleet.layers", "fleet.gcp", "fleet.api",
    }
    before = set(sys.modules)
    import fleet.epistemic  # noqa: F401
    after = set(sys.modules)

    # Only genuinely-NEW modules pulled in by importing fleet.epistemic may be
    # loaded. If any forbidden subsystem is *newly* present, the wall is breached.
    newly_loaded = after - before
    for name in newly_loaded:
        assert not any(name == f or name.startswith(f + ".") for f in forbidden_modules), \
            f"importing fleet.epistemic loaded forbidden {name}"


# ---------------------------------------------------------------------------
# ADVERSARIAL TESTS — the pressure points the architecture must hold
# ---------------------------------------------------------------------------
def test_advisory_recommendation_cannot_become_authority():
    r = Recommendation(producer="pm", target="KXIN", action_suggestion="reduce 20%")
    # Even a helper that checks authority fails closed if it ever claimed some.
    assert_advisory(r)  # passes — it is NONE
    # Constructing one that lies is impossible: __post_init__ rejects it.
    with pytest.raises(AuthorityPromotionError):
        Recommendation(producer="pm", authority="APPROVE")


def test_proposal_cannot_become_authorization():
    p = Proposal(producer="pm", action_descriptor="allocate")
    # A Proposal has no field a gate could read as "approved".
    assert "approved" not in p.state()
    assert "authority" not in p.state()


def test_probability_cannot_become_authorization_directive():
    prop = Proposition(domain="market_probability", subject="KXIN", predicate="P_yes")
    bel = Belief(producer="researcher", proposition=prop, estimate=Uncertainty.point(0.99))
    # The high confidence is sealed inside epistemic content; it cannot reach a
    # governance directive because the request schema excludes it.
    req = AuthorizationRequest(producer="x", capability="c", action_descriptor="a", proposal_ref="h")
    assert "estimate" not in req.state() and "confidence" not in req.state()


def test_confidence_cannot_become_authorization():
    # Confidence is just another epistemic value; same exclusion holds.
    u = Uncertainty.point(0.97, epistemic=0.02)
    assert u.p == 0.97
    req = AuthorizationRequest(producer="x", capability="c", action_descriptor="a")
    assert "confidence" not in req.state()


def test_epistemic_artifact_cannot_grant_capability():
    # None of the Phase 1 objects expose a capability grant.
    objs = [
        Proposition(domain="d", subject="s", predicate="p"),
        Evidence(producer="p"),
        Belief(producer="p", proposition=Proposition(domain="d", subject="s", predicate="p"),
               estimate=Uncertainty.point(0.5)),
        Assessment(producer="p"),
        Recommendation(producer="p"),
        Proposal(producer="p"),
        AuthorizationRequest(producer="p", capability="c", action_descriptor="a"),
    ]
    for o in objs:
        assert not hasattr(o, "grant_capability")
        assert not hasattr(o, "authority_grant")


def test_authority_is_contract_gated_not_epistemic():
    # Phase 2 introduced the authority contract, but it must remain OUT OF REACH
    # of the Phase 1 epistemic artifacts. The only way to obtain an
    # AuthorizationDecision is through decide() over an externally-signed grant;
    # no epistemic object may carry or mint authority.
    import fleet.epistemic as fe

    # Phase 1 epistemic artifacts still carry NO authority mechanism.
    for name in ("AuthorityGrant", "AuthorizationDecision",
                 "CapabilityScope", "AuthorizationScope"):
        # These now EXIST (Phase 2) — but they must NOT be reachable from the
        # epistemic cognition objects below.
        assert hasattr(fe, name)

    # The cognition/intent objects expose no grant/decision capability.
    objs = [
        fe.Proposition(domain="d", subject="s", predicate="p"),
        fe.Evidence(producer="p"),
        fe.Belief(producer="p", proposition=fe.Proposition(domain="d", subject="s", predicate="p"),
                  estimate=fe.Uncertainty.point(0.5)),
        fe.Assessment(producer="p"),
        fe.Recommendation(producer="pm"),
        fe.Proposal(producer="p"),
        fe.AuthorizationRequest(producer="p", capability="c", action_descriptor="a"),
    ]
    for o in objs:
        assert not hasattr(o, "grant_capability")
        assert not hasattr(o, "authority_grant")
        assert not hasattr(o, "decide")


def test_stale_or_implicit_permission_is_absent():
    # There is no 'implicitly approved' flag anywhere in the kernel.
    p = Proposal(producer="pm", action_descriptor="allocate")
    r = Recommendation(producer="pm")
    for o in (p, r):
        assert "implicit" not in o.state()
        assert "auto_approve" not in o.state()
