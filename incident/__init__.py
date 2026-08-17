"""Incident-response workload (second external domain, M0 generality proof).

This package is a *different* domain from the financial firm in ``exchange/``.
Its only job here is to supply domain objects (an ``IncidentSignal`` and a
``RemediationPlan``) that the substrate (``fleet.epistemic``) has never heard of,
so the adapter in ``incident/epistemic_adapter`` can translate them into the
neutral epistemic contract.

It deliberately shares NO imports with ``exchange/`` or ``fleet.epistemic`` —
those two trees must remain unaware of each other. The incident domain knows
only its own vocabulary and the neutral substrate's public types (via the
adapter). This is the clean second consumer M0 requires: if the substrate can
serve incident-response AND trading through the identical ``decide()`` without
either domain leaking in, the contract is genuinely domain-general.
"""
from __future__ import annotations

from .sim import IncidentSignal, RemediationPlan

__all__ = ["IncidentSignal", "RemediationPlan"]
