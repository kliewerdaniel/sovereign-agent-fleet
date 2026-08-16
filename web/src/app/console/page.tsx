import Link from "next/link";
import { LiveConsole } from "@/components/LiveConsole";

export const dynamic = "force-dynamic";

export default function ConsolePage() {
  return (
    <div className="max-w-3xl mx-auto px-5 py-8 space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/" className="text-[var(--color-accent)] text-sm mono">
          ← control surface
        </Link>
        <span className="divider-label">live console</span>
      </div>

      <header className="card p-5 space-y-1">
        <div className="text-lg font-semibold">Fleet event stream</div>
        <p className="text-sm text-[var(--color-ink-dim)]">
          Subscribes to the bridge WebSocket. Shows real audit entries and
          approval events as the fleet produces them — no polling, no replay.
        </p>
      </header>

      <LiveConsole />

      <div className="text-xs text-[var(--color-ink-faint)] mono">
        launch a run →{" "}
        <Link href="/pipelines/new" className="text-[var(--color-accent)] hover:underline">
          /pipelines/new
        </Link>{" "}
        to see live events flow in.
      </div>
    </div>
  );
}
