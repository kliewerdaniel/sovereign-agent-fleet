# 17. Judging / Submission Strategy

## 17.1 Judging criteria we can infer (Fleet track)
The Fleet track rewards: agents **cataloged** for cross-dept use, **safe context across weeks** of async ops, **production-data interaction without violating** compliance/sovereignty/security. Our design hits all three:
- Cataloged → Agent Registry (setup beat, D10).
- Safe cross-session context → Memory Bank encrypted + checkpointed lifecycle.
- Compliance/sovereignty/security → local-first (D3), capability policy (D9), Model Armor (D12), tamper-evident audit (D13).

## 17.2 How to make judges *feel* the architecture
- Lead with the thesis: "intelligence probabilistic, authority deterministic." Every demo beat returns to it.
- Show the **Gateway deny** + **tamper alert** + **cert reject** ON SCREEN — these are the "governable not just autonomous" proof.
- Architecture diagram must label the 7 hackathon components (03.2) so judges tick the rubric mentally.

## 17.3 Required submission artifacts (09)
- [ ] Repo (share w/ testing@devpost.com + cloudhackathons@google.com)
- [ ] README spin-up (local + Cloud Run deploy)
- [ ] Architecture diagram (visual)
- [ ] 4-min video (GCP console proof: Cloud Run / Vertex / Firestore)
- [ ] This planning package as the design doc

## 17.4 Bonus capture
- **Gemma:** local entity-resolution sub-task, documented (D2). Real model, real work.
- **Blog:** architecture write-up on public platform, states "for the purposes of entering this hackathon."
- **Social:** #AllThingsAgenticHackathon post on X/LinkedIn.

## 17.5 Secondary target — Best Architectural Design ($5k)
Our documentation-first approach + ADR set (10) + clean separation of the 7 security properties (04.1) positions us here. Emphasize in write-up: decision discipline, no invented crypto, reuse over rewrite.

## 17.6 Demo recording checklist (from 08)
- [ ] Problem + thesis (0:30)
- [ ] Live R→A→O + Registry beat (1:30)
- [ ] 8 adversarial beats (1:30) — deny/approve/tamper/forge/revoke-rotate visible
- [ ] Architecture diagram + GCP console proof (0:45)
- [ ] Close + repo pointer

## 17.7 Anti-patterns to avoid
- Do NOT claim "zero trust" if we only have single root — say "root-of-trust, single anchor" (05.9).
- Do NOT present GCP as authoritative — it's verifiable storage (D6).
- Do NOT let Gemini touch policy in the video — brain-only (D15).
