"""Incident authorization policy (use case: Incident Triage -> Authorized
Remediation, D26).

This module answers ONE question only:

    "Is this remediation authorized?"

It does NOT execute anything. The SimEnv answers "what happens when an
authorized action is executed?" (see fleet.simenv). Policy and SimEnv are kept
strictly separate: policy is a PURE, model-independent function of
(verification, severity, blast_radius, asset_class).

Authorization requires three INDEPENDENT gates to be satisfied; passing one
never implies passing another:

    Evidence   (D16): is the claim backed by verified observation?
    Capability (Gateway): does the cert permit this ACTION class?
    Policy     (here): is this action permitted on THIS target under these conditions?

Plus a human approval when the policy says HUMAN (bound to the exact transition).

The decision matrix (D26 sec.8):

    verification  severity  blast   asset          -> decision
    HALLUCINATION  --        --      --              BLOCKED
    VERIFIED       LOW       LOW     any             AUTO
    VERIFIED       LOW/MED   MED/HI  non-protected   HUMAN
    VERIFIED       HIGH      any     any             HUMAN
    VERIFIED       any       --      revenue-svc     HUMAN (always)
    VERIFIED       any       --      identity-svc
                                 (containment)        BLOCKED (prohibited)
    ASSERTED       any       any     any             HUMAN

Severity and evidence-confidence/verification are SEPARATE axes and are both
consumed here. A VERIFIED but HIGH-severity / high-blast action still escalates
to a human; a HALLUCINATION is always blocked regardless of severity.
"""
from __future__ import annotations

from enum import Enum
from enum import Enum
from typing import Tuple

from fleet.simenv.env import asset_class, blast_radius
from fleet.layers.verification import ASSERTED, HALLUCINATION, VERIFIED


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Authorization(str, Enum):
    AUTO = "AUTO"          # execute without human approval
    HUMAN = "HUMAN"        # requires a cryptographically-bound human approval
    BLOCKED = "BLOCKED"    # never permitted under this policy


def required_authorization(
    verification: str,
    severity: Severity,
    action: str,
    workload_id: str,
) -> Authorization:
    """Pure policy decision. See module docstring for the matrix.

    Args:
        verification: one of VERIFIED / ASSERTED / HALLUCINATION (D16 output)
        severity:     incident severity (Analyst-assigned, not the model's)
        action:       remediation action name (block_egress/isolate/quarantine)
        workload_id:  target workload (determines asset class)
    """
    # Evidence gate: a hallucinated (unbacked) claim is never authorized.
    if verification == HALLUCINATION:
        return Authorization.BLOCKED

    cls = asset_class(workload_id)
    blast = blast_radius(action)

    # Asset-class rules win before any severity nuance.
    if cls == "PROTECTED":
        # containment on the PROTECTED class is prohibited regardless of
        # evidence or severity (self-inflicted DoS defense). block_egress is a
        # LOW-blast non-containment action and remains permitted.
        if action in ("isolate", "quarantine"):
            return Authorization.BLOCKED
    if cls == "HIGH":
        # revenue-critical: always human, even LOW severity.
        return Authorization.HUMAN

    # General gradient for LOW / MEDIUM asset classes.
    if verification == VERIFIED:
        if severity == Severity.LOW and blast == "LOW":
            return Authorization.AUTO
        return Authorization.HUMAN  # LOW/MED severity, higher blast; or HIGH

    # ASSERTED evidence (medium confidence) always escalates to a human.
    if verification == ASSERTED:
        return Authorization.HUMAN

    return Authorization.BLOCKED


def bind_artifact(workload_id: str, action: str, target_state: str) -> str:
    """Content-address the exact consequential transition.

    Used as the approval ``artifact_hash`` so a human signature is bound to the
    precise action + target + resulting state (not vague text). Consumed by the
    existing D17 ``Approval.sign`` / ``verify_approval`` unchanged — the
    artifact_hash argument just now represents this transition."""
    from fleet.crypto.foundation import canonical_bytes, sha256

    return sha256(canonical_bytes(
        {"workload_id": workload_id, "action": action, "target_state": target_state}
    ))


def decision_summary(
    verification: str, severity: Severity, action: str, workload_id: str
) -> Tuple[Authorization, str]:
    """Return (decision, human-readable reason) for UI display."""
    auth = required_authorization(verification, severity, action, workload_id)
    reasons = {
        Authorization.AUTO: (
            f"VERIFIED + {severity.value} severity + "
            f"{blast_radius(action)} blast -> autonomous remediation permitted"
        ),
        Authorization.HUMAN: (
            f"{verification} + {severity.value} severity on "
            f"{asset_class(workload_id).value} asset -> human approval required"
        ),
        Authorization.BLOCKED: (
            "action BLOCKED by policy"
            + (" (protected asset)" if asset_class(workload_id) == "PROTECTED"
               and action in ("isolate", "quarantine") else "")
        ),
    }
    return auth, reasons[auth]
