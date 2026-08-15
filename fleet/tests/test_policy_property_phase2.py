"""D21 P1 — machine-checked default-deny property of the policy engine.

Replaces "code review says it's deny-by-default" with a checked property:
  * For every (role, capability) pair in the table, decide() returns exactly the
    declared outcome (GRANT or REQUIRE_APPROVAL).
  * For any capability NOT declared for ANY role, decide() returns DENY.
  * For any unknown role (and any capability), decide() returns DENY.
  * Consequential capabilities always map to REQUIRE_APPROVAL, never GRANT.

This is exhaustive over the enumerated space, so it catches a future code change
that accidentally adds an implicit allow path (the gap P1 flags).
"""
import itertools

from fleet.layers.policy import (
    Decision,
    _CONSEQUENTIAL,
    _ROLE_CAPS,
    decide,
)

ALL_CAPS = sorted({c for caps in _ROLE_CAPS.values() for c in caps})
ROLES = list(_ROLE_CAPS.keys())
UNKNOWN_CAP = "definitely_not_a_real_capability"
UNKNOWN_ROLE = "definitely_not_a_real_role"


def test_p1_declared_pairs_exact_outcome():
    for role, caps in _ROLE_CAPS.items():
        for cap in caps:
            res = decide(role, cap)
            expected = (
                Decision.REQUIRE_APPROVAL if cap in _CONSEQUENTIAL
                else Decision.GRANT
            )
            assert res.decision == expected, (
                f"({role},{cap}) -> {res.decision}, expected {expected}"
            )


def test_p1_undeclared_capability_is_denied():
    # A capability that no role declares must be denied for every role.
    for role in ROLES:
        assert decide(role, UNKNOWN_CAP).decision is Decision.DENY
    # And a capability outside the global capability set must be denied for any
    # (role, cap) combination we can enumerate.
    for role, cap in itertools.product(ROLES, [UNKNOWN_CAP, "admin", "sudo", "*"]):
        assert decide(role, cap).decision is Decision.DENY, (role, cap)


def test_p1_unknown_role_is_denied():
    for cap in ALL_CAPS + [UNKNOWN_CAP]:
        assert decide(UNKNOWN_ROLE, cap).decision is Decision.DENY


def test_p1_consequential_never_granted():
    # No consequential capability may ever be auto-GRANTed to any role.
    for role in ROLES:
        for cap in _CONSEQUENTIAL:
            res = decide(role, cap)
            assert res.decision in (Decision.REQUIRE_APPROVAL, Decision.DENY)


def test_p1_no_implicit_allow_surface():
    # Exhaustive cross-product: the only non-DENY verdicts are the exact
    # declared (role, cap) cells. Every other cell is DENY (fail-closed).
    declared = {(r, c) for r, cs in _ROLE_CAPS.items() for c in cs}
    for role, cap in itertools.product(ROLES + [UNKNOWN_ROLE], ALL_CAPS + [UNKNOWN_CAP]):
        res = decide(role, cap)
        if (role, cap) in declared:
            assert res.decision is not Decision.DENY
        else:
            assert res.decision is Decision.DENY
