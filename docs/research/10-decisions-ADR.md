# 10. Architecture Decision Records (D1–D15)

Format: Decision / Alternatives / Reason / Consequences / Status

### D1 — Track = Fortified Enterprise Fleet (+ Architecture secondary)
- **Alt:** Taskmaster, Collaborative Partner.
- **Reason:** fleet/sovereignty thesis maps exactly; defined component vocab aligns with existing assets.
- **Consequences:** must implement all 7 fleet components; heavier than other tracks but maximizes reuse.
- **Status:** Accepted

### D2 — Gemini 3.5 Flash mandatory; Gemma locally for bonus
- **Alt:** Gemini only; Gemma as primary.
- **Reason:** rules mandate Gemini 3.5 Flash; Gemma earns bonus, kept local to preserve sovereignty.
- **Consequences:** two models in stack; clear separation (Gemini=cloud brain, Gemma=local sub-task).
- **Status:** Accepted

### D3 — Crypto + execution protocol local-first; Gemini/ADK = cloud brain only
- **Alt:** full cloud deployment; hybrid.
- **Reason:** owner's non-negotiable (choice A): sovereignty of authority/keys.
- **Consequences:** GCP holds verifiable artifacts, not authority; satisfies rules without surrendering keys.
- **Status:** Accepted

### D4 — Reuse ChrisCrypt + Sovereign modules
- **Alt:** rewrite crypto/runtime.
- **Reason:** owner has working modules; avoids reinventing primitives.
- **Consequences:** integration effort instead of build; lower risk.
- **Status:** Accepted

### D5 — GCP = Cloud Run + Firestore + Pub/Sub
- **Alt:** Cloud SQL, GKE.
- **Reason:** serverless, ~zero idle cost, covers runtime/gateway + ledger/memory + async bus.
- **Consequences:** Firestore document model for ledger; Pub/Sub for handoffs.
- **Status:** Accepted

### D6 — Authority/keys local; verifiable artifacts replicate to GCP
- **Alt:** ledger fully local, GCP mirror only.
- **Reason:** owner agreed; GCP storage still verifiable by public key.
- **Consequences:** clear boundary; GCP proof straightforward.
- **Status:** Accepted

### D7 — Public vocab = hackathon 7 components → Sovereign impl
- **Alt:** invent own vocabulary.
- **Reason:** maximizes judging alignment.
- **Consequences:** docs map 1:1 to rubric.
- **Status:** Accepted

### D8 — Hard handoff: Researcher=sourced evidence; Analyst=qualified intel
- **Alt:** merge R+A; let Researcher judge.
- **Reason:** capability separation makes two real agents, not one split; protocol enforces at boundary.
- **Consequences:** schema enforcement required at handoff.
- **Status:** Accepted

### D9 — Control Plane = deterministic infra, not fleet agents
- **Alt:** a "Governor" agent in the fleet.
- **Reason:** keeps "don't trust the model" crisp; enforcer never probabilistic.
- **Consequences:** fleet = 3 workers requesting authority.
- **Status:** Accepted

### D10 — 3 executing workers; Registry discovery as setup beat
- **Alt:** 4th discovering agent live.
- **Reason:** small demonstrable fleet; Registry shown without 4th agent complexity.
- **Consequences:** Registry demo is a setup segment, not in-scenario.
- **Status:** Accepted

### D11 — Demo = simulated DailySalesOS CRM, no real sends/PII
- **Alt:** real CRM integration.
- **Reason:** safe to demo; satisfies "safe" + "easy to record".
- **Consequences:** consequential actions are simulation; still real protocol enforcement.
- **Status:** Accepted

### D12 — Model Armor = structural + deterministic
- **Alt:** add LLM-based injection classifier.
- **Reason:** avoid probabilistic component in a security control; structural defense has no execution surface.
- **Consequences:** three sub-threats handled structurally; no classifier to tune.
- **Status:** Accepted

### D13 — Key hierarchy + root-of-trust certifies each agent identity
- **Alt:** self-signed agent keys; no root.
- **Reason:** gives forged-identity rejection path (beat 7) + clean revocation.
- **Consequences:** root key is sole trust anchor (documented scope boundary).
- **Status:** Accepted

### D14 — Live key rotation in scope
- **Alt:** revocation-list only (legacied).
- **Reason:** cheap given D13; stronger adversarial story (revoke→rotate→resume).
- **Consequences:** recovery path, not just freeze.
- **Status:** Accepted

### D15 — Gemini = probabilistic brain only; never for policy/signing
- **Alt:** let Gemini advise on policy.
- **Reason:** protocol must own authority; model stays probabalistic.
- **Consequences:** clean separation; Gemini calls isolated to R/A/O generation.
- **Status:** Accepted

### D16 — Verification gate quantifies VERIFIED vs ASSERTED
- **Alt:** qualitative confidence only (status quo before this decision).
- **Reason:** verification layer must be testable + deterministic at the boundary; "confidence" alone is unverifiable.
- **Consequences:** Analyst must link every predicate to ≥1 valid SourcedEvidence; required weights (ICP-fit ≥2, role ≥1, budget-auth ≥2) + 0.6 threshold; unsupported claim = HALLUCINATION flag, not recorded verified.
- **Status:** Accepted

### D17 — Human approver has own root-certified Ed25519 identity; approval console served on Cloud Run, key stays local
- **Alt:** approval fully local (no cloud UI); or human key in cloud.
- **Reason:** real signed approval demonstrable + GCP-proof (on Cloud Run) while preserving sovereignty (key/device-bound local, D3/D6); only signed ApprovalRecord replicates.
- **Consequences:** human identity in cert chain; console is another Cloud Run surface; beat 4 becomes a signed, recordable interface.
- **Status:** Accepted

### D18 — Local abliterated Gemma4 = universal dev/test brain; Gemini 3.5 Flash = submission demo brain
- **Alt:** Gemini for all dev+demo; Gemma only as one sub-task.
- **Reason:** owner wants to build/test own infra without credit burn or model refusals; abliterated Gemma4 is free/local/controllable across all use cases. Gemini reserved for the mandated demo.
- **Consequences:** brain is a pluggable interface (model = config, not code); same test suite validates both; near-zero Gemini spend until final demo.
- **Status:** Accepted

### D19 — Graph stays local; Firestore mirror = manifest-only
- **Alt:** mirror full graph to Firestore.
- **Reason:** owner decision — preserve local-first authority (D3/D6); graph is working memory, not authoritative audit.
- **Consequences:** Audit Ledger (the "Memory Bank" component) holds hashes + evidence refs only; working graph rebuilt locally per task; cross-session continuity via manifest.
- **Status:** Accepted

### D20 — Google agent framework = GenAI SDK (Gemini API direct); Sovereign = orchestration/enforcement
- **Alt:** ADK as outer orchestration shell (13.6 open Q).
- **Reason:** owner prefers calling Gemini directly; GenAI SDK satisfies the "≥1 Google agent framework" rule; Sovereign owns orchestration + enforcement.
- **Consequences:** ADK not required; brain call is direct GenAI SDK; cleaner separation than ADK wrapping.
- **Status:** Accepted
