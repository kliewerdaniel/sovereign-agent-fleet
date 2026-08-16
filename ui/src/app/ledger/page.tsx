"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link2, Wifi, WifiOff, ShieldCheck } from "lucide-react";
import { fleetApi, AuditEntry } from "@/lib/fleet";
import { KindBadge } from "@/components/StatusPill";
import { useLedgerStream } from "@/lib/useLedgerStream";

function short(h: string | null) {
  if (!h) return "—";
  return h.slice(0, 12) + "…" + h.slice(-6);
}

export default function LedgerPage() {
  const { entries, connected } = useLedgerStream();
  const [chainValid, setChainValid] = useState<boolean | null>(null);

  useEffect(() => {
    fleetApi.chainIntegrity().then((c) => setChainValid(c.valid)).catch(() => setChainValid(null));
  }, [entries.length]);

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Link2 className="text-[var(--color-accent)]" /> Live Audit Ledger
          </h1>
          <p className="dim text-sm">Tamper-evident Ed25519 hash chain — tailed in real time.</p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          {chainValid === null ? (
            <span className="dim">verifying…</span>
          ) : chainValid ? (
            <span className="badge badge-ok"><ShieldCheck size={12} /> chain valid</span>
          ) : (
            <span className="badge badge-danger">chain broken</span>
          )}
          <span className={`badge ${connected ? "badge-ok" : "badge-danger"}`}>
            {connected ? <><Wifi size={12} /> streaming</> : <><WifiOff size={12} /> offline</>}
          </span>
        </div>
      </header>

      <div className="panel divide-y divide-[var(--color-border)] max-h-[78vh] overflow-y-auto">
        <AnimatePresence initial={false}>
          {entries.map((e, i) => {
            const prev = entries[i + 1];
            return (
              <motion.div
                key={e.id}
                layout
                initial={{ opacity: 0, x: -16, backgroundColor: "rgba(52,211,153,0.10)" }}
                animate={{ opacity: 1, x: 0, backgroundColor: "rgba(0,0,0,0)" }}
                transition={{ duration: 0.5 }}
                className="px-4 py-3 flex items-start gap-3"
              >
                <div className="font-mono text-xs faint w-24 shrink-0">
                  <div>#{e.seq}</div>
                  <div className="text-[10px]">{new Date(e.ts * 1000).toLocaleTimeString()}</div>
                </div>
                <div className="shrink-0 pt-1">
                  <KindBadge kind={e.kind} />
                </div>
                <div className="min-w-0 flex-1">
                  <pre className="text-xs mono text-[var(--color-text-dim)] whitespace-pre-wrap break-all">
{JSON.stringify(e.payload, null, 2)}
                  </pre>
                </div>
                <div className="shrink-0 w-32 text-right">
                  <div className="text-[10px] faint uppercase">prev</div>
                  <div className="font-mono text-[11px] text-[var(--color-accent)]">{short(e.prev)}</div>
                  <div className="text-[10px] faint uppercase mt-1">sig</div>
                  <div className="font-mono text-[11px] text-[var(--color-text-faint)]">{short(e.sig)}</div>
                  {prev && (
                    <div className="text-[10px] faint mt-1">links #{prev.seq}</div>
                  )}
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
        {entries.length === 0 && (
          <div className="px-4 py-10 text-center dim text-sm">
            Waiting for the first signed record…
          </div>
        )}
      </div>
    </div>
  );
}
