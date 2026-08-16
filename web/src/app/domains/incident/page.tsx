import Link from "next/link";
import { fetchDomains } from "@/lib/fleet";
import { DomainPanel } from "@/components/DomainPanel";

export const dynamic = "force-dynamic";

export default async function IncidentDomainPage() {
  const model = await fetchDomains();
  const verifs = ["VERIFIED", "ASSERTED", "HALLUCINATION"];
  const workloads = model.workloads.map((w) => w.workload_id);
  const actions = model.actions.map((a) => a.action);

  return (
    <div className="max-w-3xl mx-auto px-5 py-8 space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/" className="text-[var(--color-accent)] text-sm mono">
          ← control surface
        </Link>
        <span className="divider-label">domain · incident</span>
        <span className="pill pill-ok">wired</span>
      </div>

      <header className="card p-5 space-y-1">
        <div className="text-lg font-semibold">Incident remediation domain</div>
        <p className="text-sm text-[var(--color-ink-dim)]">
          Real R→A→O pipeline over the genuine fleet. Launch a run to exercise a
          governance path, then inspect it under{" "}
          <Link href="/pipelines" className="text-[var(--color-accent)] hover:underline">
            Pipelines
          </Link>
          .
        </p>
      </header>

      <div className="card p-4 space-y-3">
        <div className="divider-label">Launch a real incident run</div>
        <div className="flex flex-wrap gap-2">
          {verifs.map((v) => (
            <Link
              key={v}
              href={`/pipelines/new?verification=${v}`}
              className="px-3 py-2 rounded border border-[var(--color-edge)] text-sm mono text-[var(--color-ink)] hover:border-[var(--color-accent)]"
            >
              {v}
            </Link>
          ))}
        </div>
        <div className="text-xs text-[var(--color-ink-faint)] mono">
          workloads: {workloads.join(", ")} · actions: {actions.join(", ")}
        </div>
      </div>

      <DomainPanel model={model} />
    </div>
  );
}
