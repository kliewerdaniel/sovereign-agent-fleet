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
import os

from fleet.crypto.foundation import AuditTrail, IdentityRoot
from fleet.gcp.bridge import FanoutStore
from fleet.gcp.otel import OtelExporter
from fleet.layers.armor import (
    InjectionError,
    ToolEnvelope,
    redact_pii,
    redact_pii_deep,
    sanitize_tool_result,
    scan_injection,
    scan_pii,
    scan_pii_deep,
    verify_tool_envelope,
)
from fleet.layers.compliance import (
    ComplianceProof,
    build_compliance_proof,
    verify_compliance_proof,
)
from fleet.layers.consensus import ConsensusGate, same_verdict, unmapped_task
from fleet.layers.brain import (
    Brain,
    BrainSchemaError,
    DeterministicBrain,
    GemmaBrain,
    GeminiBrain,
    SchemaEnforcedBrain,
    assert_no_policy_leak,
    validate_brain_output,
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
    "scan_pii_deep",
    "redact_pii_deep",
    "ComplianceProof",
    "build_compliance_proof",
    "verify_compliance_proof",
    "ConsensusGate",
    "same_verdict",
    "unmapped_task",
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
    "Brain",
    "BrainSchemaError",
    "DeterministicBrain",
    "GemmaBrain",
    "GeminiBrain",
    "SchemaEnforcedBrain",
    "validate_brain_output",
    "assert_no_policy_leak",
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

    def __init__(self, master_secret: bytes, audit_key, store=None, now_fn=None,
                 bridge=None, otel=None, run_id="run-default"):
        self._now = now_fn or time.time
        self.run_id = run_id
        # Optional GCP replication (13.3): every audit write fans out to the
        # Firestore mirror. The bridge receives SIGNED artifacts only (D3/D6).
        self.bridge = bridge
        self.otel = otel or OtelExporter(use_sdk=False)

        def _on_put(coll, record, event):
            if coll == "ledger" and self.bridge is not None:
                # replicate the verbatim signed entry; mirror is byte-identical
                self.bridge.replicate(record)
                if self.otel is not None:
                    self.otel.emit_audit(self.run_id, record)

        audit_store = FanoutStore(store, on_put=_on_put) if store is not None else None
        self.root = IdentityRoot(master_secret)
        self.audit = AuditTrail(audit_key, store=audit_store)
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

    def rotate_root(self, new_master: bytes, ttl_seconds=86400):
        """Rotate the root key, re-sign live agents, emit signed audit (K1).

        Disaster recovery / compromise response. The CURRENT root must authorize
        the rotation (enforced in IdentityRoot.rotate_root). Live (unrevoked,
        unexpired) certs are re-issued under the new root with bumped cert_seq so
        the chain stays continuous. A signed `registry.root_rotate` entry records
        the epoch transition and the new root pubkey for verifiers.
        """
        new_root = IdentityRoot(new_master, salt=os.urandom(16))
        old_epoch = self.root.root_epoch
        # Gather live certs to re-sign.
        live = [self.registry._certs[a] for a in self.registry._certs]
        now = int(self._now())
        resigned = self.root.rotate_root(
            new_root, issued_at=now, expires_at=now + ttl_seconds, live_certs=live
        )
        # Rewrite the registry's live certs with the re-signed versions.
        for nc in resigned:
            self.registry._certs[nc.agent_id] = nc
        # Emit a signed audit entry recording the epoch transition and the new
        # root pubkey for verifiers.
        rotate_sig = getattr(self.root, "_rotation_sig", "")
        entry = self.audit.append({
            "kind": "registry.root_rotate",
            "who": "root",
            "reason": "root key rotation",
            "epoch_old": old_epoch,
            "epoch_new": self.root.root_epoch,
            "new_root_pub": self.root.root_public_pem.decode("utf-8"),
            "rotation_sig": rotate_sig,
        })
        # Invalidate Gateway idempotency cache — authority tokens were issued
        # under the old root and must not survive a root rotation (A3).
        self.gateway._cache.clear()
        return {"epoch_new": self.root.root_epoch,
                "resigned": [c.agent_id for c in resigned],
                "entry_id": entry["id"]}

    def verify_audit(self) -> bool:
        return self.audit.verify()
