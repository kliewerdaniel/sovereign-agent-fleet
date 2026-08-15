"""SimEnv — a deliberately tiny deterministic digital range.

The sophistication of Sovereign Agent Fleet lives in the *authority protocol*
surrounding a state transition, NOT in the simulated infrastructure. SimEnv is
boring on purpose: a dict of workloads, explicit states, a pure transition
function, and a verifiable result. No networking, no Kubernetes, no external
services.

SimEnv is the real target the Operator acts on. It is a SECOND LINE OF DEFENSE:
it refuses illegal transitions on its own, but the normal authority path rejects
unauthorized actions at the POLICY layer first (see fleet/layers/incident.py).
"""

from fleet.simenv.env import (
    ACTIONS,
    AssetClass,
    WorkloadState,
    SimEnv,
    blast_radius,
    asset_class,
    transition,
    WORKLOADS,
)

__all__ = [
    "WorkloadState",
    "AssetClass",
    "ACTIONS",
    "WORKLOADS",
    "transition",
    "SimEnv",
    "blast_radius",
    "asset_class",
]
