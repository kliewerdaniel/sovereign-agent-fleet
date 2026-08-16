// Bridge connection config.
//
// Server-side fetches (chain integrity, runs) talk to the bridge directly.
// Client-side WS/REST use NEXT_PUBLIC_BRIDGE_URL (same-origin in prod via the
// next.config rewrite; localhost:8787 in dev).

export const BRIDGE_BASE_URL =
  process.env.BRIDGE_BASE_URL ?? "http://127.0.0.1:8787";

export const BRIDGE_PUBLIC_URL =
  process.env.NEXT_PUBLIC_BRIDGE_URL ?? "http://127.0.0.1:8787";

export const WS_URL = BRIDGE_PUBLIC_URL.replace(/^http/, "ws") + "/ws";
