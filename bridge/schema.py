"""Typed client contract for the Sovereign Agent Fleet frontend bridge.

These Pydantic models are the ONLY shapes the Next.js client consumes. They are
1:1 projections of real fleet record types (fleet.crypto.foundation.AgentCert,
fleet.layers.handoff.Handoff, fleet.crypto.chriscrypt.ledger.Ledger.append output,
fleet.layers.approval.Approval). No fields are invented — every attribute below
maps to a field that genuinely exists in the fleet package.

Cognition subordination rule (D28): a CognitionEnrichment is carried ONLY as an
optional, secondary field on a governance record. It can never appear as a
verdict and never shares the verification badge's weight in the UI.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Real record projections (ground-truth fields only)
# ---------------------------------------------------------------------------

Verification = Literal["VERIFIED", "ASSERTED", "HALLUCINATION"]
PolicyDecision = Literal["AUTO", "HUMAN", "BLOCKED"]
ApprovalDecision = Literal["approve", "reject"]


class AgentCert(BaseModel):
    agent_id: str
    role: str
    capabilities: List[str]
    issued_at: int
    expires_at: int
    cert_seq: int
    pubkey_pem: str
    root_sig: str


class SourcedEvidence(BaseModel):
    evidence_id: str
    agent_id: str
    citation: str
    extract: str
    source_hash: str
    retrieval_prov: Optional[Dict[str, Any]] = None
    collected_at: Optional[int] = None


class Predicate(BaseModel):
    claim: Optional[str] = None
    claim_type: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    severity: Optional[str] = None


class QualifiedIntel(BaseModel):
    intel_id: str
    agent_id: str
    target_id: str
    predicates: List[Predicate]
    confidence: float
    verification: Verification
    staleness_ok: bool


class ToolEnvelope(BaseModel):
    tool_id: str
    output_hash: str
    output: str
    tool_sig: str


class PolicyResult(BaseModel):
    decision: PolicyDecision
    reason: str


class ApprovalRecord(BaseModel):
    approval_id: str
    agent_id: str
    action_id: str
    capability: str
    artifact_hash: str
    decision: ApprovalDecision
    reason: str
    human_id: str
    human_sig: str
    ts: int


class AuditEntry(BaseModel):
    id: str
    seq: int
    prev: str
    ts: float
    kind: str
    payload: Dict[str, Any]
    sig: str


# ---------------------------------------------------------------------------
# D28 cognition enrichment — subordinated, never a verdict
# ---------------------------------------------------------------------------

class CognitionEnrichment(BaseModel):
    """CompiledKnowledge (SKC) — evidence, never authority.

    Carried as optional secondary context. The UI must render this at low
    visual weight (muted, outlined) and NEVER as a badge that could be mistaken
    for a governance verdict.
    """
    compile_id: str
    compiler_cert_id: str
    provenance: List[Dict[str, Any]]
    persona: Optional[str] = None
    confidence_note: Optional[str] = None


# ---------------------------------------------------------------------------
# Pipeline run aggregate
# ---------------------------------------------------------------------------

class PipelineStage(BaseModel):
    key: Literal[
        "proposal", "evidence", "verification", "capability",
        "policy", "approval", "environment", "audit"
    ]
    status: Literal["pending", "active", "passed", "blocked", "approved", "executed"]


class PipelineRun(BaseModel):
    run_id: str
    domain: Literal["sales", "incident", "financial"]
    stages: Dict[str, PipelineStage]
    proposal: Optional[AgentCert] = None
    evidence: List[SourcedEvidence] = Field(default_factory=list)
    intel: Optional[QualifiedIntel] = None
    tool: Optional[ToolEnvelope] = None
    policy: Optional[PolicyResult] = None
    approval: Optional[ApprovalRecord] = None
    environment_before: Optional[Dict[str, Any]] = None
    environment_after: Optional[Dict[str, Any]] = None
    audit_tail: List[AuditEntry] = Field(default_factory=list)
    cognition: Optional[CognitionEnrichment] = None
    verification: Optional[Verification] = None
    blocked: bool = False
    block_reason: Optional[str] = None
    needs_approval: bool = False


# ---------------------------------------------------------------------------
# Typed event schema streamed to the client over WebSocket.
# The client maps each event to a stage transition; it never infers stage from
# prose. (Field names are the canonical client event names from the plan.)
# ---------------------------------------------------------------------------

class RunStarted(BaseModel):
    type: Literal["RunStarted"] = "RunStarted"
    run_id: str
    domain: Literal["sales", "incident", "financial"]


class EvidenceEmitted(BaseModel):
    type: Literal["EvidenceEmitted"] = "EvidenceEmitted"
    run_id: str
    evidence: SourcedEvidence


class VerificationCompleted(BaseModel):
    type: Literal["VerificationCompleted"] = "VerificationCompleted"
    run_id: str
    intel: QualifiedIntel
    cognition: Optional[CognitionEnrichment] = None


class CapabilityChecked(BaseModel):
    type: Literal["CapabilityChecked"] = "CapabilityChecked"
    run_id: str
    envelope: ToolEnvelope


class PolicyDecisionEvent(BaseModel):
    type: Literal["PolicyDecision"] = "PolicyDecision"
    run_id: str
    decision: PolicyDecision
    reason: str


class ApprovalRequested(BaseModel):
    type: Literal["ApprovalRequested"] = "ApprovalRequested"
    run_id: str
    request_id: str
    proposal: Dict[str, Any]
    artifact_hash: str


class ApprovalSigned(BaseModel):
    type: Literal["ApprovalSigned"] = "ApprovalSigned"
    run_id: str
    request_id: str
    approval: ApprovalRecord


class ActionExecuted(BaseModel):
    type: Literal["ActionExecuted"] = "ActionExecuted"
    run_id: str
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None


class AuditEntryAppended(BaseModel):
    type: Literal["AuditEntryAppended"] = "AuditEntryAppended"
    run_id: str
    entry: AuditEntry


PipelineEvent = (
    RunStarted
    | EvidenceEmitted
    | VerificationCompleted
    | CapabilityChecked
    | PolicyDecisionEvent
    | ApprovalRequested
    | ApprovalSigned
    | ActionExecuted
    | AuditEntryAppended
)
