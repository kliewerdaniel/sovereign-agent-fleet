"""Adapter that drives the REAL fleet package and projects its genuine records
into the typed client schema (bridge/schema.py).

Nothing here invents fields. Every projection reads attributes that genuinely
exist on fleet objects (AgentCert, Handoff payloads, Ledger.append output,
Approval). The bridge runs the Researcher -> Analyst -> Operator pipeline
against the live fleet and emits typed PipelineEvents as the audit ledger grows.

Cognition (D28): if a CompiledKnowledge enrichment is produced for an intel, it
is attached ONLY as the subordinated `CognitionEnrichment` on the
VerificationCompleted event — never as a verdict.
"""
from __future__ import annotations

import json
import os
import secrets
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from fleet.crypto.chriscrypt.store import JsonStore
from fleet.crypto.foundation import IdentityRoot
from fleet.layers import (
    Approval,
    Analyst,
    ControlPlane,
    MemBank,
    Operator,
    Researcher,
    Runtime,
    StubBrain,
    ToolEnvelope,
    evaluate_intel,
    stamp,
)
from fleet.layers.incident import Authorization, Severity, decision_summary, required_authorization
from fleet.layers.verification import ASSERTED, HALLUCINATION, VERIFIED
from fleet.simenv.env import SimEnv, ACTIONS

from .schema import (
    ActionExecuted,
    AgentCert,
    ApprovalDecision,
    ApprovalRecord,
    ApprovalSigned,
    AuditEntry,
    AuditEntryAppended,
    CapabilityChecked,
    CognitionEnrichment,
    EvidenceEmitted,
    PipelineEvent,
    PolicyDecisionEvent,
    Predicate,
    QualifiedIntel,
    RunStarted,
    SourcedEvidence,
    ToolEnvelope as ToolEnvelopeSchema,
    Verification,
    VerificationCompleted,
)

# Map fleet audit `kind` -> UI stage key (the client never infers stage from prose).
AUDIT_KIND_TO_STAGE = {
    "researcher.emit": "evidence",
    "analyst.qualify": "verification",
    "operator.needs_approval": "approval",
    "operator.final": "environment",
    "operator.blocked": "audit",
    "operator.approval.rejected": "audit",
    "operator.approval.signed": "approval",
    "runtime.injection": "evidence",
    "researcher.pii_redacted": "evidence",
}


def _make_audit_key(seed: bytes) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(
        HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"fleet:audit").derive(seed)
    )


def _make_mem_kek(seed: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"fleet:mem").derive(seed)


def _proj_cert(cert) -> AgentCert:
    return AgentCert(
        agent_id=cert.agent_id, role=cert.role, capabilities=list(cert.capabilities),
        issued_at=cert.issued_at, expires_at=cert.expires_at, cert_seq=cert.cert_seq,
        pubkey_pem=cert.pubkey_pem, root_sig=cert.root_sig,
    )


def _proj_evidence(payload: Dict[str, Any]) -> SourcedEvidence:
    return SourcedEvidence(
        evidence_id=payload["evidence_id"], agent_id=payload["agent_id"],
        citation=payload.get("citation", ""), extract=payload.get("extract", ""),
        source_hash=payload.get("source_hash", ""),
        retrieval_prov=payload.get("retrieval_prov"), collected_at=payload.get("collected_at"),
    )


def _proj_intel(payload: Dict[str, Any]) -> QualifiedIntel:
    preds = [
        Predicate(
            claim=p.get("claim"), claim_type=p.get("claim_type"),
            evidence_refs=list(p.get("evidence_refs", [])),
            confidence=p.get("confidence"), severity=p.get("severity"),
        )
        for p in payload.get("predicates", [])
    ]
    return QualifiedIntel(
        intel_id=payload["intel_id"], agent_id=payload["agent_id"],
        target_id=payload.get("target_id", ""), predicates=preds,
        confidence=float(payload.get("confidence", 0.0)),
        verification=payload.get("verification"),
        staleness_ok=bool(payload.get("staleness_ok")),
    )


def _proj_tool_env(env: ToolEnvelope) -> ToolEnvelopeSchema:
    return ToolEnvelopeSchema(
        tool_id=env.tool_id, output_hash=env.output_hash,
        output=env.output.decode("utf-8", "replace"), tool_sig=env.tool_sig,
    )


def _proj_approval(a: Approval) -> ApprovalRecord:
    return ApprovalRecord(
        approval_id=a.approval_id, agent_id=a.agent_id, action_id=a.action_id,
        capability=a.capability, artifact_hash=a.artifact_hash, decision=a.decision,
        reason=a.reason, human_id=a.human_id, human_sig=a.human_sig, ts=a.ts,
    )


def _proj_cognition(compile_payload: Dict[str, Any]) -> Optional[CognitionEnrichment]:
    if not compile_payload:
        return None
    return CognitionEnrichment(
        compile_id=compile_payload.get("compile_id", ""),
        compiler_cert_id=compile_payload.get("compiler_cert_id", ""),
        provenance=compile_payload.get("provenance", []),
        persona=compile_payload.get("persona"),
        confidence_note=compile_payload.get("confidence_note"),
    )


def _proj_audit(entry: Dict[str, Any]) -> AuditEntry:
    return AuditEntry(
        id=entry.get("id", ""), seq=entry.get("seq", 0), prev=entry.get("prev", ""),
        ts=entry.get("ts", 0.0), kind=entry.get("kind", ""),
        payload=entry.get("payload", {}), sig=entry.get("sig", ""),
    )


class FleetAdapter:
    """Owns one fleet ControlPlane and runs real pipelines on demand."""

    def __init__(self, master_secret: bytes, audit_seed: bytes, now_fn=None):
        self.master = master_secret
        self.audit = _make_audit_key(audit_seed)
        self.now_fn = now_fn
        # In-memory-backed JSON ledger (temp file, process-local).
        self._store_fd, store_path = tempfile.mkstemp(suffix=".json", prefix="fleet-bridge-")
        with os.fdopen(self._store_fd, "w") as fh:
            fh.write("{}")
        self.store = JsonStore(store_path)
        self.cp = ControlPlane(master_secret, self.audit, store=self.store, now_fn=self.now_fn)
        # Publish the fleet + a human approver so D17 signing is possible.
        self.researcher = self.cp.publish_agent("researcher", "researcher", ["gather"])
        self.analyst = self.cp.publish_agent("analyst", "analyst", ["qualify"])
        self.operator = self.cp.publish_agent("operator", "operator", ["incident_remediate", "trade_execute"])
        self.human = self.cp.publish_agent("human-approver", "human", ["approve"])

    # -- helpers -----------------------------------------------------------

    def audit_entries(self) -> List[Dict[str, Any]]:
        # JsonStore keys ledger entries by id; the signed checkpoint id is excluded.
        return [e for e in self.store.find("ledger") if e.get("id") != "checkpoint"]

    def audit_tail(self, limit: int = 50) -> List[AuditEntry]:
        all_ = [e for e in self.audit_entries() if e.get("id") != "checkpoint"]
        return [_proj_audit(e) for e in all_[-limit:]]

    # -- pipeline runner ---------------------------------------------------

    def run_incident(
        self,
        emit: Callable[[PipelineEvent], None],
        *,
        verification: str = VERIFIED,
        severity: str = "LOW",
        workload_id: str = "web-edge",
        action: str = "block_egress",
        query: str = "why is the web-edge host beaconing?",
    ) -> Dict[str, Any]:
        """Run a real R->A->O incident-remediation pipeline against the fleet.

        `verification`/`severity` select which policy path the demo exercises
        (VERIFIED+LOW+LOW-blast -> AUTO; HALLUCINATION -> BLOCKED; ASSERTED ->
        HUMAN). The Operator + SimEnv + audit ledger are the genuine fleet.
        The caller receives `needs_approval`/policy so it can request a human
        signature via the bridge's sign endpoint.
        """
        run_id = f"run_{secrets.token_hex(4)}"
        simenv = SimEnv()
        rt = Runtime(self.cp, MemBank(_make_mem_kek(self.master)), brain=StubBrain(), store=self.store, now_fn=self.now_fn)
        res = Researcher(self.researcher, rt)
        ana = Analyst(self.analyst, rt)
        op = Operator(self.operator, rt)

        emit(RunStarted(run_id=run_id, domain="incident"))  # type: ignore[call-arg]

        # 1. Researcher gathers verified evidence (synthetic but schema-valid).
        evidence_payload = {
            "evidence_id": f"ev_{secrets.token_hex(6)}",
            "agent_id": self.researcher.agent_id,
            "citation": "sim:web-edge:siem",
            "extract": f"{workload_id} exhibiting anomalous egress volume (severity {severity}).",
            "source_hash": secrets.token_hex(16),
            "retrieval_prov": {"tool": "siem", "ts": int(self.now_fn() if self.now_fn else time.time()), "query": query},
            "collected_at": int(self.now_fn() if self.now_fn else time.time()),
        }
        ev_handoff = type("H", (), {
            "sender_cert": self.researcher.cert,
            "payload_type": "SourcedEvidence",
            "payload": evidence_payload,
            "sender_sig": "local",
            "to_dict": lambda self=evidence_payload: evidence_payload,  # lightweight stand-in
        })()
        # Use the real Handoff builder so signatures are genuine.
        from fleet.layers.handoff import Handoff as RealHandoff
        ev_handoff = RealHandoff.make(
            self.researcher.cert, self.researcher.key, "SourcedEvidence", evidence_payload
        )
        rt.record_evidence_meta(evidence_payload["evidence_id"], int(self.now_fn() if self.now_fn else time.time()))
        emit(EvidenceEmitted(run_id=run_id, evidence=_proj_evidence(ev_handoff.payload)))  # type: ignore[call-arg]

        # 2. Analyst qualifies -> D16 verification gate stamps the intel.
        # The verification verdict is COMPUTED from evidence weight, not copied
        # from the demo param. We pick a claim_type/ref shape that lands each
        # demo path on the real verdict:
        #   VERIFIED      -> 'remediation' (weight 1) + 1 ref  -> conf 1.0
        #   ASSERTED      -> 'icp_fit' (weight 2)   + 1 ref  -> conf 0.5 (<0.6)
        #   HALLUCINATION -> non-resolving ref (handled below)
        claim_type = "icp_fit" if verification == ASSERTED else "remediation"
        predicates = [{
            "claim": f"{workload_id} requires remediation via {action}",
            "claim_type": claim_type,
            "evidence_refs": [evidence_payload["evidence_id"]],
            "severity": severity,
        }]
        if verification == HALLUCINATION:
            # Real D16 HALLUCINATION path: the intel cites a NON-RESOLVING
            # evidence id. We stamp it directly via evaluate_intel (the same
            # call the Analyst's gate uses) rather than ana.qualify, because
            # Handoff.consume would refuse the non-resolving ref at the envelope
            # boundary — which is exactly the fleet's behavior. evaluate_intel
            # sees zero VALID refs -> HALLUCINATION verdict, never executed.
            from fleet.layers.verification import stamp as _stamp
            base_intel = {
                "intel_id": f"iq_{secrets.token_hex(6)}",
                "agent_id": self.analyst.agent_id,
                "target_id": workload_id,
                "predicates": [{
                    "claim": predicates[0]["claim"],
                    "claim_type": "remediation",
                    "evidence_refs": ["ev_nonexistent"],
                    "severity": severity,
                }],
            }
            intel = _stamp(base_intel, {}, int(self.now_fn() if self.now_fn else time.time()))
            intel_handoff = RealHandoff.make(
                self.analyst.cert, self.analyst.key, "QualifiedIntel", intel
            )
        else:
            intel_handoff = ana.qualify(ev_handoff, predicates)
            intel = intel_handoff.payload
        emit(VerificationCompleted(run_id=run_id, intel=_proj_intel(intel)))  # type: ignore[call-arg]

        # 3. Policy decision (pure function of verification/severity/blast/asset).
        auth = required_authorization(intel["verification"], Severity(severity), action, workload_id)
        reason = decision_summary(intel["verification"], Severity(severity), action, workload_id)[1]
        emit(PolicyDecisionEvent(run_id=run_id, decision=auth.value, reason=reason))  # type: ignore[call-arg]

        # 4. Operator stage.
        idempotency_key = f"act_{secrets.token_hex(6)}"
        before = {"workload_id": workload_id, "state": simenv.state_of(workload_id).value}

        if intel["verification"] == HALLUCINATION:
            # The fleet blocks HALLUCINATION intel at the envelope boundary
            # (Handoff.consume refuses non-resolving refs) — the Operator never
            # executes it. Mirror that: emit a blocked outcome, no state change.
            self.cp.audit.append({
                "kind": "operator.blocked", "who": self.operator.agent_id,
                "reason": "hallucination-intel", "gate": "evidence",
                "target": workload_id, "action": action,
            })
            result = {"final": False, "blocked": True, "reason": "HALLUCINATION intel rejected"}
        else:
            result = op.act(
                intel_handoff, artifact_text=f"Remediate {workload_id} via {action}",
                capability="incident_remediate", idempotency_key=idempotency_key,
                target_workload=workload_id, action_name=action, simenv=simenv,
            )
        after = {"workload_id": workload_id, "state": simenv.state_of(workload_id).value}
        emit(ActionExecuted(run_id=run_id, before=before, after=after))  # type: ignore[call-arg]

        # 5. Stream the new audit tail (real signed entries).
        for e in self.audit_tail(limit=8):
            emit(AuditEntryAppended(run_id=run_id, entry=e))  # type: ignore[call-arg]

        return {
            "run_id": run_id,
            "agent_id": self.operator.agent_id,
            "verification": intel["verification"],
            "authorization": auth.value,
            "needs_approval": result.get("needs_approval", False),
            "blocked": result.get("blocked", False),
            "reason": result.get("reason"),
            "action_id": idempotency_key,
            "capability": "incident_remediate",
            "artifact_hash": result.get("artifact_hash"),
            "target": workload_id,
            "action": action,
            "environment_before": before,
            "environment_after": after,
            "audit_tail": [e.model_dump() for e in self.audit_tail(limit=8)],
        }

    def sign_approval(
        self,
        request_id: str,
        agent_id: str,
        action_id: str,
        capability: str,
        artifact_hash: str,
        decision: str = "approve",
        reason: str = "human approved via bridge",
    ) -> ApprovalRecord:
        """Produce a genuine Ed25519 human ApprovalRecord (D17)."""
        ts = int(self.now_fn() if self.now_fn else time.time())
        approval = Approval.sign(
            self.human.cert, self.human.key, agent_id, action_id,
            capability, artifact_hash, decision, reason, ts,
        )
        self.cp.audit.append({
            "kind": "operator.approval.signed", "who": "human-approver",
            "request_id": request_id, "action_id": action_id,
            "capability": capability, "artifact_hash": artifact_hash,
            "decision": decision, "reason": reason,
        })
        return _proj_approval(approval)
