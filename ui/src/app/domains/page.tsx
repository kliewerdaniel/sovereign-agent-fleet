"use client";

import { useCallback, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Boxes, Play, Loader2, ShieldCheck, ShieldX, AlertTriangle, ArrowRight } from "lucide-react";
import { fleetApi, RunRequest, RunResult } from "@/lib/fleet";
import Link from "next/link";

const WORKLOADS = [
  { id: "web-edge", label: "web-edge", blast: "LOW" },
  { id: "app-db", label: "app-db", blast: "MEDIUM" },
  { id: "revenue-svc", label: "revenue-svc", blast: "HIGH" },
  { id: "identity-svc", label: "identity-svc", blast: "PROTECTED" },
];
const VERIFS = ["VERIFIED", "ASSERTED", "HALLUCINATION"] as const;
const SEVS = ["LOW", "MEDIUM", "HIGH"] as const;
const ACTIONS = ["block_egress", "isolate", "quarantine"] as const;

function authTone(a: string) {
  if (a === "BLOCKED") return "badge-danger";
  if (a === "HUMAN") return "badge-warn";
  return "badge-ok";
}

export default function DomainsPage() {
  const [req, setReq] = useState<RunRequest>({ verification: "VERIFIED", severity: "LOW", workload_id: "web-edge", action: "block_egress" });
  const [result, setResult] = useState<RunResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = useCallback(async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await fleetApi.runIncident(req);
      setResult(r);
    } catch (e: any) {
      setErr(`Run failed: ${e?.message ?? e}`);
    } finally {
      setBusy(false);
    }
  }, [req]);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-bold flex items-center gap-2">
          <Boxes className="text-[var(--color-accent)]" /> Domains · Incident Trigger
        </h1>
        <p className="dim text-sm">
          Run the real R→A→O pipeline against a workload. Verdicts are computed by the
          fleet policy engine — the UI only displays them and feeds the live ledger.
        </p>
      </header>

      <div className="panel p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Verification">
          <div className="flex flex-wrap gap-2">
            {VERIFS.map((v) => (
              <Pill key={v} active={req.verification === v} onClick={() => setReq((r) => ({ ...r, verification: v }))} warn={v === "ASSERTED"} danger={v === "HALLUCINATION"}>{v}</Pill>
            ))}
          </div>
        </Field>
        <Field label="Severity">
          <div className="flex flex-wrap gap-2">
            {SEVS.map((s) => (
              <Pill key={s} active={req.severity === s} onClick={() => setReq((r) => ({ ...r, severity: s }))}>{s}</Pill>
            ))}
          </div>
        </Field>
        <Field label="Workload">
          <div className="flex flex-wrap gap-2">
            {WORKLOADS.map((w) => (
              <Pill key={w.id} active={req.workload_id === w.id} onClick={() => setReq((r) => ({ ...r, workload_id: w.id }))} danger={w.blast === "PROTECTED"}>
                {w.label} <span className="faint text-[10px]">({w.blast})</span>
              </Pill>
            ))}
          </div>
        </Field>
        <Field label="Action">
          <div className="flex flex-wrap gap-2">
            {ACTIONS.map((a) => (
              <Pill key={a} active={req.action === a} onClick={() => setReq((r) => ({ ...r, action: a }))}>{a}</Pill>
            ))}
          </div>
        </Field>
      </div>

      <button
        onClick={run}
        disabled={busy}
        className="px-4 py-2 rounded-md bg-[var(--color-accent-dim)] border border-[var(--color-accent)] text-[var(--color-accent)] text-sm font-semibold hover:bg-[rgba(52,211,153,0.15)] disabled:opacity-50 flex items-center gap-2"
      >
        {busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Run incident pipeline
      </button>

      {err && <div className="badge badge-danger text-xs">{err}</div>}

      <AnimatePresence>
        {result && (
          <motion.div
            key={result.run_id}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="panel p-4 space-y-3"
          >
            <div className="flex items-center justify-between flex-wrap gap-2">
              <span className="font-mono text-xs faint">{result.run_id}</span>
              <div className="flex items-center gap-2">
                <span className={`badge ${authTone(result.authorization)}`}>
                  {result.authorization === "BLOCKED" ? <ShieldX size={11} /> : result.authorization === "HUMAN" ? <AlertTriangle size={11} /> : <ShieldCheck size={11} />}
                  {result.authorization}
                </span>
                {result.blocked && <span className="badge badge-danger">BLOCKED</span>}
                {result.needs_approval && <span className="badge badge-warn">needs approval</span>}
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
              <Field label="verification" value={result.verification} />
              <Field label="target" value={result.target} />
              <Field label="action" value={result.action} />
              <Field label="before" value={String((result.environment_before as any)?.state ?? "—")} />
              <Field label="after" value={String((result.environment_after as any)?.state ?? "—")} />
              {result.artifact_hash && <Field label="artifact" value={result.artifact_hash.slice(0, 16) + "…"} wide />}
            </div>

            {result.needs_approval && (
              <Link href="/approvals" className="inline-flex items-center gap-1 text-xs text-[var(--color-accent)] hover:underline">
                Go to approval console to sign <ArrowRight size={12} />
              </Link>
            )}

            <div className="text-xs dim">
              <span className="faint uppercase tracking-wide">ledger tail ({result.audit_tail.length})</span>
              <div className="mt-1 flex flex-wrap gap-1">
                {result.audit_tail.map((e) => (
                  <span key={e.id} className="badge badge-info text-[10px]">{e.kind}</span>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Field({ label, value, wide, children }: { label: string; value?: string; wide?: boolean; children?: React.ReactNode }) {
  if (children) {
    return (
      <div className={wide ? "col-span-2 md:col-span-3" : ""}>
        <div className="text-[10px] faint uppercase tracking-wide mb-1">{label}</div>
        {children}
      </div>
    );
  }
  return (
    <div className={wide ? "col-span-2 md:col-span-3" : ""}>
      <div className="text-[10px] faint uppercase tracking-wide">{label}</div>
      <div className="font-mono text-[var(--color-text)]">{value}</div>
    </div>
  );
}

function Pill({ active, onClick, children, warn, danger }: { active: boolean; onClick: () => void; children: React.ReactNode; warn?: boolean; danger?: boolean }) {
  const color = danger ? "var(--color-danger)" : warn ? "var(--color-warn)" : "var(--color-accent)";
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-md border text-xs transition-colors ${active ? "border-[var(--color-accent)] bg-[var(--color-accent-dim)]" : "border-[var(--color-border-2)] bg-[var(--color-panel-2)]"}`}
      style={active ? { color } : undefined}
    >
      {children}
    </button>
  );
}
