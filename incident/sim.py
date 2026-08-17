"""Incident-response simulation objects (domain-specific, NOT epistemic).

These mirror ``exchange.quant.probability.ProbabilityEstimate`` /
``exchange.quant.kelly.KellyProposal`` in role: they carry domain semantics
(the substrate must never see), and the adapter renders them into neutral
``fleet.epistemic`` artifacts. They import nothing from ``fleet.epistemic``,
``exchange``, or ``fleet.layers``.

``IncidentSignal`` — an observed/derived compromise signal (a detection result).
``RemediationPlan`` — a proposed remediation action with a triage priority
(maps to the D26 ``incident_remediate`` capability).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class IncidentSignal:
    """A domain detection result. Confidence/severity live here; the substrate
    never reads them. They are rendered into Evidence.payload as opaque data."""

    signal_id: str
    asset: str                      # e.g. "web-edge", "db-prod"
    is_compromised: bool            # detection verdict (domain fact)
    severity: str                   # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    confidence: float               # 0..1, domain-only, never an authority input
    method: str = "detector"        # detection method / model id

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")


@dataclass(frozen=True)
class RemediationPlan:
    """A proposed remediation, analogous to a KellyProposal (advisory only)."""

    plan_id: str
    asset: str
    action: str                    # e.g. "block_egress", "isolate", "snapshot"
    triage_priority: int           # 1 (highest) .. 5 (lowest); domain-only
    verification: str              # "VERIFIED" | "ASSERTED" | "HALLUCINATED" (D26 vocab)
    rationale: str = ""

    KIND: ClassVar[str] = "remediation_plan"

    @property
    def recommendation(self) -> str:
        """A neutral classification string (not a permission): REMEDIATE / HOLD."""
        return "REMEDIATE" if self.triage_priority <= 3 else "HOLD"
