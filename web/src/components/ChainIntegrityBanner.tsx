import type { ChainIntegrity } from "@/lib/types";

/**
 * Trust-boundary-first. The chain state is COMPUTED on the bridge (real Ed25519
 * verify over the signed ledger) and handed to the client verbatim. The client
 * renders it; it never verifies crypto itself. If `valid` is false the whole
 * surface should read as compromised — fail-closed by design.
 */
export function ChainIntegrityBanner({ integrity }: { integrity: ChainIntegrity }) {
  const ok = integrity.valid;
  return (
    <div
      className={`trust-boundary w-full px-4 py-1.5 text-xs flex items-center gap-3 ${
        ok ? "" : "bg-[var(--color-danger-dim)]"
      }`}
    >
      <span
        className={`inline-block w-2 h-2 rounded-full ${
          ok ? "bg-[var(--color-ok)]" : "bg-[var(--color-danger)]"
        }`}
        aria-hidden
      />
      <span className="font-mono font-semibold tracking-wide" style={{ color: ok ? "var(--color-ok)" : "var(--color-danger)" }}>
        {ok ? "CHAIN INTACT" : "CHAIN BROKEN"}
      </span>
      <span className="text-[var(--color-ink-faint)] mono">
        {integrity.entry_count} signed entries
      </span>
      <span className="text-[var(--color-ink-faint)] mono hidden sm:inline">
        head {short(integrity.head ?? "")}
      </span>
      <span className="ml-auto text-[var(--color-ink-faint)] mono hidden md:inline">
        audit key {short(integrity.audit_pubkey_pem)}
      </span>
    </div>
  );
}

function short(s: string): string {
  if (s.length <= 16) return s;
  return `${s.slice(0, 10)}…${s.slice(-4)}`;
}
