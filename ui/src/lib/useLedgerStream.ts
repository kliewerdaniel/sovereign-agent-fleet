"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { AuditEntry } from "@/lib/fleet";

const BASE = process.env.NEXT_PUBLIC_FLEET_API ?? "http://127.0.0.1:8788";

// Bounded SSE subscription to /ledger/stream. On each audit.append we prepend
// the new entry. We cap the buffer so a busy chain never grows unbounded.
export function useLedgerStream(initial: AuditEntry[] = [], cap = 200) {
  const [entries, setEntries] = useState<AuditEntry[]>(initial);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const ingest = useCallback(
    (e: AuditEntry) => {
      setEntries((prev) => {
        if (prev.some((p) => p.id === e.id)) return prev;
        return [e, ...prev].slice(0, cap);
      });
    },
    [cap]
  );

  // seed from the REST ledger so we don't wait for the first event
  useEffect(() => {
    let alive = true;
    fetch(`${BASE}/ledger?limit=${cap}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (alive && d?.entries) setEntries(d.entries.slice().reverse());
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [cap]);

  useEffect(() => {
    const es = new EventSource(`${BASE}/ledger/stream`);
    esRef.current = es;
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg?.event === "audit.append" && msg.entry) ingest(msg.entry);
      } catch {
        /* ignore malformed frame */
      }
    };
    return () => es.close();
  }, [ingest]);

  return { entries, connected, ingest };
}
