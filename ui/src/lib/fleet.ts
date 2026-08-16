// Typed client for the fleet/api control-plane service (fleet/api/app.py).
// All shapes mirror the Pydantic models in fleet/api/schema.py 1:1.
// The UI never signs or decides anything — it only reads and calls write
// endpoints that delegate to the real fleet control plane (D17).

export type Verification = "VERIFIED" | "ASSERTED" | "HALLUCINATION";
export type PolicyDecision = "AUTO" | "HUMAN" | "BLOCKED";
export type GatewayDecision = "grant" | "require_approval" | "deny";
export type ApprovalDecision = "approve" | "reject";

export interface AuditEntry {
  id: string;
  seq: number;
  prev: string;
  ts: number;
  kind: string;
  payload: Record<string, unknown>;
  sig: string;
}

export interface LedgerPage {
  entries: AuditEntry[];
  next_cursor: string | null;
  head: string | null;
  entry_count: number;
  chain_valid: boolean;
}

export interface ChainIntegrity {
  valid: boolean;
  entry_count: number;
  head: string | null;
  audit_pubkey_pem: string;
  checked_at: number;
}

export interface AgentRecord {
  agent_id: string;
  role: string;
  capabilities: string[];
  cert_seq: number;
  status: "active" | "revoked";
  issued_at: number;
  expires_at: number;
}

export interface AgentsSnapshot {
  root_epoch: number;
  root_public_pem: string;
  agents: AgentRecord[];
}

export interface PolicyDecisionRow {
  seq: number;
  ts: number;
  agent_id: string;
  capability: string;
  decision: GatewayDecision;
  require_approval: boolean;
  policy_id: string | null;
  reason: string | null;
  idempotency_key: string | null;
}

export interface VerificationRow {
  seq: number;
  ts: number;
  agent_id: string;
  intel_id: string;
  verification: Verification;
  confidence: number;
  target_id: string;
  artifact_hash: string | null;
}

export interface PendingApproval {
  request_id: string;
  action_id: string;
  capability: string;
  agent_id: string;
  artifact_hash: string;
  reason: string | null;
  raised_at: number;
}

export interface ApprovalResult {
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

export interface BeatListEntry {
  beat: number;
  name: string;
  summary: string;
}

export interface BeatResult {
  beat: number;
  name: string;
  passed: boolean;
  detail: string;
  ledger_entries: AuditEntry[];
}

export interface RunRequest {
  verification?: Verification;
  severity?: "LOW" | "MEDIUM" | "HIGH";
  workload_id?: string;
  action?: "block_egress" | "isolate" | "quarantine";
}

export interface RunResult {
  run_id: string;
  verification: Verification;
  authorization: PolicyDecision;
  needs_approval: boolean;
  blocked: boolean;
  reason: string | null;
  action_id: string;
  capability: string;
  artifact_hash: string | null;
  target: string;
  action: string;
  environment_before: Record<string, unknown> | null;
  environment_after: Record<string, unknown> | null;
  audit_tail: AuditEntry[];
}

export interface RevokeRotateResult {
  agent_id: string;
  cert_seq: number;
  revoked: boolean;
  discoverable: boolean;
  root_epoch: number;
  chain_valid: boolean;
  new_cert: {
    agent_id: string;
    role: string;
    capabilities: string[];
    cert_seq: number;
    issued_at: number;
    expires_at: number;
  };
}

export interface DecideRequest {
  approve: boolean;
  signer: string;
}

const BASE = process.env.NEXT_PUBLIC_FLEET_API ?? "http://127.0.0.1:8788";

async function jget<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return (await r.json()) as T;
}

async function jpost<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (!r.ok) {
    const txt = await r.text().catch(() => "");
    throw new Error(`${path} -> ${r.status}: ${txt}`);
  }
  return (await r.json()) as T;
}

export const fleetApi = {
  health: () => jget<{ status: string; live: boolean; note: string }>("/health"),
  agents: () => jget<AgentsSnapshot>("/agents"),
  ledger: (since?: string, limit = 50) =>
    jget<LedgerPage>(`/ledger?limit=${limit}${since ? `&since=${since}` : ""}`),
  chainIntegrity: () => jget<ChainIntegrity>("/chain/integrity"),
  policyLog: () => jget<{ decisions: PolicyDecisionRow[] }>("/policy-log"),
  verification: () => jget<{ artifacts: VerificationRow[] }>("/verification"),
  pending: () => jget<PendingApproval[]>("/approvals/pending"),
  decide: (requestId: string, body: DecideRequest) =>
    jpost<ApprovalResult>(`/approvals/${requestId}/decide`, body),
  runIncident: (body: RunRequest) => jpost<RunResult>("/run/incident", body),
  revokeRotate: (agentId: string) =>
    jpost<RevokeRotateResult>(`/agents/${agentId}/revoke-rotate`),
  beats: () => jget<BeatListEntry[]>("/demo/beats"),
  beat: (n: number) => jpost<BeatResult>(`/demo/beat/${n}`),
};
