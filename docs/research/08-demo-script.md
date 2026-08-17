# 8. Demonstration Script

## 8.1 Scenario (MVD, D11)
"Find 20 qualified prospects matching a defined ICP and prepare personalized outreach" — executed against a **simulated** DailySalesOS CRM. No real sends, no real PII.

### R→A→O flow
- **Researcher:** discovers candidates, gathers sources, emits `SourcedEvidence` (citation + extract + source hash + provenance).
- **Analyst:** evaluates candidates, determines qualification, structures intelligence, emits `QualifiedIntel` (classification + entity resolution + confidence bound to evidence refs), flags uncertainty.
- **Operator:** prepares outreach + CRM draft; **requests authorization** for consequential `crm_write`; on approval, executes; artifact + evidence + audit entry.
- **Policy layer:** allows low-risk; blocks unauthorized; requires approval for consequential.
- **Security layer:** records identity, signs events, encrypts sensitive state, maintains tamper-evident ledger.
- **Verification layer:** checks evidence, validates outputs, detects unsupported claims.
- **Human:** approves the selected consequential action.
- **Audit:** complete execution history.

### Registry setup beat (D10)
Short segment: Researcher published + versioned in Agent Registry; a second "department" discovers it. Shows cross-department cataloging without a 4th live agent.

## 8.2 4-minute video shot plan (Q3 accepted)
| Time | Beat | Shows |
|------|------|-------|
| 0:00–0:30 | Problem + thesis | "intelligence probabilistic, authority deterministic" |
| 0:30–1:30 | Live ICP scenario R→A→O + Registry setup beat | real multi-step agentic execution |
| 1:30–3:00 | Adversarial 8 beats (sec 7) | governability: block/deny/approve/tamper/forge/revoke-rotate |
| 3:00–3:45 | Architecture diagram + (optional) GCP replication proof | Cloud Run / Gemini / Firestore console (opt-in; default local) |
| 3:45–4:00 | Close | thesis restate + repo/README pointer |

## 8.3 Gemma bonus (honest)
Run a **local Gemma** for one sub-task — e.g., Analyst's entity-resolution draft — as a real model doing real work, distinct from the mandated Gemini 3.5 Flash. Documented as bonus integration, not the primary brain.

## 8.4 Recording notes
- Keep adversarial beats punchy; show the *signed deny / tamper alert / cert reject* on screen.
- GCP replication proof (opt-in) shows the console (Cloud Run service, Gemini endpoint, Firestore ledger); the default runtime is local-first. Vertex AI is not used in the current code.
- Safe to demo: CRM is simulated; no external sends.
