"use client";

import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { UserCheck, Check, X, Loader2, ShieldCheck, FileSignature } from "lucide-react";
import { fleetApi, PendingApproval, ApprovalResult } from "@/lib/fleet";

export default function ApprovalsPage() {
  const [pending, setPending] = useState<PendingApproval[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [resolved, setResolved] = useState<Record<string, ApprovalResult>>({});
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    fleetApi.pending().then(setPending).catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [load]);

  async function decide(p: PendingApproval, approve: boolean) {
    setBusy(p.request_id);
    setErr(null);
    try {
      const r = await fleetApi.decide(p.request_id, { approve, signer: "human-approver" });
      setResolved((m) => ({ ...m, [p.request_id]: r }));
      setPending((list) => list.filter((x) => x.request_id !== p.request_id));
    } catch (e: any) {
      setErr(`${approve ? "Approve" : "Deny"} failed: ${e?.message ?? e}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <UserCheck className="text-[var(--color-accent)]" /> Approval Console · D17
          </h1>
          <p className="dim text-sm">
            Consequential actions held for human sign-off. Approve/deny signs through the
            real <span className="text-[var(--color-text)]">Approval.sign</span> flow — the UI never signs itself.
          </p>
        </div>
        <button onClick={load} className="px-3 py-2 rounded-md bg-[var(--color-panel-2)] border border-[var(--color-border-2)] text-sm hover:border-[var(--color-accent)] transition-colors">
          Refresh
        </button>
      </header>

      <div className="bg-[rgba(90,169,230,0.06)] border border-[var(--color-info)] rounded-md px-3 py-2 text-xs flex items-start gap-2">
        <ShieldCheck size={14} className="text-[var(--color-info)] mt-0.5 shrink-0" />
        <span className="dim">
          A genuine Ed25519 human signature is bound to the exact action, capability, and
          artifact hash. A rebound or reused approval is rejected by the Operator (fail-closed).
        </span>
      </div>

      {err && <div className="badge badge-danger text-xs">{err}</div>}

      {pending.length === 0 && Object.keys(resolved).length === 0 && (
        <div className="panel p-8 text-center dim text-sm">
          No pending approvals. Trigger a HUMAN-authorization run from the{" "}
          <span className="text-[var(--color-text)]">Domains</span> page to populate the queue.
        </div>
      )}

      <div className="space-y-3">
        <AnimatePresence initial={false}>
          {pending.map((p) => (
            <motion.div
              key={p.request_id}
              layout
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: 24 }}
              className="panel p-4"
            >
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <span className="badge badge-warn">HUMAN REQUIRED</span>
                  <span className="font-mono text-xs faint">{p.request_id}</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    disabled={busy !== null}
                    onClick={() => decide(p, true)}
                    className="px-3 py-1.5 rounded-md bg-[var(--color-accent-dim)] border border-[var(--color-accent)] text-[var(--color-accent)] text-xs font-semibold hover:bg-[rgba(52,211,153,0.15)] disabled:opacity-50 flex items-center gap-1"
                  >
                    {busy === p.request_id ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />} Approve &amp; sign
                  </button>
                  <button
                    disabled={busy !== null}
                    onClick={() => decide(p, false)}
                    className="px-3 py-1.5 rounded-md bg-[rgba(240,88,75,0.12)] border border-[var(--color-danger)] text-[var(--color-danger)] text-xs font-semibold hover:bg-[rgba(240,88,75,0.2)] disabled:opacity-50 flex items-center gap-1"
                  >
                    {busy === p.request_id ? <Loader2 size={12} className="animate-spin" /> : <X size={12} />} Deny
                  </button>
                </div>
              </div>
              <dl className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-3 text-xs">
                <Field label="agent" value={p.agent_id || "operator"} />
                <Field label="capability" value={p.capability} />
                <Field label="raised" value={new Date(p.raised_at * 1000).toLocaleTimeString()} />
                <Field label="artifact hash" value={p.artifact_hash ? p.artifact_hash.slice(0, 20) + "…" : "—"} wide />
              </dl>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {Object.keys(resolved).length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold dim flex items-center gap-2"><FileSignature size={14} /> Resolved</h2>
          {Object.values(resolved).map((r) => (
            <div key={r.approval_id} className="panel p-3 text-xs">
              <div className="flex items-center gap-2">
                {r.decision === "approve" ? (
                  <span className="badge badge-ok"><Check size={11} /> signed approve</span>
                ) : (
                  <span className="badge badge-danger"><X size={11} /> denied</span>
                )}
                <span className="font-mono faint">{r.approval_id}</span>
                <span className="dim">by {r.human_id}</span>
              </div>
              {r.human_sig && (
                <div className="mt-1 text-[10px] faint font-mono break-all">sig: {r.human_sig}</div>
              )}
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

function Field({ label, value, wide }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={wide ? "col-span-2 md:col-span-3" : ""}>
      <div className="text-[10px] faint uppercase tracking-wide">{label}</div>
      <div className="font-mono text-[var(--color-text)]">{value}</div>
    </div>
  );
}
