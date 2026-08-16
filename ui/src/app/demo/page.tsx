"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Crosshair, Check, X, Loader2, ShieldAlert } from "lucide-react";
import { fleetApi, BeatListEntry, BeatResult } from "@/lib/fleet";

type State = "idle" | "running" | "done" | "fail";

export default function DemoPage() {
  const [beats, setBeats] = useState<BeatListEntry[]>([]);
  const [results, setResults] = useState<Record<number, BeatResult>>({});
  const [state, setState] = useState<Record<number, State>>({});

  useEffect(() => {
    fleetApi.beats().then(setBeats).catch(() => setBeats([]));
  }, []);

  async function fire(n: number) {
    setState((s) => ({ ...s, [n]: "running" }));
    try {
      const r = await fleetApi.beat(n);
      setResults((m) => ({ ...m, [n]: r }));
      setState((s) => ({ ...s, [n]: r.passed ? "done" : "fail" }));
    } catch {
      setState((s) => ({ ...s, [n]: "fail" }));
    }
  }

  async function fireAll() {
    for (const b of beats) {
      await fire(b.beat);
    }
  }

  const allDone = beats.length > 0 && beats.every((b) => state[b.beat] === "done");
  const anyFail = Object.values(state).some((s) => s === "fail");

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Crosshair className="text-[var(--color-accent)]" /> Adversarial Demo Runner
          </h1>
          <p className="dim text-sm">
            Each beat attacks the live fleet protocol. A pass means the attack was
            defeated by construction — not configured away.
          </p>
        </div>
        <button
          onClick={fireAll}
          className="px-3 py-2 rounded-md bg-[var(--color-panel-2)] border border-[var(--color-border-2)] text-sm hover:border-[var(--color-accent)] transition-colors"
        >
          Fire all 8
        </button>
      </header>

      <div className="bg-[rgba(240,88,75,0.06)] border border-[var(--color-accent-dim)] rounded-md px-3 py-2 text-xs flex items-start gap-2">
        <ShieldAlert size={14} className="text-[var(--color-warn)] mt-0.5 shrink-0" />
        <span className="dim">
          <b className="text-[var(--color-text)]">Honest scope:</b> beats run against a fresh,
          <b className="text-[var(--color-text)]"> local, in-process</b> fleet sandbox — not a live GCP run.
          They exercise the real control-plane code (no reimplementation) and return genuinely
          signed ledger entries. This proves the protocol enforces each guarantee; it is not a
          production deployment.
        </span>
      </div>

      {allDone && (
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className={`badge ${anyFail ? "badge-danger" : "badge-ok"} text-sm px-3 py-1`}
        >
          {anyFail ? "Some beats failed" : "All 8 beats passed — protocol held"}
        </motion.div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {beats.map((b) => {
          const st = state[b.beat] ?? "idle";
          const res = results[b.beat];
          return (
            <div key={b.beat} className="panel p-4 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs faint">#{b.beat}</span>
                  <span className="font-semibold text-sm">{b.name}</span>
                </div>
                <StateBadge st={st} />
              </div>
              <p className="text-xs dim leading-relaxed">{b.summary}</p>
              <div className="flex items-center justify-between mt-1">
                <span className="text-[11px] faint">
                  {res ? (res.passed ? res.detail : "FAILED: " + res.detail) : "—"}
                </span>
                <button
                  onClick={() => fire(b.beat)}
                  disabled={st === "running"}
                  className="px-3 py-1.5 rounded-md bg-[var(--color-panel-2)] border border-[var(--color-border-2)] text-xs hover:border-[var(--color-accent)] disabled:opacity-50 transition-colors"
                >
                  {st === "running" ? <Loader2 size={12} className="inline animate-spin" /> : "Fire beat"}
                </button>
              </div>
              {res && res.ledger_entries.length > 0 && (
                <div className="text-[10px] faint">
                  {res.ledger_entries.length} signed ledger entr{res.ledger_entries.length === 1 ? "y" : "ies"} produced
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StateBadge({ st }: { st: State }) {
  if (st === "running") return <span className="badge badge-info"><Loader2 size={12} className="animate-spin" /> running</span>;
  if (st === "done") return <span className="badge badge-ok"><Check size={12} /> pass</span>;
  if (st === "fail") return <span className="badge badge-danger"><X size={12} /> fail</span>;
  return <span className="badge"><span className="live-dot" /> idle</span>;
}
