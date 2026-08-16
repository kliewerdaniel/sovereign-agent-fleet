import Link from "next/link";
import { fetchAudit, fetchChainIntegrity } from "@/lib/fleet";
import { AuditGraph } from "@/components/AuditGraph";

export const dynamic = "force-dynamic";

// Display order: newest (highest seq) first, matching /pipelines ordering.
function summarizeKind(kind: string): string {
  const short = kind.split(".").pop() ?? kind;
  return short;
}

export default async function AuditPage() {
  const [audit, chain] = await Promise.all([fetchAudit(200), fetchChainIntegrity()]);
  const entries = [...audit.entries].sort((a, b) => b.seq - a.seq);

  return (
    <div className="max-w-5xl mx-auto px-5 py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <Link href="/" className="text-[var(--color-accent)] text-sm mono">
            ← control surface
          </Link>
          <h1 className="text-xl font-semibold tracking-tight">Audit ledger</h1>
          <p className="text-sm text-[var(--color-ink-dim)]">
            Immutable, append-only, Ed25519-signed. Edge between nodes is the
            parent hash link. Best viewed newest-first.
          </p>
        </div>
        <div className="text-right space-y-1">
          <span
            className={`pill ${chain.valid ? "pill-ok" : "pill-danger"}`}
          >
            chain {chain.valid ? "valid" : "invalid"}
          </span>
          <div className="divider-label">{chain.entry_count} entries</div>
        </div>
      </div>

      <AuditGraph entries={audit.entries} />

      <div className="space-y-2">
        {entries.map((e) => (
          <Link
            key={e.id}
            href={`/audit/${e.id}`}
            className="card flex items-center gap-3 px-4 py-3 hover:border-[var(--color-line)] transition-colors"
          >
            <span className="mono text-[var(--color-ink-faint)] text-xs w-10">
              #{e.seq}
            </span>
            <span className="mono text-sm text-[var(--color-ink)]">{e.kind}</span>
            <span className="mono text-xs text-[var(--color-ink-dim)] truncate flex-1">
              {summarizeKind(e.kind)} · prev {e.prev.slice(0, 12)}…
            </span>
            <span className="mono text-[0.65rem] text-[var(--color-ink-faint)]">
              {e.sig.slice(0, 12)}…
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
