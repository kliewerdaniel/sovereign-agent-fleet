"use client";

import { useEffect, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";

// Route-keyed narration scripts. Each step is a real trust-boundary concept,
// not a sales pitch — the demo is honest about what the fleet actually does.
const SCRIPTS: Record<string, { title: string; body: string }[]> = {
  "/": [
    { title: "Control surface", body: "This surface RECEIVES signed artifacts. It never decides. The fleet decides; you verify." },
    { title: "Chain-integrity banner", body: "Top banner is server-computed trust state. The client never verifies crypto itself — the bridge does, fail-closed." },
    { title: "Do not trust the model", body: "Every action is bound to a verification verdict (D16), an authorization class, and an Ed25519 signature. Trust the protocol, not the agent." },
  ],
  "/pipelines": [
    { title: "Pipeline runs", body: "Each run is a real R→A→O pipeline: Researcher gathers evidence, Analyst qualifies (D16 gate), Operator requests authority." },
    { title: "Three governance paths", body: "VERIFIED → AUTO. ASSERTED → HUMAN sign. HALLUCINATION → BLOCKED at the envelope boundary (non-resolving ref)." },
    { title: "Drill in", body: "Open any run to see the six governance stages and the audit entries the fleet actually emitted." },
  ],
  "/audit": [
    { title: "Immutable ledger", body: "Append-only, Ed25519-signed. Each entry commits to its parent's hash (sha256 of the parent body)." },
    { title: "Hash-chain graph", body: "Edges are genuine parent-hash links. Tamper with one entry and every downstream signature breaks." },
    { title: "Open an entry", body: "See the canonical signed bytes and the ledger public key that verifies the signature." },
  ],
  "/domains/incident": [
    { title: "Incident domain", body: "The only wired domain. Real SimEnv digital range: web-edge, app-db, revenue-svc, identity-svc." },
    { title: "Protected asset", body: "identity-svc refuses containment (isolate/quarantine) regardless of evidence — a self-inflicted DoS defense baked into the state machine." },
    { title: "Launch a run", body: "Pick a verification class to exercise AUTO / HUMAN / BLOCKED and watch the governance path form." },
  ],
};

const GENERIC = [
  { title: "Trust boundary", body: "You are viewing a real artifact the fleet produced. The signature, not this page, authorizes anything." },
  { title: "Signed & hash-chained", body: "Every record here is committed to the prior one and signed with Ed25519. Replay and reordering are detectable." },
];

export function NarratedTour() {
  const params = useSearchParams();
  const pathname = usePathname();
  const narrated = params.get("mode") === "narrated";
  const [step, setStep] = useState(0);

  useEffect(() => {
    setStep(0);
  }, [pathname, narrated]);

  if (!narrated) return null;

  const baseKey = "/" + (pathname?.split("/").filter(Boolean)[0] ?? "");
  const steps = SCRIPTS[pathname ?? ""] ?? SCRIPTS[baseKey] ?? GENERIC;
  const current = steps[Math.min(step, steps.length - 1)];
  const isLast = step >= steps.length - 1;
  const isFirst = step <= 0;

  return (
    <div className="fixed bottom-0 inset-x-0 z-50 border-t border-[var(--color-line)] bg-[var(--color-surface-2)]/95 backdrop-blur trust-boundary">
      <div className="max-w-3xl mx-auto px-5 py-3 flex items-start gap-4">
        <div className="flex-1 min-w-0">
          <div className="divider-label mb-1">
            narrated · step {step + 1}/{steps.length} · {pathname}
          </div>
          <div className="text-sm text-[var(--color-ink)] font-semibold">{current.title}</div>
          <div className="text-sm text-[var(--color-ink-dim)]">{current.body}</div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={isFirst}
            className="px-3 py-1.5 rounded text-xs mono border border-[var(--color-edge)] text-[var(--color-ink-dim)] disabled:opacity-40"
          >
            ← prev
          </button>
          <button
            onClick={() => setStep((s) => Math.min(steps.length - 1, s + 1))}
            disabled={isLast}
            className="px-3 py-1.5 rounded text-xs mono bg-[var(--color-accent)] text-[var(--color-bg)] font-semibold disabled:opacity-40"
          >
            next →
          </button>
          <a
            href={pathname ?? "/"}
            className="px-3 py-1.5 rounded text-xs mono border border-[var(--color-edge)] text-[var(--color-ink-faint)]"
          >
            exit
          </a>
        </div>
      </div>
    </div>
  );
}
