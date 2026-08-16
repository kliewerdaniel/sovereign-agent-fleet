"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { runIncident, signApproval } from "@/lib/fleet";
import { VerifyPill, AuthPill } from "@/components/StatusPills";
import type { RunResult } from "@/lib/types";

const VERIFS = ["VERIFIED", "ASSERTED", "HALLUCINATION"];
const SEVS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
const WORKLOADS = ["web-edge", "identity-svc", "payments-api", "data-lake"];
const ACTIONS = ["block_egress", "isolate", "quarantine", "rate_limit"];

export default function NewRunPage() {
  const router = useRouter();
  const [verification, setVerification] = useState("VERIFIED");
  const [severity, setSeverity] = useState("LOW");
  const [workload_id, setWorkload] = useState("web-edge");
  const [action, setAction] = useState("block_egress");
  const [run, setRun] = useState<RunResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [signed, setSigned] = useState(false);

  async function go() {
    setBusy(true);
    setErr(null);
    setSigned(false);
    setRun(null);
    try {
      const r = await runIncident({ verification, severity, workload_id, action });
      setRun(r);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function sign() {
    if (!run || !run.needs_approval) return;
    try {
      await signApproval({
        request_id: run.action_id,
        agent_id: run.agent_id,
        action_id: run.action_id,
        capability: run.capability,
        artifact_hash: run.artifact_hash ?? "",
      });
      setSigned(true);
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-5 py-8 space-y-6">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">New pipeline run</h1>
        <p className="text-[var(--color-ink-dim)] text-sm mt-1">
          Drives the real fleet. Pick the verification class to exercise a
          different governance path.
        </p>
      </header>

      <div className="card p-4 space-y-4">
        <Field label="Verification class">
          <Select value={verification} set={setVerification} opts={VERIFS} />
        </Field>
        <Field label="Severity">
          <Select value={severity} set={setSeverity} opts={SEVS} />
        </Field>
        <Field label="Target workload">
          <Select value={workload_id} set={setWorkload} opts={WORKLOADS} />
        </Field>
        <Field label="Remediation action">
          <Select value={action} set={setAction} opts={ACTIONS} />
        </Field>
        <button
          onClick={go}
          disabled={busy}
          className="w-full text-sm mono py-2 rounded border border-[var(--color-line)] text-[var(--color-accent)] hover:bg-[var(--color-surface-2)] disabled:opacity-50"
        >
          {busy ? "running real fleet pipeline…" : "run pipeline"}
        </button>
      </div>

      {err && (
        <div className="card p-4 text-[var(--color-danger)] mono text-sm">error: {err}</div>
      )}

      {run && (
        <div className="card p-4 space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <VerifyPill v={run.verification} />
            <AuthPill auth={run.authorization} needs={run.needs_approval} />
            <span className="text-[var(--color-ink-dim)] text-sm">
              {run.target} · {run.action}
            </span>
          </div>
          <div className="text-xs mono text-[var(--color-ink-faint)]">
            {run.environment_before.workload_id}=
            <span className="text-[var(--color-ink)]">{run.environment_before.state}</span>{" "}
            →{" "}
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

          {run.needs_approval && !signed && (
            <button
              onClick={sign}
              className="w-full text-sm mono py-2 rounded border border-[var(--color-warn)] text-[var(--color-warn)] hover:bg-[var(--color-warn-dim)]"
            >
              sign human approval (Ed25519)
            </button>
          )}
          {signed && (
            <div className="text-[var(--color-ok)] mono text-sm">
              ✓ approval signed &amp; broadcast
            </div>
          )}

          <button
            onClick={() => router.push(`/pipelines/${run.run_id}`)}
            className="text-[var(--color-accent)] text-sm mono hover:underline"
          >
            inspect run →
          </button>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="divider-label mb-1.5">{label}</div>
      {children}
    </label>
  );
}

function Select({
  value,
  set,
  opts,
}: {
  value: string;
  set: (v: string) => void;
  opts: string[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => set(e.target.value)}
      className="w-full bg-[var(--color-surface-2)] border border-[var(--color-edge)] rounded px-3 py-2 text-sm mono text-[var(--color-ink)]"
    >
      {opts.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}
