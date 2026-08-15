"""Sovereign Cognitive Architecture — cognition layer (D28).

This package is the **intelligence / evidence-formation** substrate that lives
UPSTREAM of Sovereign Agent Fleet governance. It produces structured evidence
and evaluation artifacts; it NEVER authorizes, decides, or executes.

HARD BOUNDARY (enforced by ``fleet/tests/test_boundary.py``):
    ``fleet/cognition`` may import ONLY:
        * ``fleet.crypto``            (sign / verify / audit primitives)
        * ``fleet.layers.handoff``    (emit signed Handoffs, read the ledger)
    It must NEVER import ``fleet.layers.gateway``, ``fleet.layers.policy``,
    ``fleet.layers.runtime``, ``fleet.layers.incident``, ``fleet.fin``,
    ``fleet.simenv``, or ``fleet.gcp`` — doing so is a build failure.

Rationale: the gateway/policy/risk/verifier already decide authorization.
If the cognition layer could import them it could *become* authority, breaking
the meta-invariant M0 ("no security invariant may depend on model behavior").
The import wall makes D-A / D-G structural facts, not conventions.
"""
from __future__ import annotations

from fleet.crypto.foundation import AgentCert, canonical_bytes, sha256
from fleet.layers.handoff import Handoff, HandoffError

__all__ = ["AgentCert", "canonical_bytes", "sha256", "Handoff", "HandoffError"]
