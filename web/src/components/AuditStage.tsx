import Link from "next/link";
import type { AuditEntry } from "@/lib/types";

const STAGE_COLOR: Record<string, string> = {
  evidence: "var(--color-accent)",
  verification: "var(--color-ok)",
  policy: "var(--color-warn)",
  approval: "var(--color-ink)",
  action: "var(--color-ink-dim)",
  audit: "var(--color-danger)",
};

function summarize(kind: string, payload: Record<string, unknown>): string {
  const p = payload ?? {};
  switch (kind) {
    case "researcher.emit":
      return `evidence ${String(p.evidence_id ?? "").replace("ev_", "#")} · ${p.citation} · "${String(p.extract ?? "").slice(0, 60)}"`;
    case "analyst.qualify":
      return `intel ${String(p.intel_id ?? "").replace("iq_", "#")} · verification ${p.verification}`;
    case "gateway.grant":
      return `capability ${p.capability} granted (policy ${p.policy_id})`;
    case "gateway.deny":
      return `DENIED: ${p.why}`;
    case "operator.final":
      return `final=${p.final} · artifact ${String(p.artifact_hash ?? "").slice(0, 12)}…`;
    case "operator.blocked":
      return `BLOCKED: ${p.reason} (gate ${p.gate})`;
    case "operator.needs_approval":
      return `requires human approval (${p.capability})`;
    case "operator.approval.signed":
      return `human ${p.human_id} approved (${p.decision})`;
    case "operator.approval.rejected":
      return `human ${p.human_id} rejected (${p.decision})`;
    default:
      return JSON.stringify(payload).slice(0, 120);
  }
}

export function AuditStage({
  stageKey,
  label,
  agent,
  entries,
  runId,
}: {
  stageKey: string;
  label: string;
  agent: string;
  entries: AuditEntry[];
  runId: string;
}) {
  const has = entries.length > 0;
  return (
    <section className="card overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--color-edge)]">
        <span
          className="w-2 h-2 rounded-full"
          style={{ background: STAGE_COLOR[stageKey] ?? "var(--color-ink-faint)" }}
        />
        <span className="text-sm font-medium">{label}</span>
        <span className="text-[var(--color-ink-faint)] text-xs mono">
          {agent}
        </span>
        <span className="ml-auto text-[var(--color-ink-faint)] text-xs mono">
          {entries.length} entry{entries.length === 1 ? "" : "ies"}
        </span>
        <Link
          href={`/pipelines/${runId}/stage/${stageKey}`}
          className="text-[var(--color-accent)] text-xs mono hover:underline"
        >
          drill ↓
        </Link>
      </div>
      {has ? (
        <ul className="divide-y divide-[var(--color-edge)]">
          {entries.map((e) => (
            <li key={e.id} className="px-4 py-2 text-xs mono text-[var(--color-ink-dim)]">
              <span className="text-[var(--color-ink-faint)]">seq {e.seq}</span>{" "}
              <span className="text-[var(--color-ink)]">{e.kind}</span> —{" "}
              {summarize(e.kind, e.payload)}
            </li>
          ))}
        </ul>
      ) : (
        <div className="px-4 py-2 text-xs text-[var(--color-ink-faint)] mono">
          no entries for this stage
        </div>
      )}
    </section>
  );
}
