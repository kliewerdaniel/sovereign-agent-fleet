import Link from "next/link";
import type { DomainModel } from "@/lib/fleet";

function AuthPill({ decision }: { decision: string }) {
  const cls =
    decision === "BLOCKED"
      ? "pill pill-danger"
      : decision === "HUMAN"
        ? "pill pill-warn"
        : "pill pill-ok";
  return <span className={cls}>{decision}</span>;
}

function AssetClassPill({ cls }: { cls: string }) {
  const c =
    cls === "PROTECTED"
      ? "pill pill-danger"
      : cls === "HIGH"
        ? "pill pill-warn"
        : cls === "MEDIUM"
          ? "pill pill-warn"
          : "pill pill-ok";
  return <span className={c}>{cls}</span>;
}

export function DomainPanel({ model }: { model: DomainModel }) {
  return (
    <div className="space-y-6">
      <div className="card p-4 space-y-3">
        <div className="divider-label">Workloads (digital range)</div>
        <div className="grid gap-2">
          {model.workloads.map((w) => (
            <div
              key={w.workload_id}
              className="flex items-center gap-3 text-sm border border-[var(--color-edge)] rounded px-3 py-2"
            >
              <span className="mono text-[var(--color-ink)] w-28">{w.workload_id}</span>
              <AssetClassPill cls={w.asset_class} />
              {w.protected && (
                <span className="text-[var(--color-ink-dim)] text-xs">
                  containment prohibited (self-inflicted DoS defense)
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="card p-4 space-y-3">
        <div className="divider-label">Remediation actions (blast radius)</div>
        <div className="grid gap-2">
          {model.actions.map((a) => (
            <div
              key={a.action}
              className="flex items-center gap-3 text-sm border border-[var(--color-edge)] rounded px-3 py-2"
            >
              <span className="mono text-[var(--color-ink)] w-28">{a.action}</span>
              <span className="text-[var(--color-ink-dim)]">→ {a.result_state}</span>
              <span className="mono text-[var(--color-ink-faint)] text-xs">
                blast {a.blast_radius}
              </span>
              {a.prohibited_on_protected && (
                <span className="text-[var(--color-danger)] text-xs">
                  ✕ identity-svc
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="card p-4 space-y-3">
        <div className="divider-label">Incident authorization policy (verification × severity × blast × asset)</div>
        <div className="grid gap-2">
          {model.policy_matrix.map((p, i) => (
            <div
              key={i}
              className="flex items-center gap-3 text-xs border border-[var(--color-edge)] rounded px-3 py-2"
            >
              <span className="mono text-[var(--color-ink-dim)] flex-1">{p.when}</span>
              <AuthPill decision={p.decision} />
              <span className="text-[var(--color-ink-faint)] flex-1">{p.note}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function UnwiredNote({ domain, wired }: { domain: string; wired: string[] }) {
  return (
    <div className="card p-5 space-y-2 trust-boundary">
      <span className="pill pill-warn">not yet wired</span>
      <p className="text-sm text-[var(--color-ink-dim)]">
        The <span className="mono">{domain}</span> domain is declared in the fleet
        schema but has no real pipeline runner yet. To avoid fabricating evidence,
        this panel shows only the operator surface model — no simulated runs.
      </p>
      <p className="text-xs text-[var(--color-ink-faint)] mono">
        wired domains: {wired.join(", ")}
      </p>
      <Link
        href={`/domains/${wired[0] ?? "incident"}`}
        className="text-[var(--color-accent)] text-sm mono hover:underline"
      >
        see the wired domain →
      </Link>
    </div>
  );
}
