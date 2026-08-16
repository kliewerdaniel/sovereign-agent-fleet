import Link from "next/link";
import { fetchRun } from "@/lib/fleet";
import { AuthPill, VerifyPill } from "@/components/StatusPills";
import { AuditStage } from "@/components/AuditStage";

export const dynamic = "force-dynamic";

// Map real audit `kind`s to the 5 governance stages. These are genuine fleet
// ledger kinds — not invented.
// Map real fleet audit `kind`s to the 6 governance stages (derived from
// bridge/fleet_adapter.AUDIT_KIND_TO_STAGE + observed run ledger kinds).
const STAGE_OF: Record<string, string> = {
  "researcher.emit": "evidence",
  "analyst.qualify": "verification",
  "gateway.grant": "policy",
  "gateway.deny": "policy",
  "operator.needs_approval": "approval",
  "operator.approval.signed": "approval",
  "operator.final": "action",
  "operator.blocked": "audit",
  "operator.approval.rejected": "audit",
};

const STAGE_LABEL: Record<string, { label: string; agent: string }> = {
  evidence: { label: "Evidence", agent: "researcher" },
  verification: { label: "Verification", agent: "analyst" },
  policy: { label: "Policy decision", agent: "control-plane" },
  approval: { label: "Human approval", agent: "human-approver" },
  action: { label: "Action execution", agent: "operator" },
  audit: { label: "Audit / blocked", agent: "operator" },
};

export default async function RunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  let run = null;
  try {
    run = await fetchRun(runId);
  } catch {
    run = null;
  }

  if (!run) {
    return (
      <div className="max-w-3xl mx-auto px-5 py-10">
        <div className="card p-6 text-[var(--color-warn)] mono text-sm">
          unknown run <span className="text-[var(--color-ink)]">{runId}</span> —
          it may have aged out of the bridge process memory.
        </div>
        <Link href="/pipelines" className="text-[var(--color-accent)] text-sm mono">
          ← pipelines
        </Link>
      </div>
    );
  }

  const stages = (["evidence", "verification", "policy", "approval", "action", "audit"] as const).map(
    (key) => ({
      key,
      label: STAGE_LABEL[key].label,
      agent: STAGE_LABEL[key].agent,
      entries: [] as typeof run.audit_tail,
    }),
  );
  // The Researcher's sourced evidence is emitted to the pipeline stream but not
  // appended to the shared immutable ledger (only the analyst/operator stages
  // are). Surface it as the real evidence for this run's Evidence stage.
  if (run.evidence && run.evidence_id) {
    stages[0].entries.push({
      seq: 0,
      prev: "",
      ts: (run.evidence.collected_at as number) ?? 0,
      kind: "researcher.emit",
      payload: run.evidence,
      sig: "emitted",
      id: run.evidence_id,
    });
  }
  for (const e of run.audit_tail) {
    const stage = STAGE_OF[e.kind] ?? "audit";
    stages.find((s) => s.key === stage)?.entries.push(e);
  }

  return (
    <div className="max-w-4xl mx-auto px-5 py-8 space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/pipelines" className="text-[var(--color-accent)] text-sm mono">
          ← pipelines
        </Link>
        <span className="text-[var(--color-ink-faint)] text-sm mono">
          {run.run_id}
        </span>
      </div>

      <header className="card p-4 flex items-center gap-3 flex-wrap">
        <VerifyPill v={run.verification} />
        <AuthPill auth={run.authorization} needs={run.needs_approval} />
        <span className="text-[var(--color-ink-dim)] text-sm">
          {run.target} · {run.action}
        </span>
        {run.needs_approval && (
          <Link
            href={`/approve/${run.action_id}`}
            className="ml-auto text-sm mono px-3 py-1.5 rounded border border-[var(--color-warn)] text-[var(--color-warn)] hover:bg-[var(--color-warn-dim)]"
          >
            sign approval →
          </Link>
        )}
      </header>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="card p-3">
          <div className="divider-label mb-1">Environment before</div>
          <div className="mono">
            {run.environment_before.workload_id}=
            <span className="text-[var(--color-ink)]">
              {run.environment_before.state}
            </span>
          </div>
        </div>
        <div className="card p-3">
          <div className="divider-label mb-1">Environment after</div>
          <div className="mono">
            {run.environment_after.workload_id}=
            <span
              className={
                run.environment_after.state !== run.environment_before.state
                  ? "text-[var(--color-ok)]"
                  : "text-[var(--color-ink)]"
              }
            >
              {run.environment_after.state}
            </span>
          </div>
        </div>
      </div>

      <div className="divider-label">Governance stages</div>
      <div className="space-y-3">
        {stages.map((s) => (
          <AuditStage
            key={s.key}
            stageKey={s.key}
            label={s.label}
            agent={s.agent}
            entries={s.entries}
            runId={run.run_id}
          />
        ))}
      </div>
    </div>
  );
}
