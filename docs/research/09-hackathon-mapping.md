# 9. Hackathon Requirements Mapping

## Mandatory (every project)
| Requirement | How satisfied | Evidence for judges |
|-------------|---------------|---------------------|
| Gemini 3.5 Flash via Gemini API or Vertex AI | Probabilistic brain inside R/A/O (D15) | Vertex AI console in video; calls in code |
| ≥1 Google agent framework (ADK/GenAI/GenKit/Antigravity) | **GenAI SDK** (Gemini API called directly); Sovereign = orchestration/enforcement (D20, resolves 3.8) | GenAI SDK calls in repo |
| ≥1 GCP service (Cloud Run/SQL/Firestore/GKE/Pub/Sub) | **Cloud Run + Firestore + Pub/Sub** (D5) | console in video |
| Fortified Enterprise Fleet track | Thesis maps exactly; 7 components implemented | this doc + demo |
| Repo (share w/ testing@devpost.com, cloudhackathons@google.com) | public/private repo | README spin-up |
| README spin-up instructions | step-by-step local + deploy | README.md |
| Architecture diagram | visual system map | diagram file |
| ~4-min demo video | shot plan sec 8.2 | video |

## Fortified Enterprise Fleet component coverage
| Component | Implemented by | Doc |
|-----------|----------------|-----|
| Agent Registry | Sovereign catalog (setup beat) | 03.2 #1 |
| Agent Runtime | Sovereign runtime | 03.2 #2 |
| Memory Bank | ChrisCrypt encrypted state + Firestore mirror | 03.2 #3 |
| Agent Identity | ChrisCrypt Ed25519 + root cert | 03.2 #4 |
| Agent Gateway | Sovereign policy/control plane | 03.2 #5 |
| Model Armor | structural/deterministic guardrails | 04.3 |
| Agent Observability | OTel audit ledger + traces | 03.2 #7 |

## Bonus (optional)
| Bonus | How | Status |
|-------|-----|--------|
| Gemma integration | local Gemma for Analyst entity-resolution sub-task | planned (D2) |
| Publish content (blog) | architecture write-up on public platform | optional |
| Social post #AllThingsAgenticHackathon | X/LinkedIn promo | optional |

## GCP Setup (owner-provisioned)
- Account: wayzoftheroachandcat@gmail.com (new GCP account, credits available).
- Project ID: `project-3ba93cec-8ca6-43c0-ba4` — **verify exact ID matches console** before video (typo risk).
- Service account principal created; gmail account granted admin IAM roles (broad privileged access — dev-only infra account; fleet identity uses least-privilege, see 16 R13).
- Status: infra provisioned; we must be **extremely conservative with credits**.
- Dev brain = local abliterated Gemma4 (free); Gemini 3.5 Flash used only for the submission demo (D18).

## Cost guardrail
- No public ingress required at judging; Cloud Run idle ~$0 (min instances 0); Firestore minimal; Pub/Sub light. Credits claimed. Dev on local Gemma4 to avoid Gemini spend until final demo.

## Submission checklist
- [ ] Repo + shares
- [ ] README spin-up (local + deploy)
- [ ] Architecture diagram
- [ ] 4-min video (GCP console proof)
- [ ] This planning package as design doc
- [ ] Gemma bonus wired
