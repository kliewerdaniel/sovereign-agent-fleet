"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { GitBranch, ShieldCheck, ShieldX, Loader2 } from "lucide-react";
import { fleetApi, PolicyDecisionRow, VerificationRow } from "@/lib/fleet";

function tone(d: string) {
  if (d === "deny") return "badge-danger";
  if (d === "grant") return "badge-ok";
  return "badge-warn";
}

export default function PolicyPage() {
  const [decisions, setDecisions] = useState<PolicyDecisionRow[]>([]);
  const [verifs, setVerifs] = useState<VerificationRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    Promise.all([fleetApi.policyLog(), fleetApi.verification()])
      .then(([p, v]) => {
        if (!alive) return;
        setDecisions(p.decisions);
        setVerifs(v.artifacts);
      })
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-bold flex items-center gap-2">
          <GitBranch className="text-[var(--color-accent)]" /> Policy &amp; Verification
        </h1>
        <p className="dim text-sm">
          Gateway authorization decisions — independent of any model call — plus the
          analyst verification labels on every qualified intel.
        </p>
      </header>

      {loading && (
        <div className="panel p-6 text-center dim text-sm"><Loader2 size={14} className="inline animate-spin" /> loading…</div>
      )}

      <section className="space-y-2">
        <h2 className="text-sm font-semibold dim flex items-center gap-2"><ShieldCheck size={14} /> Gateway decisions</h2>
        {!loading && decisions.length === 0 && (
          <div className="panel p-6 text-center dim text-sm">No gateway decisions yet. Run an incident to generate them.</div>
        )}
        <div className="panel divide-y divide-[var(--color-border)]">
          {decisions.map((d) => (
            <motion.div key={d.seq} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="px-4 py-2 flex items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2">
                <span className="font-mono faint">#{d.seq}</span>
                <span className="font-mono">{d.agent_id}</span>
                <span className="dim">→</span>
                <span className="mono">{d.capability}</span>
              </div>
              <div className="flex items-center gap-2">
                {d.require_approval && <span className="badge badge-warn">requires approval</span>}
                <span className={`badge ${tone(d.decision)}`}>{d.decision}</span>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold dim flex items-center gap-2"><ShieldX size={14} /> Verification labels</h2>
        {!loading && verifs.length === 0 && (
          <div className="panel p-6 text-center dim text-sm">No verification records yet.</div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {verifs.map((v) => (
            <motion.div key={v.seq} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="panel p-3 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-mono faint">#{v.seq}</span>
                <span className={`badge ${v.verification === "HALLUCINATION" ? "badge-danger" : v.verification === "ASSERTED" ? "badge-warn" : "badge-ok"}`}>{v.verification}</span>
              </div>
              <div className="mt-2 dim">
                intel <span className="mono text-[var(--color-text)]">{v.intel_id}</span>
                <span className="dim"> · </span>conf <span className="mono">{(v.confidence * 100).toFixed(0)}%</span>
              </div>
            </motion.div>
          ))}
        </div>
      </section>
    </div>
  );
}
