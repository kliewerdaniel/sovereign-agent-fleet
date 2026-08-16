"use client";

import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
import type { AuditEntry } from "@/lib/types";

// Kind -> node color (mirrors globals.css trust palette).
const KIND_COLOR: Record<string, string> = {
  "registry.publish": "#5b6675",
  "analyst.qualify": "#58a6ff",
  "gateway.grant": "#3fb950",
  "operator.needs_approval": "#d29922",
  "operator.approval.signed": "#d29922",
  "operator.approval.rejected": "#f85149",
  "operator.final": "#3fb950",
  "operator.blocked": "#f85149",
  "researcher.emit": "#58a6ff",
};

function shortId(id: string): string {
  // zero-padded seq id -> seq number label
  return String(parseInt(id, 10));
}

// Builds the genuine tamper-evident chain: each entry's `prev` is the running
// hash of its parent. We draw edges by sequence order (entry[i-1] -> entry[i]),
// since that is exactly the parent link ledgered by fleet/crypto/chriscrypt/ledger.py.
function toElements(entries: AuditEntry[]) {
  const ordered = [...entries].sort((a, b) => a.seq - b.seq);
  const nodes = ordered.map((e) => ({
    data: {
      id: e.id,
      label: `${shortId(e.id)}:${e.kind}`,
      kind: e.kind,
      color: KIND_COLOR[e.kind] ?? "#8b98a8",
    },
  }));
  const edges = ordered.slice(1).map((e) => ({
    data: { id: `e_${e.id}`, source: ordered[e.seq - 1].id, target: e.id, prev: e.prev },
  }));
  return [...nodes, ...edges];
}

export function AuditGraph({ entries }: { entries: AuditEntry[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const selectedRef = useRef<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const cy = cytoscape({
      container: containerRef.current,
      elements: toElements(entries),
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            label: "data(label)",
            color: "#e6edf3",
            "font-size": "9px",
            "font-family": "var(--font-mono), ui-monospace, monospace",
            "text-valign": "center",
            "text-halign": "center",
            width: 26,
            height: 26,
            "border-width": 1,
            "border-color": "#2a3441",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#2a3441",
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#2a3441",
          },
        },
        {
          selector: "node:selected",
          style: { "border-width": 3, "border-color": "#58a6ff" },
        },
      ],
      layout: { name: "breadthfirst", directed: true, padding: 12 } as cytoscape.LayoutOptions,
    });
    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [entries]);

  return (
    <div className="space-y-2">
      <div className="divider-label">Hash-chain graph · edge = sha256(parent body) bound by Ed25519 sig</div>
      <div
        ref={containerRef}
        className="card"
        style={{ height: 320, width: "100%" }}
        aria-label="audit hash-chain graph"
      />
    </div>
  );
}
