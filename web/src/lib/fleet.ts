// Thin client over the bridge REST surface. Every shape here is returned by
// the real fleet via the bridge — no transformation, no invented fields.

import { BRIDGE_BASE_URL, BRIDGE_PUBLIC_URL } from "./config";
import type { ApprovalRecord, ChainIntegrity, RunResult } from "./types";

async function getJson<T>(base: string, path: string): Promise<T> {
  const res = await fetch(base + path, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`bridge ${path} -> ${res.status}`);
  }
  return (await res.json()) as T;
}

// Server-side (no-store) reads.
export function fetchChainIntegrity(): Promise<ChainIntegrity> {
  return getJson<ChainIntegrity>(BRIDGE_BASE_URL, "/api/chain/integrity");
}

export function fetchAudit(limit = 50) {
  return getJson<{ entries: unknown[]; count: number; ledger_pubkey_pem: string }>(
    BRIDGE_BASE_URL,
    `/api/audit?limit=${limit}`,
  );
}

export interface RunSummary {
  run_id: string;
  verification: string;
  authorization: string;
  needs_approval: boolean;
  blocked: boolean;
  target: string;
  action: string;
  audit_count: number;
}

export async function fetchRuns(): Promise<{ runs: RunSummary[] }> {
  const data = await getJson<{ run_ids: string[]; runs: Record<string, RunSummary> }>(
    BRIDGE_BASE_URL,
    "/api/runs",
  );
  return { runs: Object.values(data.runs).sort((a, b) => (a.run_id < b.run_id ? 1 : -1)) };
}

export async function fetchRun(runId: string): Promise<RunResult> {
  return getJson<RunResult>(BRIDGE_BASE_URL, `/api/runs/${runId}/state`);
}

// Client-side (same-origin via next.config rewrite in dev/prod).
export function publicBridgeUrl(): string {
  return BRIDGE_PUBLIC_URL;
}

export async function runIncident(params: {
  verification?: string;
  severity?: string;
  workload_id?: string;
  action?: string;
}): Promise<RunResult> {
  const q = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null) as [string, string][],
  ).toString();
  const res = await fetch(`${BRIDGE_BASE_URL}/api/run/incident?${q}`, {
    method: "GET",
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`run incident -> ${res.status}`);
  return (await res.json()) as RunResult;
}

export async function fetchRunByAction(actionId: string): Promise<{
  run: RunResult;
  operator: { agent_id: string };
  human: { agent_id: string };
}> {
  return getJson(BRIDGE_BASE_URL, `/api/runs/by-action/${actionId}`);
}

export async function signApproval(body: {
  request_id: string;
  agent_id: string;
  action_id: string;
  capability: string;
  artifact_hash: string;
  decision?: string;
  reason?: string;
}): Promise<ApprovalRecord> {
  const res = await fetch(`/api/approve/${body.request_id}/sign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      agent_id: body.agent_id,
      action_id: body.action_id,
      capability: body.capability,
      artifact_hash: body.artifact_hash,
      decision: body.decision ?? "approve",
      reason: body.reason ?? "human approved via bridge",
    }),
  });
  if (!res.ok) throw new Error(`sign -> ${res.status}`);
  return (await res.json()) as ApprovalRecord;
}
