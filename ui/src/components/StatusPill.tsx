import { BadgeCheck, AlertTriangle, ShieldX, Clock } from "lucide-react";

type Tone = "ok" | "warn" | "danger" | "info";

export function StatusPill({
  tone,
  children,
}: {
  tone: Tone;
  children: React.ReactNode;
}) {
  const cls =
    tone === "ok"
      ? "badge badge-ok"
      : tone === "warn"
      ? "badge badge-warn"
      : tone === "danger"
      ? "badge badge-danger"
      : "badge badge-info";
  return <span className={cls}>{children}</span>;
}

export function DecisionBadge({ decision }: { decision: string }) {
  if (decision === "AUTO" || decision === "approve" || decision === "grant")
    return <StatusPill tone="ok">{decision}</StatusPill>;
  if (decision === "HUMAN" || decision === "require_approval" || decision === "reject" || decision === "pending")
    return <StatusPill tone="warn">{decision}</StatusPill>;
  if (decision === "BLOCKED" || decision === "deny" || decision === "blocked")
    return <StatusPill tone="danger">{decision}</StatusPill>;
  return <StatusPill tone="info">{decision}</StatusPill>;
}

export function VerificationBadge({ v }: { v: string }) {
  if (v === "VERIFIED") return <StatusPill tone="ok">VERIFIED</StatusPill>;
  if (v === "ASSERTED") return <StatusPill tone="warn">ASSERTED</StatusPill>;
  if (v === "HALLUCINATION") return <StatusPill tone="danger">HALLUCINATION</StatusPill>;
  return <StatusPill tone="info">{v}</StatusPill>;
}

export const KIND_TONE: Record<string, Tone> = {
  "researcher.emit": "info",
  "analyst.qualify": "info",
  "gateway.grant": "ok",
  "gateway.deny": "danger",
  "operator.needs_approval": "warn",
  "operator.approval.signed": "ok",
  "operator.approval.rejected": "danger",
  "operator.final": "ok",
  "operator.blocked": "danger",
  "runtime.injection": "danger",
  "registry.publish": "info",
  "registry.revoke": "warn",
  "registry.rotate": "warn",
  "registry.root_rotate": "warn",
};

export function KindBadge({ kind }: { kind: string }) {
  const tone = KIND_TONE[kind] ?? "info";
  return <StatusPill tone={tone}>{kind}</StatusPill>;
}
