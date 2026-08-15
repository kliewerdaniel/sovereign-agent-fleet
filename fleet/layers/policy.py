"""Policy engine (Control Plane component #5 — 03.3 / D9 / D16).

Pure, deterministic decision logic. Maps (role, capability) -> an authority
outcome. The Gateway consults this; it never calls Gemini (13.1 / D15).

Outcomes:
  GRANT         - capability present; action auto-allowed (low-risk)
  REQUIRE_APPROVAL - capability present but consequential -> human sign-off (D17)
  DENY          - capability absent OR role not permitted -> hard deny

Capability vocabulary (12.1):
  researcher: emit_evidence
  analyst:    qualify, verify_gate
  operator:   prepare_artifact, crm_write (REQUIRE_APPROVAL), outreach_send (REQUIRE_APPROVAL)
  human:      approve_deny
  tool:       tool_result
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


class Decision(str, Enum):
    GRANT = "grant"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


@dataclass
class PolicyResult:
    decision: Decision
    policy_id: str
    reason: str


# Per-role capability grants. Absence => DENY.
_ROLE_CAPS: Dict[str, List[str]] = {
    "researcher": ["emit_evidence"],
    "analyst": ["qualify", "verify_gate"],
    "operator": ["prepare_artifact", "crm_write", "outreach_send", "incident_remediate"],
    "human": ["approve_deny"],
    "tool": ["tool_result"],
}

# Capabilities whose exercise is consequential and therefore require a human
# approval record before FINAL (D17, 03.4 Operator).
_CONSEQUENTIAL = {"crm_write", "outreach_send"}


def decide(role: str, capability: str) -> PolicyResult:
    allowed = _ROLE_CAPS.get(role, [])
    if capability not in allowed:
        return PolicyResult(
            decision=Decision.DENY,
            policy_id=f"cap:{role}:{capability}",
            reason=f"role '{role}' not granted capability '{capability}'",
        )
    if capability in _CONSEQUENTIAL:
        return PolicyResult(
            decision=Decision.REQUIRE_APPROVAL,
            policy_id=f"cap:{role}:{capability}",
            reason=f"capability '{capability}' is consequential; human approval required",
        )
    return PolicyResult(
        decision=Decision.GRANT,
        policy_id=f"cap:{role}:{capability}",
        reason=f"capability '{capability}' granted to role '{role}'",
    )
