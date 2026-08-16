import Link from "next/link";
import { fetchRun } from "@/lib/fleet";

export const dynamic = "force-dynamic";

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

export default async function StagePage({
  params,
}: {
  params: Promise<{ runId: string; stage: string }>;
}) {
  const { runId, stage } = await params;
  let run = null;
  try {
    run = await fetchRun(runId);
  } catch {
    run = null;
  }

  const tailEntries = run?.audit_tail ?? [];
  let entries = tailEntries.filter((e) => STAGE_OF[e.kind] === stage);
  // The Evidence stage is sourced from the run's emitted researcher evidence,
  // not from the shared immutable ledger (which holds only analyst/operator
  // stages). Build the synthetic evidence entry when drilling into "evidence".
  if (stage === "evidence" && run?.evidence && run?.evidence_id) {
    entries = [{
      seq: 0,
      prev: "",
      ts: (run.evidence.collected_at as number) ?? 0,
      kind: "researcher.emit",
      payload: run.evidence,
      sig: "emitted",
      id: run.evidence_id,
    }];
  }

  return (
    <div className="max-w-3xl mx-auto px-5 py-8 space-y-5">
      <div className="flex items-center gap-3">
        <Link href={`/pipelines/${runId}`} className="text-[var(--color-accent)] text-sm mono">
          ← {runId}
        </Link>
        <span className="divider-label">stage / {stage}</span>
      </div>

      {!run ? (
        <div className="card p-6 text-[var(--color-warn)] mono text-sm">
          run not found
        </div>
      ) : entries.length === 0 ? (
        <div className="card p-6 text-[var(--color-ink-faint)] mono text-sm">
          no signed entries map to stage “{stage}” for this run
        </div>
      ) : (
        <div className="space-y-3">
          {entries.map((e) => (
            <div key={e.id} className="card p-4 space-y-2">
              <div className="flex items-center gap-2">
                <span className="pill pill-ok">{e.kind}</span>
                <span className="text-[var(--color-ink-faint)] text-xs mono">
                  seq {e.seq} · {new Date(e.ts * 1000).toISOString().slice(11, 19)}
                </span>
              </div>
              <pre className="text-xs mono text-[var(--color-ink-dim)] overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(e.payload, null, 2)}
              </pre>
              <div className="divider-label">entry signature (Ed25519)</div>
              <div className="text-[0.65rem] mono text-[var(--color-ink-faint)] break-all">
                {e.sig}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
