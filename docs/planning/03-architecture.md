# 3. Architecture

## 3.1 Central principle
> **Do not trust the model. Trust the execution protocol.**

The model may propose plans, actions, tool calls, and interpretations. The **deterministic Control Plane** decides: authority, permission, available tools, required evidence, required verification, required approval, what is recorded, and how the event is cryptographically protected. The enforcer is never probabilistic.

## 3.2 Public vocabulary → Sovereign implementation (hackathon alignment)
The Fortified Enterprise Fleet track defines 7 component classes. We adopt these as our **public** architecture vocabulary and map each to an existing Sovereign/ChrisCrypt implementation.

| # | Hackathon component | Role | Sovereign / ChrisCrypt implementation |
|---|---------------------|------|----------------------------------------|
| 1 | **Agent Registry** | publish/version/discover enterprise agents | Sovereign Worker agent catalog (D10 setup beat) |
| 2 | **Agent Runtime** | long-running async background execution | Sovereign Worker runtime + lifecycle state machine |
| 3 | **Memory Bank** | persistent secure cross-session context | Encrypted local state (ChrisCrypt) + Firestore mirror |
| 4 | **Agent Identity** | zero-trust access control | ChrisCrypt Ed25519 identity + root-of-trust cert (D13) |
| 5 | **Agent Gateway** | unified routing + policy enforcement | Sovereign Worker policy/control plane (capability-based) |
| 6 | **Model Armor** | inline guardrails (injection/tool-poisoning/PII) | Structural + deterministic controls (D12) |
| 7 | **Agent Observability** | OTel audit logs + reasoning traces | Audit ledger + traces, exported OTel-compliant |

## 3.3 Control Plane (deterministic infrastructure — NOT fleet agents, D9)
- **Identity Root (root-of-trust):** holds the Control Plane root key; issues + signs each agent's identity certificate; maintains revocation + rotation.
- **Registry:** publishes/versions/discovers agents.
- **Policy/Gateway:** capability-based authorization; the only component that issues/denies authority.
- **Runtime:** executes worker lifecycle; checkpointing; idempotency.
- **Memory Bank:** persistent encrypted state.
- **Model Armor:** structural guardrails at boundaries.
- **Observability:** audit ledger + reasoning traces, OTel export.

The **fleet** = the worker agents (Researcher, Analyst, Operator) that *request authority* from the Control Plane. They are probabilistic; the Control Plane is not.

## 3.4 Fleet agents (the 3 executing workers, D8/D10/D11)
### Researcher — *gather*
- Emits **sourced raw evidence**: citation + extract + source hash + retrieval provenance.
- Forbidden from *judging* evidence (capability separation).
- Tools: web research, document retrieval, structured extraction, source collection.
- Gemini use: synthesis of findings only.

### Analyst — *judge*
- Consumes Researcher evidence; emits **qualified structured intelligence**: classification, entity resolution, confidence bound to specific evidence IDs.
- Tools: classification, entity resolution, knowledge representation, qualification, synthesis, confidence/evidence analysis.
- Gemini use: classification + confidence reasoning only.
- Reuses SKC / GraphRAG for knowledge representation (see 11).

### Operator — *act**
- Prepares artifacts (CRM draft, outreach) and executes **approved** consequential actions.
- Tools: modify structured business state (simulated), prepare CRM ops, generate artifacts, communicate results.
- Gemini use: draft outreach copy only.
- Consequential actions (CRM write / outreach send) require APPROVAL state before FINAL.

## 3.5 Handoff contract (hard boundary, D8)
Researcher → Analyst → Operator is enforced **at the protocol boundary by schema**, not by trust:
- Researcher output schema: `SourcedEvidence { citation, extract, source_hash, retrieval_provenance, researcher_sig }`
- Analyst output schema: `QualifiedIntel { classification, entities, confidence, evidence_refs[], analyst_sig }` where `evidence_refs` MUST cite valid `SourcedEvidence` IDs.
- Operator input: only `QualifiedIntel` records (never raw model text). The protocol rejects an Operator action whose inputs don't resolve to signed evidence.

## 3.6 Topology — local-first with verifiable cloud artifacts (D3/D6)
```
[ LOCAL — sovereign runtime, keys never leave ]
  ChrisCrypt: root key, agent Ed25519 keys, per-record XChaCha20 keys
  Sovereign Worker: Identity/Poilicy/Gateway/Runtime/Memory/ModelArmor
  Gemini 3.5 Flash (called from within R/A/O for probabilistic brain only)
        │  signed evidence + hash-chain audit entries replicate OUT
        ▼
[ GCP — verifiable artifacts, no authority ]
  Cloud Run      → runtime + gateway endpoints (deployed proof)
  Firestore      → tamper-evident audit ledger + Memory Bank mirror
  Pub/Sub        → async task bus (R→A→O handoffs, redelivery)
  Vertex AI      → Gemini 3.5 Flash endpoint (shown in console for video)
```
Anyone holding the agent **public** keys can verify signatures; walking the hash-chain detects alteration. GCP holds *data*, sovereignty holds *authority*.

## 3.7 Lifecycle (Sovereign Worker, unchanged shape)
REQUEST → INTENT → PLAN → ACTION → TOOL → OBSERVATION → EVIDENCE → VERIFICATION → ARTIFACT → APPROVAL → FINAL → AUDIT
Each transition is a checkpointed state; FINAL only after APPROVAL (failure model: partial completion).

## 3.8 Open architecture question (to confirm in impl phase)
Does ADK wrap the local Sovereign runtime as the outer orchestration shell, with Sovereign as the inner deterministic protocol? Recommendation: **ADK = agent shell/orchestration; Sovereign = enforcement protocol; Gemini = model called via ADK tool.** Confirm during implementation.
