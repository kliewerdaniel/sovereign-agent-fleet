"""SimEnv digital range — deterministic state machine.

Entities (4 workloads, one PROTECTED class):
  web-edge      LOW       internet-facing app (safe to auto-remediate)
  app-db        MEDIUM    database (isolation needs approval)
  revenue-svc   HIGH      revenue-critical (always human approval)
  identity-svc  PROTECTED auth / domain controller
                          isolate/quarantine PROHIBITED regardless of
                          evidence or severity (self-inflicted DoS defense)

States (one-directional, no restore workflow):
  RUNNING -> ISOLATED -> QUARANTINED ; RUNNING -> EGRESS_BLOCKED

Remediations (3, graded blast radius):
  block_egress  -> EGRESS_BLOCKED  (LOW)   still serves, cannot call out
  isolate       -> ISOLATED        (HIGH)  dark to network
  quarantine    -> QUARANTINED     (HIGH)  full containment

`transition(...)` is a PURE function: same inputs -> same outputs, no side
effects. It refuses illegal transitions (idempotent no-ops return the same
state; PROTECTED workloads refuse isolate/quarantine). The SimEnv class
wraps a mutable dict and records each applied change.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Tuple

from fleet.crypto.foundation import sha256


class WorkloadState(str, Enum):
    RUNNING = "RUNNING"
    EGRESS_BLOCKED = "EGRESS_BLOCKED"
    ISOLATED = "ISOLATED"
    QUARANTINED = "QUARANTINED"


class AssetClass(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    PROTECTED = "PROTECTED"


# workload_id -> asset class (blast-radius / criticality class)
WORKLOADS: Dict[str, AssetClass] = {
    "web-edge": AssetClass.LOW,
    "app-db": AssetClass.MEDIUM,
    "revenue-svc": AssetClass.HIGH,
    "identity-svc": AssetClass.PROTECTED,
}

# action -> (resulting state, blast radius class)
ACTIONS: Dict[str, Tuple[WorkloadState, str]] = {
    "block_egress": (WorkloadState.EGRESS_BLOCKED, "LOW"),
    "isolate": (WorkloadState.ISOLATED, "HIGH"),
    "quarantine": (WorkloadState.QUARANTINED, "HIGH"),
}

# isolate/quarantine are containment actions that must never target identity-svc
_PROTECTED_ACTIONS = ("isolate", "quarantine")


def asset_class(workload_id: str) -> AssetClass:
    return WORKLOADS[workload_id]


def blast_radius(action: str) -> str:
    return ACTIONS[action][1]


def transition(workload_id: str, state: WorkloadState, action: str) -> Tuple[WorkloadState, bool]:
    """Pure state-transition function. Returns (new_state, ok).

    Rules:
      * unknown workload / action -> rejected (ok=False), state unchanged
      * PROTECTED workload + containment action -> rejected (security invariant)
      * precondition: only RUNNING may be acted on
      * idempotent: acting on a workload already in the target state is a
        no-op success (ok=True, same state) — this is what makes replay safe
    """
    if workload_id not in WORKLOADS:
        return state, False
    if action not in ACTIONS:
        return state, False
    target_state, _ = ACTIONS[action]
    # Second-line-of-defense: containment on the PROTECTED class is always refused.
    if workload_id == "identity-svc" and action in _PROTECTED_ACTIONS:
        return state, False
    # Precondition: must currently be RUNNING (no double-containment / restore).
    if state != WorkloadState.RUNNING:
        # Idempotent no-op: already in the intended state is fine.
        if state == target_state:
            return state, True
        return state, False
    return target_state, True


@dataclass
class TransitionResult:
    workload_id: str
    action: str
    prev_state: WorkloadState
    new_state: WorkloadState
    ok: bool
    reason: str


class SimEnv:
    """Mutable digital range wrapping the pure transition function.

    Holds a dict of workload -> current state (all start RUNNING). `apply`
    executes a single remediation and returns a recorded TransitionResult.
    `snapshot()` gives the inspectable current state for UI/audit.
    """

    def __init__(self, seed: Dict[str, WorkloadState] | None = None):
        if seed is None:
            self._state = {wid: WorkloadState.RUNNING for wid in WORKLOADS}
        else:
            self._state = dict(seed)

    def apply(self, workload_id: str, action: str) -> TransitionResult:
        prev = self._state.get(workload_id, WorkloadState.RUNNING)
        new_state, ok = transition(workload_id, prev, action)
        reason = "ok" if ok else (
            "protected-asset" if (workload_id == "identity-svc" and action in _PROTECTED_ACTIONS)
            else "bad-precondition" if prev != WorkloadState.RUNNING
            else "unknown"
        )
        if ok:
            self._state[workload_id] = new_state
        return TransitionResult(
            workload_id=workload_id,
            action=action,
            prev_state=prev,
            new_state=new_state,
            ok=ok,
            reason=reason,
        )

    def snapshot(self) -> Dict[str, str]:
        return {wid: s.value for wid, s in self._state.items()}

    def state_of(self, workload_id: str) -> WorkloadState:
        return self._state.get(workload_id, WorkloadState.RUNNING)

    def apply_integrity_hash(self, workload_id: str, action: str) -> str:
        """sha256 over (workload_id, action, prev_state, new_state) — content
        address for the audit record of this transition."""
        res = self.apply(workload_id, action)
        payload = f"{res.workload_id}|{res.action}|{res.prev_state.value}|{res.new_state.value}"
        return sha256(payload.encode())
