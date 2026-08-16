"use client";

import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Users, RefreshCw, KeyRound, ShieldCheck, ShieldX, Loader2 } from "lucide-react";
import { fleetApi, AgentsSnapshot, RevokeRotateResult } from "@/lib/fleet";

export default function RegistryPage() {
  const [snap, setSnap] = useState<AgentsSnapshot | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [lastRot, setLastRot] = useState<RevokeRotateResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    fleetApi.agents().then(setSnap).catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  async function rotate(id: string) {
    setBusy(id);
    setErr(null);
    try {
      const r = await fleetApi.revokeRotate(id);
      setLastRot(r);
      load();
    } catch (e: any) {
      setErr(`Rotate failed: ${e?.message ?? e}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Users className="text-[var(--color-accent)]" /> Agent Registry
          </h1>
          <p className="dim text-sm">
            Live roster of fleet identities and their certs. Revoke → rotate exercises
            the recovery path (beat 8) against the real control plane.
          </p>
        </div>
        <button onClick={load} className="px-3 py-2 rounded-md bg-[var(--color-panel-2)] border border-[var(--color-border-2)] text-sm hover:border-[var(--color-accent)] transition-colors">
          Refresh
        </button>
      </header>

      {err && <div className="badge badge-danger text-xs">{err}</div>}

      {snap && (
        <div className="panel p-3 text-xs faint flex items-center gap-3">
          <KeyRound size={14} className="text-[var(--color-info)]" />
          root epoch <span className="mono text-[var(--color-text)]">{snap.root_epoch}</span>
          <span className="dim">·</span>
          <span className="mono text-[var(--color-text-faint)]">{snap.root_public_pem.slice(0, 48)}…</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {snap?.agents.map((a) => (
          <motion.div key={a.agent_id} layout className="panel p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm">{a.agent_id}</span>
                {a.status === "revoked" ? (
                  <span className="badge badge-danger"><ShieldX size={11} /> revoked</span>
                ) : (
                  <span className="badge badge-ok"><ShieldCheck size={11} /> active</span>
                )}
              </div>
              <span className="text-xs faint uppercase tracking-wide">{a.role}</span>
            </div>
            <div className="flex flex-wrap gap-1 mt-2">
              {a.capabilities.map((c) => (
                <span key={c} className="badge badge-info text-[10px]">{c}</span>
              ))}
            </div>
            <dl className="grid grid-cols-2 gap-2 mt-3 text-xs">
              <Field label="cert seq" value={String(a.cert_seq)} />
              <Field label="expires" value={new Date(a.expires_at * 1000).toLocaleDateString()} />
            </dl>
            <button
              disabled={busy !== null}
              onClick={() => rotate(a.agent_id)}
              className="mt-3 px-3 py-1.5 rounded-md bg-[var(--color-panel-2)] border border-[var(--color-border-2)] text-xs hover:border-[var(--color-accent)] disabled:opacity-50 transition-colors flex items-center gap-1"
            >
              {busy === a.agent_id ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />} Revoke &amp; rotate
            </button>
          </motion.div>
        ))}
      </div>

      {lastRot && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="panel p-3 text-xs space-y-1"
        >
          <div className="flex items-center gap-2">
            <RefreshCw size={14} className="text-[var(--color-accent)]" />
            <span className="font-semibold">{lastRot.agent_id}</span>
            <span className="badge badge-ok">chain {lastRot.chain_valid ? "valid" : "broken"}</span>
            <span className="badge badge-info">cert seq → {lastRot.cert_seq}</span>
          </div>
          <div className="dim">
            revoked={String(lastRot.revoked)} · discoverable={String(lastRot.discoverable)} ·
            new cert issued for <span className="mono">{lastRot.new_cert.agent_id}</span> ({lastRot.new_cert.role})
          </div>
        </motion.div>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] faint uppercase tracking-wide">{label}</div>
      <div className="font-mono text-[var(--color-text)]">{value}</div>
    </div>
  );
}
