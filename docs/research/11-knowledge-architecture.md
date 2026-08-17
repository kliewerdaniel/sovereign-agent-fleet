# 11. Knowledge Architecture (where SKC / GraphRAG / vectors fit)

## Principle
Knowledge representation belongs to the **Analyst** (judge), not the Researcher (gatherer) — consistent with the hard handoff (D8). The fleet does not need a global knowledge store to demonstrate governance; knowledge is a capability the Analyst uses to *qualify* evidence.

## Components
| Asset | Role in fleet | Owner |
|-------|---------------|-------|
| **Sovereign Knowledge Compiler (SKC)** | Compiles extracted sources into structured, versioned knowledge artifacts the Analyst reasons over | Analyst |
| **GraphRAG** | Entity-resolution + relationship graph over qualified intel; supports "why this prospect qualifies" traces | Analyst |
| **Vector retrieval** | Researcher source discovery + Analyst similarity/conflict checks | Researcher (discovery) / Analyst (conflict) |
| **Transient graphs** | Per-task working graph discarded after FINAL; not persisted to ledger | Analyst (runtime) |
| **Compiled artifacts** | SKC output referenced by `QualifiedIntel.evidence_refs` (deterministic link) | Analyst → ledger |

## Boundary rules
- GraphRAG/vector state is **working memory**, not authoritative audit. Only the signed `QualifiedIntel` + its `evidence_refs` enter the ledger.
- Knowledge retrieval provenance (which source, which embed) is captured in `SourcedEvidence.source_hash` so a qualification claim is always traceable to a retrieved source.
- No model-free "knowledge" is trusted as fact; qualification confidence is explicit and bounded to cited evidence (failure model #1).

## Resolved (D19)
Graph stays **local** (owner decision). Firestore Audit Ledger mirror (the "Memory Bank" component) carries only the *compiled artifact manifest* — hashes + evidence refs, not the graph — preserving local-first authority (D3/D6). Cross-session continuity uses the manifest; the working graph is rebuilt locally per task.
