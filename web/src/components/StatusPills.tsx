import type { Authorization, Verification } from "@/lib/types";

export function AuthPill({ auth, needs }: { auth: Authorization | string; needs?: boolean }) {
  const cls =
    auth === "BLOCKED"
      ? "pill pill-danger"
      : needs
        ? "pill pill-warn"
        : "pill pill-ok";
  return <span className={cls}>{auth}</span>;
}

export function VerifyPill({ v }: { v: Verification | string }) {
  const cls =
    v === "HALLUCINATION"
      ? "pill pill-danger"
      : v === "ASSERTED"
        ? "pill pill-warn"
        : "pill pill-ok";
  return <span className={cls}>{v}</span>;
}
