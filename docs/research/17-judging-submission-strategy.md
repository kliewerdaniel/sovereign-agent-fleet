# 17. Judging / Submission Strategy

> **Reality check:** the Fleet track framing below was written early. The current repo
> (D27–D30) is a **general-purpose governance substrate** (`fleet/`) with two financial
> reference workloads (`fleet/fin/`, `exchange/`) plus a real ZK attestation layer
> (`exchange/quant/zk.py`). The strongest judge-facing story is now *architecture + verifiable
> governance + domain-generality proof*, not a specific hackathon "7 components" checklist.
> Keep this doc's rubric-alignment discipline; update specifics to the shipped code.

## 17.1 Judging criteria we can infer (Fleet track)
The Fleet track rewards: agents **cataloged** for cross-dept use, **safe context across weeks**
of async ops, **production-data interaction without violating** compliance/sovereignty/security.
Our design hits all three:
- Cataloged → Agent Registry (`fleet/layers/registry.py`).
- Safe cross-session context → signed, tamper-evident `AuditLedger` (replicated, verifiable
  by public key — never trust the model, trust the protocol).
- Compliance/sovereignty/security → local-first authority (keys never leave the control plane),
  capability policy (default-deny property test), Model Armor, tamper-evident audit.

## 17.2 How to make judges *feel* the architecture
- Lead with the thesis: "intelligence probabilistic, authority deterministic." Every demo beat
  returns to it.
- Show the **Gateway deny** + **tamper alert** + **cert reject** ON SCREEN — these are the
  "governable not just autonomous" proof. (8-beat adversarial demo: `demo/sovereign_agent_fleet_demo.mp4`.)
- Architecture diagram (`docs/assets/architecture.svg` + `.png`) labels the layers: cognition →
  governance → execution → verification, with the import walls (M0) drawn explicitly.

## 17.3 Required submission artifacts
- [ ] Repo (share w/ testing@devpost.com + cloudhackathons@google.com)
- [ ] README spin-up (local `pip install -r requirements.txt && pytest` + optional `FLEET_MODE=gcp` deploy)
- [ ] Architecture diagram (visual) — done (`docs/assets/architecture.svg`)
- [ ] Demo video(s): adversarial 8-beat (`demo/sovereign_agent_fleet_demo.mp4`) + exchange quant
      pipeline (`demo/exchange_demo/exchange_demo_1080p.mp4`); live script `python demo/quant_demo.py`
- [ ] Design doc set under `docs/research/` (this package)

## 17.4 Bonus capture
- **Gemma:** local entity-resolution brain (`fleet/layers/brain.py`), real model, real work.
- **Blog:** architecture write-up on public platform, states "for the purposes of entering this
  hackathon."
- **Social:** #AllThingsAgenticHackathon post on X/LinkedIn.

## 17.5 Secondary target — Best Architectural Design
Our documentation-first approach + ADR set (D1–D20) + clean separation of the security properties
positions us here. Emphasize in write-up: decision discipline, **no invented crypto** (vendored
ChrisCryptSN, real Ed25519/XChaCha20/Argon2id), reuse over rewrite, and the **M0 proof** (Run A =
Run B — removing all cognition leaves the authorization verdict unchanged).

## 17.6 Demo recording checklist
- [ ] Problem + thesis (0:30)
- [ ] Researcher→Analyst→Operator + Registry beat (1:30)
- [ ] 8 adversarial beats (1:30) — deny/approve/tamper/forge/revoke-rotate visible
- [ ] Architecture diagram + verification (public-key recompute) proof (0:45)
- [ ] Close + repo pointer

## 17.7 Anti-patterns to avoid
- Do NOT claim "zero trust" if we only have single root — say "root-of-trust, single anchor".
- Do NOT present GCP as authoritative — it's verifiable storage; default runtime is local
  (`FLEET_MODE=local`), live is opt-in.
- Do NOT let Gemini touch policy in the video — brain-only (D15). Cognition is import-walled
  from the decision function (M0).
- Do NOT re-introduce the "zero-knowledge" label for `exchange/quant/zk.py` — it is a genuine
  Σ-protocol *range* proof (selective-disclosure + real ZK), named precisely.
