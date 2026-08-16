import Link from "next/link";

const LINKS = [
  { href: "/", label: "Console" },
  { href: "/pipelines", label: "Pipelines" },
  { href: "/audit", label: "Audit" },
  { href: "/domains/incident", label: "Incident" },
  { href: "/domains/financial", label: "Financial" },
  { href: "/domains/sales", label: "Sales" },
  { href: "/console", label: "Live" },
];

export function SiteNav() {
  return (
    <nav className="border-b border-[var(--color-edge)] bg-[var(--color-surface)]">
      <div className="px-4 h-12 flex items-center gap-1">
        <Link href="/" className="mr-4 flex items-center gap-2 group">
          <span className="text-[var(--color-accent)] mono text-sm font-bold tracking-tight">
            ⛨ SOVEREIGN
          </span>
          <span className="text-[var(--color-ink-faint)] text-[0.65rem] mono hidden lg:inline">
            agent fleet
          </span>
        </Link>
        <div className="flex items-center gap-0.5 overflow-x-auto">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="px-2.5 py-1.5 rounded text-[0.8rem] text-[var(--color-ink-dim)] hover:text-[var(--color-ink)] hover:bg-[var(--color-surface-2)] transition-colors mono"
            >
              {l.label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
