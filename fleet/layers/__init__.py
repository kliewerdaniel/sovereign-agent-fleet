"""fleet.layers — Control Plane deterministic infrastructure (D9).

Components:
  registry  - Agent Registry (publish/version/discover/revoke/rotate)
  policy    - capability -> GRANT / REQUIRE_APPROVAL / DENY
  gateway   - the only issuer of authority; signed deny events; idempotency
  handoff   - signed cross-agent envelopes + D8 separation + evidence-ref resolve
  control   - ControlPlane assembler wiring the above over Phase 0 crypto
"""
from __future__ import annotations

import time

from fleet.crypto.foundation import AuditTrail, IdentityRoot
from fleet.layers.armor import (
    InjectionError,
    ToolEnvelope,
    redact_pii,
    sanitize_tool_result,
    scan_injection,
    scan_pii,
    verify_tool_envelope,
)
from fleet.layers.gateway import AuthorityResponse, Gateway, GatewayDeny
from fleet.layers.handoff import Handoff, HandoffError
from fleet.layers.policy import Decision, PolicyResult, decide
from fleet.layers.registry import AgentRegistry, RegistryError
from fleet.layers.runtime import (
    Analyst,
    Approval,
    MemBank,
    Operator,
    PublishedAgent,
    Researcher,
    RuntimeError_,
    Runtime,
    StubBrain,
)
from fleet.layers.verification import (
    ASSERTED,
    HALLUCINATION,
    VERIFIED,
    evaluate_intel,
    stamp,
)

__all__ = [
    "AgentRegistry",
    "RegistryError",
    "decide",
    "Decision",
    "PolicyResult",
    "Gateway",
    "GatewayDeny",
    "AuthorityResponse",
    "Handoff",
    "HandoffError",
    "InjectionError",
    "ToolEnvelope",
    "verify_tool_envelope",
    "sanitize_tool_result",
    "scan_injection",
    "scan_pii",
    "redact_pii",
    "Runtime",
    "Researcher",
    "Analyst",
    "Operator",
    "Approval",
    "MemBank",
    "StubBrain",
    "PublishedAgent",
    "RuntimeError_",
    "evaluate_intel",
    "stamp",
    "VERIFIED",
    "ASSERTED",
    "HALLUCINATION",
    "ControlPlane",
]


class ControlPlane:
    """Wires the Control Plane components over a Phase 0 IdentityRoot + audit key.

    Local-first: keys never leave this object (D3/D6). Only signed/verifiable
    artifacts (certs, deny events, handoff envelopes) cross to GCP later.

    A single clock is shared by the Registry and Gateway so that "now" means the
    same instant everywhere (expiry, idempotency, audit timestamps). Advance it
    with `advance_clock` for deterministic tests.
    """

    def __init__(self, master_secret: bytes, audit_key, store=None, now_fn=None):
        self._now = now_fn or time.time
        self.root = IdentityRoot(master_secret)
        self.audit = AuditTrail(audit_key, store=store)
        self.registry = AgentRegistry(self.root, self.audit, now_fn=self._now)
        self.gateway = Gateway(
            self.registry, self.audit, signing_key=audit_key,
            signing_agent_id="gateway", now_fn=self._now,
        )

    def advance_clock(self, t: float) -> None:
        """Set the shared clock to a fixed instant (deterministic testing)."""
        fixed = lambda: t  # noqa: E731
        self._now = fixed
        self.registry._now = fixed
        self.gateway._now = fixed

    def publish_agent(self, agent_id, role, capabilities, ttl_seconds=86400):
        pa = self.registry.publish(agent_id, role, capabilities, ttl_seconds)
        return PublishedAgent(agent_id=agent_id, role=role, cert=pa.cert, key=pa.key)

    def request_authority(self, cert, capability, idempotency_key=None):
        return self.gateway.request_authority(cert, capability, idempotency_key)

    def verify_audit(self) -> bool:
        return self.audit.verify()
