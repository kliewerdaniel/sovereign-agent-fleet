import Link from "next/link";
import { fetchAudit } from "@/lib/fleet";

export const dynamic = "force-dynamic";

export default async function AuditEntryPage({
  params,
}: {
  params: Promise<{ entryId: string }>;
}) {
  const { entryId } = await params;
  const audit = await fetchAudit(200);
  const entry = audit.entries.find((e) => e.id === entryId);

  if (!entry) {
    return (
      <div className="max-w-2xl mx-auto px-5 py-8">
        <Link href="/audit" className="text-[var(--color-accent)] text-sm mono">
          ← audit ledger
        </Link>
        <div className="card p-6 mt-4 text-[var(--color-warn)] mono text-sm">
          entry {entryId} not found in current ledger
        </div>
      </div>
    );
  }

  const payload = entry.payload as Record<string, unknown>;

  return (
    <div className="max-w-3xl mx-auto px-5 py-8 space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/audit" className="text-[var(--color-accent)] text-sm mono">
          ← audit ledger
        </Link>
        <span className="divider-label">ledger entry #{entry.seq}</span>
      </div>

      <header className="card p-5 space-y-1">
        <div className="text-lg font-semibold mono">{entry.kind}</div>
        <div className="text-sm text-[var(--color-ink-dim)]">
          Seq {entry.seq} · signed by the fleet control-plane Ed25519 key.
        </div>
      </header>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="card p-4 space-y-2">
          <div className="divider-label">Identity</div>
          <Row k="seq" v={String(entry.seq)} />
          <Row k="id" v={entry.id} />
          <Row k="kind" v={entry.kind} />
          <Row k="timestamp" v={new Date(entry.ts * 1000).toISOString()} />
        </div>
        <div className="card p-4 space-y-2">
          <div className="divider-label">Chain link</div>
          <Row k="prev" v={entry.prev} />
          <Row k="sig" v={entry.sig} mono />
        </div>
      </div>

      <div className="card p-4 space-y-2">
        <div className="divider-label">Canonical payload (signed bytes)</div>
        <pre className="text-xs mono text-[var(--color-ink-dim)] overflow-x-auto whitespace-pre-wrap">
          {JSON.stringify(payload, null, 2)}
        </pre>
      </div>

      <div className="card p-4 space-y-2">
        <div className="divider-label">Ledger public key (verifies sig)</div>
        <div className="text-[0.65rem] mono text-[var(--color-ink-faint)] break-all">
          {audit.ledger_pubkey_pem}
        </div>
      </div>
    </div>
  );
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="divider-label">{k}</span>
      <span className={`text-[var(--color-ink)] ${mono ? "mono text-[0.7rem] break-all" : "mono break-all"}`}>
        {v}
      </span>
    </div>
  );
}
