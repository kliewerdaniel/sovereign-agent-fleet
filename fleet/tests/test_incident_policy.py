"""Incident authorization policy tests (Stage 3).

Every row of the D26 sec.8 matrix, plus property checks that the three
independent gates behave correctly and that evidence!=authority holds.
"""
import pytest

from fleet.layers.incident import (
    Authorization,
    Severity,
    bind_artifact,
    decision_summary,
    required_authorization,
)
from fleet.layers.verification import ASSERTED, HALLUCINATION, VERIFIED


# (verification, severity, action, workload_id, expected)
MATRIX = [
    (HALLUCINATION, Severity.LOW, "block_egress", "web-edge", Authorization.BLOCKED),
    (VERIFIED, Severity.LOW, "block_egress", "web-edge", Authorization.AUTO),
    (VERIFIED, Severity.LOW, "block_egress", "app-db", Authorization.AUTO),
    (VERIFIED, Severity.LOW, "isolate", "web-edge", Authorization.HUMAN),  # LOW sev, HIGH blast
    (VERIFIED, Severity.MEDIUM, "isolate", "web-edge", Authorization.HUMAN),
    (VERIFIED, Severity.HIGH, "block_egress", "web-edge", Authorization.HUMAN),
    (VERIFIED, Severity.HIGH, "quarantine", "app-db", Authorization.HUMAN),
    (VERIFIED, Severity.LOW, "isolate", "revenue-svc", Authorization.HUMAN),  # HIGH asset always
    (VERIFIED, Severity.LOW, "block_egress", "revenue-svc", Authorization.HUMAN),
    (VERIFIED, Severity.HIGH, "isolate", "revenue-svc", Authorization.HUMAN),
    (VERIFIED, Severity.LOW, "isolate", "identity-svc", Authorization.BLOCKED),  # protected
    (VERIFIED, Severity.HIGH, "quarantine", "identity-svc", Authorization.BLOCKED),
    (VERIFIED, Severity.LOW, "block_egress", "identity-svc", Authorization.AUTO),  # LOW blast ok
    (ASSERTED, Severity.LOW, "block_egress", "web-edge", Authorization.HUMAN),
    (ASSERTED, Severity.HIGH, "quarantine", "app-db", Authorization.HUMAN),
]


@pytest.mark.parametrize("ver,sev,act,wid,expected", MATRIX)
def test_matrix(ver, sev, act, wid, expected):
    assert required_authorization(ver, sev, act, wid) == expected


def test_hallucination_always_blocked_regardless_of_severity():
    for sev in Severity:
        for act in ("block_egress", "isolate", "quarantine"):
            for wid in ("web-edge", "app-db", "revenue-svc", "identity-svc"):
                assert required_authorization(HALLUCINATION, sev, act, wid) == Authorization.BLOCKED


def test_protected_asset_containment_blocked_but_low_blast_allowed():
    # isolation on identity-svc is BLOCKED...
    assert required_authorization(VERIFIED, Severity.HIGH, "isolate", "identity-svc") == Authorization.BLOCKED
    # ...but the LOW-blast non-containment action is permitted (AUTO).
    assert required_authorization(VERIFIED, Severity.LOW, "block_egress", "identity-svc") == Authorization.AUTO


def test_evidence_is_not_authority():
    # VERIFIED evidence that identity-svc is compromised does NOT grant the
    # power to isolate it — policy BLOCKS on the asset class, not the evidence.
    decision, reason = decision_summary(VERIFIED, Severity.HIGH, "isolate", "identity-svc")
    assert decision == Authorization.BLOCKED
    assert "protected" in reason


def test_severity_and_confidence_are_separate_axes():
    # Same LOW severity, different verification: VERIFIED -> AUTO (low blast),
    # ASSERTED -> HUMAN. This proves verification is an independent gate.
    assert required_authorization(VERIFIED, Severity.LOW, "block_egress", "web-edge") == Authorization.AUTO
    assert required_authorization(ASSERTED, Severity.LOW, "block_egress", "web-edge") == Authorization.HUMAN


def test_bind_artifact_is_stable_and_action_specific():
    h1 = bind_artifact("web-edge", "isolate", "ISOLATED")
    h2 = bind_artifact("web-edge", "isolate", "ISOLATED")
    assert h1 == h2
    assert isinstance(h1, str) and len(h1) == 64
    # different target -> different binding (no rebinding)
    assert bind_artifact("app-db", "isolate", "ISOLATED") != h1
    assert bind_artifact("web-edge", "quarantine", "QUARANTINED") != h1
