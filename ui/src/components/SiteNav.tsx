"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck, ScrollText, Crosshair, UserCheck, Users, GitBranch, Boxes } from "lucide-react";

const LINKS = [
  { href: "/", label: "Overview", icon: ShieldCheck },
  { href: "/ledger", label: "Live Ledger", icon: ScrollText },
  { href: "/demo", label: "Adversarial Demo", icon: Crosshair },
  { href: "/approvals", label: "Approval Console", icon: UserCheck },
  { href: "/registry", label: "Agent Registry", icon: Users },
  { href: "/policy", label: "Policy Log", icon: GitBranch },
  { href: "/domains", label: "Domains", icon: Boxes },
];

export function SiteNav() {
  const path = usePathname();
  return (
    <nav className="border-b border-[var(--color-border)] px-5 py-3 flex items-center gap-1 flex-wrap">
      <Link href="/" className="mr-4 font-bold tracking-tight flex items-center gap-2">
        <ShieldCheck size={18} className="text-[var(--color-accent)]" />
        SOVEREIGN<span className="faint font-normal">agent fleet</span>
      </Link>
      {LINKS.map((l) => {
        const active = path === l.href || (l.href !== "/" && path.startsWith(l.href));
        const Icon = l.icon;
        return (
          <Link
            key={l.href}
            href={l.href}
            className={`px-3 py-1.5 rounded-md text-sm flex items-center gap-1.5 transition-colors ${
              active
                ? "bg-[var(--color-panel-2)] text-[var(--color-text)]"
                : "text-[var(--color-text-dim)] hover:text-[var(--color-text)]"
            }`}
          >
            <Icon size={15} />
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
