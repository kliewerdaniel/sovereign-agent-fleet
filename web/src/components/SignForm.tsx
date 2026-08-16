"use client";

import { useState } from "react";
import { signApproval } from "@/lib/fleet";
import type { ApprovalRecord } from "@/lib/types";

// Client component: performs the real POST to the bridge and renders the
// returned signature. The signature is produced by fleet/layers/runtime
// Approval.sign with the human-approver Ed25519 key.
export function SignForm({
  requestId,
  agentId,
  actionId,
  capability,
  artifactHash,
}: {
  requestId: string;
  agentId: string;
  actionId: string;
  capability: string;
  artifactHash: string;
}) {
  const [state, setState] = useState<"idle" | "signing" | "done" | "error">("idle");
  const [approval, setApproval] = useState<ApprovalRecord | null>(null);
  const [err, setErr] = useState<string>("");

  async function doSign() {
    setState("signing");
    setErr("");
    try {
      const rec = await signApproval({
        request_id: requestId,
        agent_id: agentId,
        action_id: actionId,
        capability,
        artifact_hash: artifactHash,
        decision: "approve",
        reason: "human approved via bridge",
      });
      setApproval(rec);
      setState("done");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "sign failed");
      setState("error");
    }
  }

  if (state === "done" && approval) {
    return (
      <div className="card p-5 space-y-3 trust-boundary">
        <div className="flex items-center gap-2">
          <span className="pill pill-ok">signed</span>
          <span className="text-sm text-[var(--color-ok)]">
            Authorization granted — operator may execute.
          </span>
        </div>
        <div className="divider-label">Approval record</div>
        <pre className="text-xs mono text-[var(--color-ink-dim)] overflow-x-auto whitespace-pre-wrap">
          {JSON.stringify(approval, null, 2)}
        </pre>
        <div className="divider-label">human_sig (Ed25519)</div>
        <div className="text-[0.65rem] mono text-[var(--color-accent)] break-all">
          {approval.human_sig}
        </div>
        <a
          href={`/pipelines`}
          className="text-[var(--color-accent)] text-sm mono hover:underline"
        >
          back to pipelines →
        </a>
      </div>
    );
  }

  return (
    <div className="card p-5 space-y-3 trust-boundary">
      <button
        onClick={doSign}
        disabled={state === "signing"}
        className="w-full py-3 rounded-md bg-[var(--color-accent)] text-[var(--color-bg)] font-semibold text-sm disabled:opacity-50"
      >
        {state === "signing" ? "signing…" : "Sign & authorize execution"}
      </button>
      {state === "error" && (
        <div className="text-sm text-[var(--color-danger)] mono">{err}</div>
      )}
      <div className="text-xs text-[var(--color-ink-faint)] mono">
        POST /api/approve/{requestId}/sign — produces a genuine Ed25519
        ApprovalRecord signed by the human-approver key.
      </div>
    </div>
  );
}
