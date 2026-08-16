import Link from "next/link";
import { fetchRunByAction } from "@/lib/fleet";
import { VerifyPill, AuthPill } from "@/components/StatusPills";
import { SignForm } from "@/components/SignForm";

export const dynamic = "force-dynamic";

// The exact fields the bridge signs (mirrors fleet/layers/runtime.Approval.sign).
// Rendered verbatim so a human can inspect the bytes before signing.
function signingPayload(run: {
  agent_id: string;
  action_id: string;
  capability: string;
  artifact_hash: string | null;
}) {
  return {
    agent_id: run.agent_id,
    action_id: run.action_id,
    capability: run.capability,
    artifact_hash: run.artifact_hash ?? "",
    decision: "approve",
    reason: "human approved via bridge",
    human_id: "",
  };
}

export default async function ApprovePage({
  params,
}: {
  params: Promise<{ requestId: string }>;
}) {
  const { requestId } = await params;
  let ctx: Awaited<ReturnType<typeof fetchRunByAction>> | null = null;
  let error: string | null = null;
  try {
    ctx = await fetchRunByAction(requestId);
  } catch {
    error = `no pending approval for request ${requestId}`;
  }

  const run = ctx?.run;
  const humanId = ctx?.human.agent_id ?? "";
  const payload = run ? signingPayload(run) : null;

  return (
    <div className="max-w-2xl mx-auto px-5 py-8 space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/pipelines" className="text-[var(--color-accent)] text-sm mono">
          ← pipelines
        </Link>
        <span className="divider-label">D17 · human approval</span>
      </div>

      <header className="card p-5 space-y-1">
        <div className="text-lg font-semibold">Sign human approval</div>
        <div className="text-sm text-[var(--color-ink-dim)]">
          You are the human authority on the trust boundary. Below is the exact
          artifact the operator deferred to you. Your Ed25519 key signs it — the
          signature, not this page, is what authorizes execution.
        </div>
      </header>

      {error || !run || !payload ? (
        <div className="card p-6 text-[var(--color-warn)] mono text-sm">{error}</div>
      ) : (
        <>
          <div className="card p-4 space-y-3">
            <div className="flex items-center gap-3 flex-wrap">
              <VerifyPill v={run.verification} />
              <AuthPill auth={run.authorization} needs={run.needs_approval} />
              <span className="text-[var(--color-ink-dim)] text-sm">
                {run.target} · {run.action}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <div className="divider-label mb-1">Operator (agent)</div>
                <div className="mono text-[var(--color-ink)]">{run.agent_id}</div>
              </div>
              <div>
                <div className="divider-label mb-1">Human signer</div>
                <div className="mono text-[var(--color-ink)]">{humanId}</div>
              </div>
              <div>
                <div className="divider-label mb-1">Action id (idempotency)</div>
                <div className="mono text-[var(--color-ink)] break-all">
                  {run.action_id}
                </div>
              </div>
              <div>
                <div className="divider-label mb-1">Capability</div>
                <div className="mono text-[var(--color-ink)]">{run.capability}</div>
              </div>
            </div>
          </div>

          <div className="card p-4 space-y-2">
            <div className="divider-label">Canonical signing payload</div>
            <pre className="text-xs mono text-[var(--color-ink-dim)] overflow-x-auto whitespace-pre-wrap">
              {JSON.stringify(payload, null, 2)}
            </pre>
            <div className="divider-label">Artifact hash (evidence binding)</div>
            <div className="text-[0.65rem] mono text-[var(--color-ink-faint)] break-all">
              {run.artifact_hash ?? "—"}
            </div>
          </div>

          <SignForm
            requestId={requestId}
            agentId={run.agent_id}
            actionId={run.action_id}
            capability={run.capability}
            artifactHash={run.artifact_hash ?? ""}
          />
        </>
      )}
    </div>
  );
}
