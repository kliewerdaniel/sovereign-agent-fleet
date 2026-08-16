import Link from "next/link";
import { fetchRuns } from "@/lib/fleet";
import { AuthPill, VerifyPill } from "@/components/StatusPills";

export const dynamic = "force-dynamic";

const STAGES = [
  { key: "evidence", label: "Evidence", agent: "Researcher" },
  { key: "verification", label: "Verification", agent: "Analyst" },
  { key: "policy", label: "Policy", agent: "Gateway" },
  { key: "approval", label: "Approval", agent: "Human" },
  { key: "action", label: "Action", agent: "Operator" },
];

export default async function PipelinesPage() {
  let runs: Awaited<ReturnType<typeof fetchRuns>>["runs"] = [];
  try {
    const r = await fetchRuns();
    runs = r.runs;
  } catch {
    runs = [];
  }

  return (
    <div className="max-w-5xl mx-auto px-5 py-8 space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Pipelines</h1>
          <p className="text-[var(--color-ink-dim)] text-sm mt-1">
            Each run drives the real Researcher → Analyst → Operator pipeline
            against the fleet. The model proposes; the protocol disposes.
          </p>
        </div>
        <Link
          href="/pipelines/new"
          className="text-sm mono px-3 py-1.5 rounded border border-[var(--color-line)] text-[var(--color-accent)] hover:bg-[var(--color-surface-2)]"
        >
          + new run
        </Link>
      </header>

      {runs.length === 0 ? (
        <div className="card p-6 text-[var(--color-ink-faint)] text-sm mono">
          no runs yet — start one from{" "}
          <Link href="/pipelines/new" className="text-[var(--color-accent)]">
            /pipelines/new
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {runs.map((r) => (
            <Link
              key={r.run_id}
              href={`/pipelines/${r.run_id}`}
              className="card p-4 flex items-center gap-4 hover:border-[var(--color-line)] transition-colors"
            >
              <div className="w-32 shrink-0">
                <div className="text-[0.65rem] mono text-[var(--color-ink-faint)]">
                  run
                </div>
                <div className="text-sm mono">{r.run_id.replace("run_", "#")}</div>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <VerifyPill v={r.verification} />
                <AuthPill auth={r.authorization} needs={r.needs_approval} />
              </div>
              <div className="ml-auto text-right text-sm">
                <div className="text-[var(--color-ink)]">
                  {r.target} · {r.action}
                </div>
                <div className="text-[var(--color-ink-faint)] text-xs mono">
                  {r.audit_count} audit entries
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      <div className="divider-label pt-4">Pipeline stages</div>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
        {STAGES.map((s) => (
          <div key={s.key} className="card p-3">
            <div className="text-sm font-medium">{s.label}</div>
            <div className="text-[var(--color-ink-faint)] text-xs mono mt-0.5">
              {s.agent}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
