"""Thin Pydantic response models for the fleet API.

Serialize-only. Every field maps 1:1 to a field that genuinely exists on a
real fleet object (AgentCert, Ledger.append output, Approval, Gateway
decisions, VerificationResult). No crypto or policy logic lives here; the API
layer only projects what the control plane already computed.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Canonical literals (mirror the real fleet verdicts)
# ---------------------------------------------------------------------------
Verification = Literal["VERIFIED", "ASSERTED", "HALLUCINATION"]
PolicyDecision = Literal["AUTO", "HUMAN", "BLOCKED"]
GatewayDecision = Literal["grant", "require_approval", "deny"]
ApprovalDecision = Literal["approve", "reject"]

# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------
class AgentCert(BaseModel):
    agent_id: str
    role: str
    capabilities: List[str]
    issued_at: int
    expires_at: int
    cert_seq: int
    pubkey_pem: str
    root_sig: str


class AgentRecord(BaseModel):
    agent_id: str
    role: str
    capabilities: List[str]
    cert_seq: int
    status: Literal["active", "revoked"]
    issued_at: int
    expires_at: int


class AgentsSnapshot(BaseModel):
    root_epoch: int
    root_public_pem: str
    agents: List[AgentRecord]


# ---------------------------------------------------------------------------
# Audit ledger
# ---------------------------------------------------------------------------
class AuditEntry(BaseModel):
    id: str
    seq: int
    prev: str
    ts: float
    kind: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    sig: str


class LedgerPage(BaseModel):
    entries: List[AuditEntry]
    # opaque cursor: pass as `since` to fetch entries after it
    next_cursor: Optional[str] = None
    head: Optional[str] = None
    entry_count: int
    chain_valid: bool


class ChainIntegrity(BaseModel):
    valid: bool
    entry_count: int
    head: Optional[str] = None
    audit_pubkey_pem: str
    checked_at: int


# ---------------------------------------------------------------------------
# Policy decisions
# ---------------------------------------------------------------------------
class PolicyDecisionRow(BaseModel):
    seq: int
    ts: float
    agent_id: str
    capability: str
    decision: GatewayDecision          # grant | require_approval | deny
    require_approval: bool = False
    policy_id: Optional[str] = None
    reason: Optional[str] = None
    idempotency_key: Optional[str] = None


class PolicyLog(BaseModel):
    decisions: List[PolicyDecisionRow]


# ---------------------------------------------------------------------------
# Verification results
# ---------------------------------------------------------------------------
class VerificationRow(BaseModel):
    seq: int
    ts: float
    agent_id: str
    intel_id: str
    verification: Verification
    confidence: float
    target_id: str
    artifact_hash: Optional[str] = None


class VerificationLog(BaseModel):
    artifacts: List[VerificationRow]


# ---------------------------------------------------------------------------
# Approval queue / D17
# ---------------------------------------------------------------------------
class PendingApproval(BaseModel):
    request_id: str
    action_id: str
    capability: str
    agent_id: str
    artifact_hash: str
    reason: Optional[str] = None
    raised_at: float


class ApprovalResult(BaseModel):
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


class DecideRequest(BaseModel):
    approve: bool
    signer: str


# ---------------------------------------------------------------------------
# Adversarial demo runner
# ---------------------------------------------------------------------------
class BeatResult(BaseModel):
    beat: int
    name: str
    passed: bool
    detail: str
    # ledger entries appended by this beat (real signed records)
    ledger_entries: List[AuditEntry] = Field(default_factory=list)


class BeatListEntry(BaseModel):
    beat: int
    name: str
    summary: str


# ---------------------------------------------------------------------------
# Run trigger (additive — feeds the live ledger + approval console)
# ---------------------------------------------------------------------------
class RunRequest(BaseModel):
    verification: Verification = "VERIFIED"
    severity: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"
    workload_id: str = "web-edge"
    action: Literal["block_egress", "isolate", "quarantine"] = "block_egress"


class RunResult(BaseModel):
    run_id: str
    verification: Verification
    authorization: PolicyDecision
    needs_approval: bool
    blocked: bool
    reason: Optional[str] = None
    action_id: str
    capability: str
    artifact_hash: Optional[str] = None
    target: str
    action: str
    environment_before: Optional[Dict[str, Any]] = None
    environment_after: Optional[Dict[str, Any]] = None
    audit_tail: List[AuditEntry] = Field(default_factory=list)


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    live: bool = True
    note: str = "Live control plane — reads real signed ledger, writes call the fleet control plane."
