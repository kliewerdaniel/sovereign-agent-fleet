"""SimEnv digital range — deterministic state machine tests (Stage 2).

Pure transition function + SimEnv wrapper. One-directional states, graded blast
radius, idempotent no-ops, and the PROTECTED identity-svc invariant.
"""
from fleet.simenv.env import (
    AssetClass,
    SimEnv,
    WorkloadState,
    asset_class,
    blast_radius,
    transition,
)


def test_initial_state_all_running():
    env = SimEnv()
    assert env.snapshot() == {
        "web-edge": "RUNNING",
        "app-db": "RUNNING",
        "revenue-svc": "RUNNING",
        "identity-svc": "RUNNING",
    }


def test_block_egress_runs_to_egress_blocked():
    env = SimEnv()
    res = env.apply("web-edge", "block_egress")
    assert res.ok is True
    assert res.prev_state == WorkloadState.RUNNING
    assert res.new_state == WorkloadState.EGRESS_BLOCKED
    assert env.state_of("web-edge") == WorkloadState.EGRESS_BLOCKED


def test_isolate_runs_to_isolated():
    env = SimEnv()
    res = env.apply("app-db", "isolate")
    assert res.ok is True
    assert res.new_state == WorkloadState.ISOLATED


def test_quarantine_runs_to_quarantined():
    env = SimEnv()
    res = env.apply("app-db", "quarantine")
    assert res.ok is True
    assert res.new_state == WorkloadState.QUARANTINED


def test_idempotent_noop_on_same_target_state():
    env = SimEnv()
    env.apply("web-edge", "block_egress")
    # applying again is a safe no-op (already in target state)
    res = env.apply("web-edge", "block_egress")
    assert res.ok is True
    assert res.new_state == WorkloadState.EGRESS_BLOCKED


def test_no_double_containment_from_non_running():
    env = SimEnv()
    env.apply("app-db", "isolate")  # -> ISOLATED
    # containment from ISOLATED to QUARANTINED is not a direct transition
    res = env.apply("app-db", "quarantine")
    assert res.ok is False
    assert res.reason == "bad-precondition"
    assert env.state_of("app-db") == WorkloadState.ISOLATED


def test_identity_svc_protected_rejects_isolate():
    env = SimEnv()
    res = env.apply("identity-svc", "isolate")
    assert res.ok is False
    assert res.reason == "protected-asset"
    assert env.state_of("identity-svc") == WorkloadState.RUNNING


def test_identity_svc_protected_rejects_quarantine():
    env = SimEnv()
    res = env.apply("identity-svc", "quarantine")
    assert res.ok is False
    assert env.state_of("identity-svc") == WorkloadState.RUNNING


def test_block_egress_on_identity_svc_allowed_low_blast():
    # block_egress is LOW blast and is NOT a containment action, so it is
    # permitted on the PROTECTED class (it does not take down auth).
    env = SimEnv()
    res = env.apply("identity-svc", "block_egress")
    assert res.ok is True
    assert res.new_state == WorkloadState.EGRESS_BLOCKED


def test_transition_pure_unknown_workload():
    s, ok = transition("does-not-exist", WorkloadState.RUNNING, "isolate")
    assert ok is False
    assert s == WorkloadState.RUNNING


def test_transition_pure_unknown_action():
    s, ok = transition("web-edge", WorkloadState.RUNNING, "nuke")
    assert ok is False


def test_asset_classes():
    assert asset_class("web-edge") == AssetClass.LOW
    assert asset_class("app-db") == AssetClass.MEDIUM
    assert asset_class("revenue-svc") == AssetClass.HIGH
    assert asset_class("identity-svc") == AssetClass.PROTECTED


def test_blast_radius_metadata():
    assert blast_radius("block_egress") == "LOW"
    assert blast_radius("isolate") == "HIGH"
    assert blast_radius("quarantine") == "HIGH"


def test_integrity_hash_stable_for_same_transition():
    env = SimEnv()
    h1 = env.apply_integrity_hash("web-edge", "block_egress")
    env2 = SimEnv()
    h2 = env2.apply_integrity_hash("web-edge", "block_egress")
    assert h1 == h2
    assert isinstance(h1, str) and len(h1) == 64
