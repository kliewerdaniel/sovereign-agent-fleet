"""Single source of truth for M0 cross-domain generality (consolidation).

Every external consumer suite (exchange/incident/supply/hypothesis) used to
duplicate the same 4-domain generality block. This file owns it ONCE: a
parameterized generality suite over ``domain_registry.REGISTERED_CAPABILITIES``
so that "add a domain" is a one-line table edit, not a new test.

The registry drives the neutral ``fleet.epistemic.decide()`` directly with a
fully generic (grant, scope, policy) tuple — the substrate never sees a domain
label, only the literal capability string. The M0 claims proven here:

  1. SAME POLICY -> SAME VERDICT across ALL registered domains (semantic domain
     is irrelevant; only the literal capability + policy matter).
  2. POLICY FLIP moves EVERY domain AUTO->HUMAN together.
  3. NO SHARED SUBSTRATE STATE among domains (pure function, no per-domain cache).
  4. SCOPED GRANT cannot authorize an out-of-scope universal capability.
  5. SUBSTRATE IMPORT WALL intact: fleet.epistemic imports none of the
     registered adapters/domains (directionality, AST-confirmed).
"""
from __future__ import annotations

import ast
import sys

import pytest

import domain_registry as reg
from domain_registry import REGISTERED_CAPABILITIES, decide_all, decide_registered

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


@pytest.fixture
def gov():
    return reg.GovernanceAuthority(Ed25519PrivateKey.generate())


def test_registry_table_has_all_four_consumers():
    """The registry enumerates exactly the four external consumers; capability
    strings are distinct literals (the substrate sees the string, not the label)."""
    labels = [label for label, _ in REGISTERED_CAPABILITIES]
    caps = [cap for _, cap in REGISTERED_CAPABILITIES]
    assert labels == [
        "exchange/finance", "incident/security",
        "supply/logistics", "hypothesis/research",
    ]
    assert len(set(caps)) == 4 == len(caps)


def test_m0_same_policy_same_verdict_across_all_registered_domains(gov):
    """All registered domains return the IDENTICAL verdict + reason under the
    same AUTO policy. Different literal capability strings, identical substrate
    verdict — the semantic domain is invisible to decide()."""
    results = decide_all(policy_allow=True, human=False, gov=gov)
    verdicts = [r.verdict for r in results]
    reasons = [r.reason for r in results]
    assert verdicts == ["AUTO", "AUTO", "AUTO", "AUTO"]
    assert reasons == ["granted", "granted", "granted", "granted"]
    # Distinct capability literals survive through to the decision...
    assert len({r.capability for r in results}) == 4
    # ...but the substrate verdict is identical across all four.
    assert len({r.verdict for r in results}) == 1


def test_m0_policy_flip_changes_all_registered_domains_identically(gov):
    """When policy flips (require_human_approval), EVERY registered domain moves
    AUTO->HUMAN together. Substrate behavior is a pure function of
    (grant, scope, policy) — never the domain."""
    auto = decide_all(policy_allow=True, human=False, gov=gov)
    human = decide_all(policy_allow=True, human=True, gov=gov)
    assert [r.verdict for r in auto] == ["AUTO", "AUTO", "AUTO", "AUTO"]
    assert [r.verdict for r in human] == ["HUMAN", "HUMAN", "HUMAN", "HUMAN"]


def test_m0_no_shared_substrate_state_among_registered_domains(gov):
    """The substrate keeps no per-domain state. A repeated interleaved sequence
    of decisions across all four domains uses the same pure function and yields
    domain-independent results — guards against any accidental module-level
    domain cache."""
    seq = [c for _, c in REGISTERED_CAPABILITIES] + [REGISTERED_CAPABILITIES[0][1]]
    verdicts = [
        decide_registered(label, cap, policy_allow=True, human=False, gov=gov).verdict
        for label, cap in REGISTERED_CAPABILITIES
        for _ in range(1)
    ] + [decide_registered(REGISTERED_CAPABILITIES[0][0], REGISTERED_CAPABILITIES[0][1],
                           policy_allow=True, human=False, gov=gov).verdict]
    assert verdicts == ["AUTO", "AUTO", "AUTO", "AUTO", "AUTO"]


@pytest.mark.parametrize("label,capability", REGISTERED_CAPABILITIES)
def test_m0_each_registered_domain_decides_auto_under_allow_policy(label, capability, gov):
    """Parameterized across the registry table: each registered capability, on
    its own, yields AUTO when allowed. Adding a domain extends this for free."""
    d = decide_registered(label, capability, policy_allow=True, human=False, gov=gov)
    assert d.verdict == "AUTO"
    assert d.reason == "granted"
    assert d.capability == capability


@pytest.mark.parametrize("label,capability", REGISTERED_CAPABILITIES)
def test_m0_scoped_grant_cannot_authorize_universal_capability(label, capability, gov):
    """A grant scoped to ONE registered capability cannot authorize an unrelated
    universal action. The domain scope stays bounded at the substrate."""
    out_of_scope = decide_registered(
        label, capability, policy_allow=True, human=False, gov=gov,
        request_capability="system.shutdown")
    assert out_of_scope.verdict == "BLOCKED"
    assert out_of_scope.reason == "capability_not_granted"


def test_reverse_epistemic_layer_does_not_import_any_registered_adapter():
    """RISK 7 (consolidated): fleet.epistemic must remain ignorant of every
    registered adapter/domain. AST scan over all modules under fleet/epistemic
    confirms none import the adapter packages, the domain sim packages, or
    fleet.fin. This is the directionality invariant the adapters depend on."""
    ep = __import__("pathlib").Path(__file__).resolve().parents[2] / "fleet" / "epistemic"
    bad = (
        "exchange.epistemic_adapter", "exchange.quant", "exchange.governance",
        "incident.epistemic_adapter", "incident.sim",
        "supply.epistemic_adapter", "supply.sim",
        "hypothesis.epistemic_adapter", "hypothesis.sim",
        "domain_registry", "fleet.fin",
    )
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
    assert not offenders, f"fleet.epistemic must not import adapters/domains/registry: {offenders}"


def test_reverse_substrate_functional_without_any_adapter_present():
    """RISK 8 (consolidated): the neutral substrate imports and operates with
    NO reference to any adapter/registry. Force-removing all of them from
    sys.modules still lets fleet.epistemic decide() (BLOCKED, no_grant) cleanly."""
    saved = {}
    for mod in ("exchange.epistemic_adapter", "incident.epistemic_adapter",
                "supply.epistemic_adapter", "hypothesis.epistemic_adapter",
                "domain_registry"):
        saved[mod] = sys.modules.pop(mod, None)
    try:
        import importlib
        for m in ("fleet.epistemic",) + tuple(saved):
            sys.modules.pop(m, None)
        import fleet.epistemic as fe
        importlib.reload(fe)
        idn = reg.AgentIdentity.from_cert(reg.AgentCert(
            agent_id="x", pubkey_pem="pub", role="operator", capabilities=["c"],
            issued_at=0, expires_at=10**9, cert_seq=0, root_sig=""))
        az = reg.build_authorization_scope(("c",))
        constr = reg.build_governance_constraints(allowlist=("c",))
        req = reg.AuthorizationRequest(producer="t", request_id="r", capability="c")
        d = fe.decide(identity=idn, grant=None, authorization_scope=az, request=req,
                      constraints=constr, current_epoch=1, now=100,
                      trusted_issuer_pubkey_pem="x")
        assert d.verdict == "BLOCKED" and d.reason == "no_grant"
    finally:
        for mod, val in saved.items():
            if val is not None:
                sys.modules[mod] = val
