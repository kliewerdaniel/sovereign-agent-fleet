"use client";

import { useEffect, useRef, useState } from "react";
import { WS_URL } from "@/lib/config";

interface LiveEvent {
  type: string;
  run_id: string;
  at: number;
  summary: string;
}

function summarize(e: Record<string, unknown>): string {
  const t = String(e["type"] ?? "?");
  if (t === "AuditEntryAppended") {
    const entry = (e["entry"] as Record<string, unknown>) ?? {};
    return `audit · ${(entry["kind"] as string) ?? "?"} (#${entry["seq"] ?? "?"})`;
  }
  if (t === "ApprovalSigned") {
    const a = (e["approval"] as Record<string, unknown>) ?? {};
    return `approval signed · ${(a["decision"] as string) ?? "?"} by ${(a["human_id"] as string) ?? "?"}`;
  }
  return t;
}

export function LiveConsole() {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let closed = false;
    function connect() {
      if (closed) return;
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!closed) setTimeout(connect, 2000);
      };
      ws.onmessage = (m) => {
        try {
          const data = JSON.parse(m.data) as Record<string, unknown>;
          setEvents((prev) =>
            [
              {
                type: String(data["type"] ?? "?"),
                run_id: String(data["run_id"] ?? ""),
                at: Date.now(),
                summary: summarize(data),
              },
              ...prev,
            ].slice(0, 50),
          );
        } catch {
          /* ignore malformed */
        }
      };
    }
    connect();
    return () => {
      closed = true;
      wsRef.current?.close();
    };
  }, []);

  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${connected ? "bg-[var(--color-ok)]" : "bg-[var(--color-danger)]"}`} />
        <span className="divider-label">
          live bridge · {connected ? "connected" : "reconnecting…"} · {WS_URL}
        </span>
      </div>
      <div className="space-y-1 max-h-96 overflow-y-auto">
        {events.length === 0 && (
          <div className="text-xs text-[var(--color-ink-faint)] mono">
            waiting for fleet events — launch a run from /pipelines/new
          </div>
        )}
        {events.map((e, i) => (
          <div
            key={`${e.at}-${i}`}
            className="flex items-center gap-3 text-xs border border-[var(--color-edge)] rounded px-3 py-1.5"
          >
            <span className="mono text-[var(--color-ink-faint)] w-16">
              {new Date(e.at).toLocaleTimeString()}
            </span>
            <span className="mono text-[var(--color-ink)] flex-1">{e.summary}</span>
            {e.run_id && (
              <span className="mono text-[var(--color-ink-dim)] text-[0.65rem]">
                {e.run_id.slice(0, 12)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
