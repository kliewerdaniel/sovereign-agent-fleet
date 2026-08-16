"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ShieldCheck, ScrollText, Crosshair, UserCheck, Users, GitBranch, Boxes, Hash } from "lucide-react";
import { fleetApi } from "@/lib/fleet";

export default function HomePage() {
  const [stats, setStats] = useState<{
    agents: number;
    chainValid: boolean;
    head: string | null;
  } | null>(null);

  useEffect(() => {
    Promise.all([fleetApi.agents(), fleetApi.chainIntegrity()])
      .then(([a, c]) =>
        setStats({ agents: a.agents.length, chainValid: c.valid, head: c.head })
      )
      .catch(() => setStats(null));
  }, []);

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <motion.h1
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-2xl font-bold tracking-tight flex items-center gap-2"
        >
          <ShieldCheck className="text-[var(--color-accent)]" /> Live Trust Boundary
        </motion.h1>
        <p className="dim max-w-2xl text-sm">
          A governed 3-agent fleet (Researcher → Analyst → Operator). The thesis:
          <span className="text-[var(--color-text)]"> do not trust the model — trust the execution protocol.</span>{" "}
          Every consequential action is gated by a deterministic policy engine, signed
          by a local-first root of trust, and recorded in a tamper-evident Ed25519
          hash chain. This surface reads that chain <span className="text-[var(--color-accent)]">live</span> — it never signs or approves anything itself.
        </p>
      </header>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Live agents" value={stats ? String(stats.agents) : "—"} tone="info" />
        <Stat
          label="Chain integrity"
          value={stats == null ? "—" : stats.chainValid ? "VALID" : "BROKEN"}
          tone={stats?.chainValid ? "ok" : stats == null ? "info" : "danger"}
        />
        <Stat label="Control plane" value="LIVE" tone="ok" />
        <Stat label="Demo beats" value="8" tone="info" />
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <NavCard href="/ledger" icon={ScrollText} title="Live Audit Ledger"
          desc="SSE tail of the signed hash chain. New records animate in, each linking to the previous." />
        <NavCard href="/demo" icon={Crosshair} title="Adversarial Demo"
          desc="Fire beats 1–8 against the live fleet. Watch attacks fail on camera with pass/fail badges." />
        <NavCard href="/approvals" icon={UserCheck} title="Approval Console (D17)"
          desc="Consequential actions awaiting a human-signed ApprovalRecord. Approve/deny calls the real flow." />
        <NavCard href="/registry" icon={Users} title="Agent Registry"
          desc="Live roster of identities and certs. Exercise key rotation (beat 8) and watch the chain stay continuous." />
        <NavCard href="/policy" icon={GitBranch} title="Policy Decision Log"
          desc="GRANT / REQUIRE_APPROVAL / DENY decisions — independent of any model call." />
        <NavCard href="/domains" icon={Boxes} title="Domains"
          desc="Run the same governance layer against different workloads." />
      </section>

      {stats?.head && (
        <section className="panel p-3 flex items-center gap-2 text-xs faint">
          <Hash size={14} className="text-[var(--color-accent)]" />
          chain head: <span className="mono">{stats.head.slice(0, 32)}…</span>
        </section>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone: "ok" | "warn" | "danger" | "info" }) {
  const color =
    tone === "ok" ? "text-[var(--color-accent)]" :
    tone === "warn" ? "text-[var(--color-warn)]" :
    tone === "danger" ? "text-[var(--color-danger)]" : "text-[var(--color-info)]";
  return (
    <div className="panel p-4">
      <div className="text-xs faint uppercase tracking-wide">{label}</div>
      <div className={`text-xl font-bold mt-1 ${color}`}>{value}</div>
    </div>
  );
}

function NavCard({ href, icon: Icon, title, desc }: { href: string; icon: any; title: string; desc: string }) {
  return (
    <Link href={href} className="panel p-4 hover:border-[var(--color-border-2)] transition-colors group">
      <div className="flex items-center gap-2 mb-1">
        <Icon size={18} className="text-[var(--color-accent)]" />
        <span className="font-semibold">{title}</span>
      </div>
      <p className="text-xs dim leading-relaxed">{desc}</p>
    </Link>
  );
}
