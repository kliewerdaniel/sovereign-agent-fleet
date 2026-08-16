// Client-side contract types. These mirror bridge/schema.py 1:1 — the bridge
// projects ONLY real fleet record attributes, so these are honest shapes, not
// invented fields. Kept deliberately close to the Python Pydantic models.

export type Verification = "VERIFIED" | "ASSERTED" | "HALLUCINATION";
export type ApprovalDecision = "approve" | "deny";
export type Authorization = "AUTO" | "HUMAN" | "BLOCKED";

export interface AgentCert {
  agent_id: string;
  role: string;
  capabilities: string[];
  pubkey_pem: string;
  cert_seq: number;
  issued_by: string;
  issued_at: number;
  expires_at: number;
}

export interface SourcedEvidence {
  evidence_id: string;
  agent_id: string;
  query: string;
  content: string;
  source: string;
  retrieved_at: number;
  reliability: number;
}

export interface Predicate {
  claim: string;
  claim_type: string;
  evidence_refs: string[];
  severity: string;
  confidence?: number;
  verification?: Verification;
  staleness_ok?: boolean;
}

export interface QualifiedIntel {
  intel_id: string;
  agent_id: string;
  target_id: string;
  predicates: Predicate[];
  verification: Verification;
  confidence: number;
}

export interface ApprovalRecord {
  approval_id: string;
  agent_id: string;
  action_id: string;
  capability: string;
  artifact_hash: string;
  decision: ApprovalDecision;
  reason: string;
  human_id: string;
  human_sig: string;
  ts: number;
}

export interface AuditEntry {
  seq: number;
  prev: string;
  ts: number;
  kind: string;
  payload: Record<string, unknown>;
  sig: string;
  id: string;
}

export interface CognitionEnrichment {
  intel_id: string;
  model_id: string;
  advisory: string;
  confidence_spread: number;
  subordinated: boolean;
}

// --- Live pipeline events (WebSocket) ---------------------------------------

export type PipelineEventType =
  | "RunStarted"
  | "EvidenceEmitted"
  | "VerificationCompleted"
  | "CapabilityChecked"
  | "PolicyDecision"
  | "ApprovalRequested"
  | "ApprovalSigned"
  | "ActionExecuted"
  | "AuditEntryAppended";

export interface PipelineEvent {
  type: PipelineEventType;
  run_id: string;
  [key: string]: unknown;
}

// --- Trust-boundary-first: server computes this; client renders verbatim ---

export interface ChainIntegrity {
  valid: boolean;
  entry_count: number;
  head: string | null;
  checkpoint: {
    id: string;
    count: number;
    head: string;
    ts: number;
    sig: string;
  } | null;
  audit_pubkey_pem: string;
  checked_at: number;
}

export interface RunResult {
  run_id: string;
  agent_id: string;
  verification: Verification;
  authorization: Authorization;
  needs_approval: boolean;
  blocked: boolean;
  reason: string | null;
  action_id: string;
  capability: string;
  artifact_hash: string | null;
  target: string;
  action: string;
  environment_before: { workload_id: string; state: string };
  environment_after: { workload_id: string; state: string };
  evidence: Record<string, unknown>;
  evidence_id: string;
  audit_tail: AuditEntry[];
}
