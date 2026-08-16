import { fetchChainIntegrity, runIncident } from "@/lib/fleet";
import { ChainIntegrityBanner } from "@/components/ChainIntegrityBanner";
import Link from "next/link";

export const dynamic = "force-dynamic";

function AuthPill({ auth, needs }: { auth: string; needs?: boolean }) {
  const cls =
    auth === "BLOCKED"
      ? "pill pill-danger"
      : needs
        ? "pill pill-warn"
        : "pill pill-ok";
  return <span className={cls}>{auth}</span>;
}

export default async function HomePage() {
  let integrity = null;
  let run = null;
  try {
    integrity = await fetchChainIntegrity();
  } catch {
    integrity = null;
  }
  try {
    // Real fleet pipeline, lowest-risk path, so the console opens on truth.
    run = await runIncident({ verification: "VERIFIED", severity: "LOW", workload_id: "web-edge", action: "block_egress" });
  } catch {
    run = null;
  }

  return (
    <div className="max-w-5xl mx-auto px-5 py-8 space-y-8">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          Sovereign Agent Fleet
        </h1>
        <p className="text-[var(--color-ink-dim)] max-w-2xl">
          A 3-agent pipeline — Researcher → Analyst → Operator — that{" "}
          <span className="text-[var(--color-ink)]">proposes</span>. It never
          self-authorizes. Every action passes through signed evidence, a
          verification gate, capability policy, and (when required) a human
          Ed25519 approval before any environment changes. The model is never
          the authority.
        </p>
      </header>

      <section className="space-y-3">
        <div className="divider-label">Trust posture</div>
        {integrity ? (
          <div className="card p-4 space-y-3">
            <div className="flex items-center gap-3">
              <AuthPill auth={integrity.valid ? "INTACT" : "BROKEN"} />
              <span className="text-[var(--color-ink-dim)] text-sm">
                {integrity.entry_count} signed audit entries · chain verified on
                the bridge
              </span>
            </div>
            <div className="grid sm:grid-cols-2 gap-3 text-xs mono text-[var(--color-ink-faint)]">
              <div>
                <div className="divider-label mb-1">Chain head</div>
                <div className="break-all">{integrity.head}</div>
              </div>
              <div>
                <div className="divider-label mb-1">Audit public key</div>
                <div className="break-all">{integrity.audit_pubkey_pem}</div>
              </div>
            </div>
          </div>
        ) : (
          <div className="card p-4 text-[var(--color-warn)] mono text-sm">
            bridge unreachable — start it with `uvicorn bridge.app:app`
          </div>
        )}
      </section>

      <section className="space-y-3">
        <div className="divider-label">Live first run (real fleet)</div>
        {run ? (
          <div className="card p-4 space-y-3">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="pill pill-ok">{run.verification}</span>
              <AuthPill auth={run.authorization} needs={run.needs_approval} />
              <span className="text-[var(--color-ink-dim)] text-sm">
                {run.target} · {run.action}
              </span>
            </div>
            <div className="text-xs mono text-[var(--color-ink-faint)]">
              {run.environment_before.workload_id}=
              <span className="text-[var(--color-ink)]">{run.environment_before.state}</span>{" "}
              →{" "}
              <span className="text-[var(--color-ok)]">
                {run.environment_after.state}
              </span>
            </div>
            <Link
              href={`/pipelines/${run.run_id}`}
              className="inline-block text-[var(--color-accent)] text-sm mono hover:underline"
            >
              inspect run →
            </Link>
          </div>
        ) : (
          <div className="card p-4 text-[var(--color-warn)] mono text-sm">
            could not run a pipeline — bridge or fleet unavailable
          </div>
        )}
      </section>

      <section className="grid sm:grid-cols-3 gap-3">
        <QuickLink href="/pipelines" title="Pipelines" sub="run & inspect R→A→O" />
        <QuickLink href="/audit" title="Audit ledger" sub="hash-chain explorer" />
        <QuickLink href="/domains/incident" title="Incident domain" sub="remediation gate" />
      </section>
    </div>
  );
}

function QuickLink({ href, title, sub }: { href: string; title: string; sub: string }) {
  return (
    <Link href={href} className="card p-4 hover:border-[var(--color-line)] transition-colors">
      <div className="text-sm font-medium">{title}</div>
      <div className="text-[var(--color-ink-faint)] text-xs mt-1">{sub}</div>
    </Link>
  );
}
