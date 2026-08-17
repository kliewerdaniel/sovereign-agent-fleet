# D26 — Incident Triage → Authorized Remediation (Locked Use Case)

> Living plan for the Sovereign Agent Fleet hackathon use case.
> Status: IMPLEMENTED & TESTED — **205-test** suite (D26 adds 42: 14 SimEnv + 20 policy + 8 e2e on top of the baseline).
> Companion to D1–D20. Does NOT replace the crypto foundation or control plane.

## 1. Thesis (the whole point)

> **The model proposes. It cannot grant itself authority to execute.**

The strongest single demonstration:
**Evidence that a fact is true does not grant permission to act on it.**

```text
Evidence: identity-svc is compromised   → D16: VERIFIED
Capability: operator may ATTEMPT remediation
Policy:    identity-svc is PROTECTED     → BLOCKED
```

Evidence ≠ Capability ≠ Policy ≠ Authority. Each gate is independent; passing
one never implies passing another.

## 2. Use case statement

> A local-first multi-agent security operations fleet that investigates
> security incidents and performs **bounded, cryptographically authorized
> remediation inside a deterministic digital range** — autonomous where it
> safely can be, and requiring human authority where it should.

The SimEnv (digital range) is deliberately tiny: a `dict` of workloads + a pure
transition function. It exists only as a real, inspectable target for the
authority protocol. NOT a fake Kubernetes / EDR / SOC product.

## 3. Pipeline (unchanged roles, incident framing)

```text
Researcher  → SourcedEvidence   (telemetry, CANNOT judge)
Analyst     → QualifiedIntel    (severity + D16, CANNOT act)
Operator    → proposes action, clears 3 gates, executes SimEnv transition
Human       → signs bound ApprovalRecord for HUMAN-cell actions
Gateway     → sole issuer of authority (capability + signed deny event)
Policy      → pure: verification × severity × blast_radius × asset_class
```

## 4. SimEnv entities (4, one PROTECTED class)

| id | role | blast-radius class | special rule |
|----|------|--------------------|--------------|
| `web-edge` | internet-facing app | LOW | safe AUTO remediation |
| `app-db` | database | MEDIUM | isolation needs approval |
| `revenue-svc` | revenue-critical | HIGH | always HUMAN, even LOW |
| `identity-svc` | auth / DC | PROTECTED | `isolate`/`quarantine` **prohibited** regardless of evidence/severity |

States (one-directional, no restore): `RUNNING → ISOLATED → QUARANTINED`,
`RUNNING → EGRESS_BLOCKED`.

## 5. Remediations (3, graded blast radius)

| action | → state | precondition | blast | prohibited on |
|--------|---------|--------------|-------|---------------|
| `block_egress` | EGRESS_BLOCKED | RUNNING | LOW | — |
| `isolate` | ISOLATED | RUNNING (idempotent) | HIGH | identity-svc |
| `quarantine` | QUARANTINED | RUNNING (idempotent) | HIGH | identity-svc |

`transition(workload, state, action) -> (new_state, ok)` is a **pure function**.
Idempotent no-ops return same state (replay safe). The real change becomes a
signed `operator.final` event: `{workload_id, prev_state, new_state, action,
agent, capability, artifact_hash, ts}`.

## 6. Evidence schema (D8 enforced: two distinct quantities)

Researcher `SourcedEvidence` (NO severity/classification field):
```
{ evidence_id, agent_id, citation, workload_id, indicator,
  observed_state, confidence, telemetry_source, source_hash }
```
Analyst `QualifiedIntel` predicate (NO execution field):
```
{ claim:"compromised", target_id, severity:LOW|MEDIUM|HIGH,
  confidence:0..1, verification:VERIFIED|ASSERTED|HALLUCINATION,
  evidence_refs:[...], analyst_id }
```
`severity` (how bad) and `confidence`/verification (D16: how well backed by
distinct verified refs) are SEPARATE axes. Policy consumes both.

## 7. Authorization model — three independent gates

```text
Evidence (D16: is the claim backed by verified observation?)
   ↓
Capability (does the cert permit this ACTION class? — Gateway)
   ↓
Policy (is THIS action on THIS asset in THIS context allowed?)
   ↓
Approval (bound human signature, when required)
   ↓
Execution (SimEnv transition inside idempotent _commit)
```
"workload X is compromised" ⇒ evidence. It does NOT ⇒ "agent Y may isolate X"
(capability) nor "this isolate is permitted now" (policy).

## 8. Policy matrix (pure, deterministic, model-independent)

```text
required_authorization(verification, severity, blast_radius, asset_class)
   -> AUTO | HUMAN | BLOCKED
```

| verification | severity | blast | asset | → decision |
|---|---|---|---|---|
| HALLUCINATION | — | — | — | BLOCKED |
| VERIFIED | LOW | LOW | any | AUTO |
| VERIFIED | LOW/MED | MED/HIGH | non-protected | HUMAN |
| VERIFIED | HIGH | any | any | HUMAN |
| VERIFIED | any | — | revenue-svc | HUMAN (always) |
| VERIFIED | any | — | identity-svc(isol/quar) | BLOCKED (prohibited) |
| ASSERTED | any | any | any | HUMAN |

## 9. Human approval — bound to the exact state change

`Approval.sign` binds `artifact_hash = sha256(workload_id + action + target_state)`.
Human signs *"authorize operator to isolate web-edge → ISOLATED"*, not a vague
incident. Forged / rebound-to-different-target / replayed ⇒ `verify_approval`
rejects fail-closed (already tested in D17/A1/A2).

## 10. Agent responsibilities

- **Researcher**: gather telemetry from signed `edr-sim` tool envelope; emit raw
  SourcedEvidence. Cannot judge.
- **Analyst**: consume evidence; assign severity; run D16; emit QualifiedIntel.
  Cannot act.
- **Operator**: consume intel; *propose a plan*; clear 3 gates; execute SimEnv
  transition inside the existing idempotent `_commit`. Cannot manufacture evidence.
- **Human**: sign bound ApprovalRecord for HUMAN-cell actions.

## 11. Trust boundaries

**Trusted:** IdentityRoot, Registry (liveness/revocation), AuditTrail hash-chain,
Policy (pure), SimEnv transition fn (pure), human Ed25519 key.
**Untrusted:** model brain (proposes only), external telemetry (signed envelope
only), any agent self-asserted claim.
**Model controls:** what it proposes. **Cannot control:** authority, verification,
signing, audit, SimEnv state.
**Auto-executes:** VERIFIED + LOW + LOW-blast. **Fails closed:** any missing
authority/approval/verification.

## 12. Attack model (3 live + 1 verifier-output; all also tests)

1. **Hallucinated / wrong target** — isolate `app-db` with no citing evidence ⇒
   D16 HALLUCINATION ⇒ BLOCKED. (proves evidence≠authority)
2. **Capability violation** — `quarantine` without the capability ⇒ Gateway deny
   + signed deny event. (proves cert-bound authority)
3. **Revoked/forged identity** — analyst cert revoked mid-run ⇒ identity fails.
   (proves crypto identity)
4. **Tampered evidence/audit** — shown via `FirestoreVerifier`/audit.verify()
   output: hash-chain FAIL. (proves tamper detection)

The `identity-svc` PROTECTED case (Evidence VERIFIED, Capability pass, **Policy
BLOCKS**) is surfaced in the normal success/failure flow (Act 3), not just as
an attack — it is the single clearest proof of the thesis.

## 13. Local / GCP boundary (unchanged)

Local-first authority; GCP = verifiable mirror only (`FirestoreVerifier`
public-key-only, no private key). SimEnv 100% local.

## 14. Brain boundary (Gemini first-class, never trusted)

```text
   GeminiBrain (probabilistic) ──PROPOSAL──┐
                                           ↓
                                  Deterministic Fleet Protocol
                                           ↓
              Evidence ─ Policy ─ Capability ─ Human ─ Execution ─ Audit
```
- `GeminiBrain` is a **first-class** production/demo backend (hackathon
  requires Gemini 3.5 Flash, D5/D20). `DeterministicBrain` for reproducible
  tests/demos. Same protocol, policy, capability, evidence, approval, SimEnv,
  audit regardless of brain.
- **No security decision ever depends on the model choosing to behave.** The
  brain proposes; the protocol decides.

## 15. UI — Streamlit, minimal, subordinate to protocol

Outside `fleet/` (`demo_app.py`). A window into the protocol, NOT part of the
trust boundary. Primary visual hierarchy:
1. Agent proposal
2. Evidence
3. Verification
4. Capability
5. Policy decision
6. Human approval (if required)
7. SimEnv state before/after
8. Signed audit event

No SOC dashboard chrome (maps/charts/live feeds). Exists to make the authority
decision visible.

## 16. Repository changes — surgical

**New:** `fleet/simenv/{__init__,env}.py`; `fleet/layers/incident.py`
(severity + authorization matrix + SimEnv binding); `test_simenv.py`,
`test_incident_policy.py`, `test_incident_e2e.py`; `demo_app.py`.
**Edit:** `runtime.Operator.act` — perform `simenv.transition(...)` inside the
existing `_commit`. `approval.py` — bind `artifact_hash` to the state change.
**Docs:** this D26; rewrite stale "no code yet" planning docs; update README/
00-INDEX. **Untouched:** crypto foundation, control plane, GCP layer, 125-test
suite.

## 17. Demo narrative (Acts 1–5)

- **Act 1 — Safe autonomy:** LOW+VERIFIED `web-edge` → `block_egress` → AUTO →
  transition → audit. (system is not "human for everything")
- **Act 2 — Consequential autonomy needs consent:** HIGH+VERIFIED `app-db` →
  `isolate` → HUMAN → exact action/state shown → human signs → transition → audit.
- **Act 3 — Evidence is not authority:** VERIFIED `identity-svc compromised` →
  `isolate identity-svc` → evidence pass → capability pass → **policy BLOCKS**.
- **Act 4 — Attack the protocol:** wrong target / missing evidence BLOCKED;
  capability violation BLOCKED; revoked agent BLOCKED; tampered audit FAIL.
- **Act 5 — Close:** "The model proposes. The protocol decides what it is
  allowed to do."

## 18. Decisions locked in this doc

- keep `identity-svc` PROTECTED (evidence true but action prohibited)
- Streamlit UI (1 new dev dep), outside core runtime
- Gemini first-class brain, deterministic downstream enforcement
- 4 SimEnv entities, 3 remediations, one-directional states
- 3 independent authorization gates; policy = verification×severity×blast×asset
- approval bound to exact state transition
- 3 live attacks + tamper shown via verifier output
- new video OUT OF SCOPE until system finalized; narration audio only after
  user starts Qwen TTS on :7860; video reference kept in README once rebuilt.

## 19. Implementation record (as shipped)

**SimEnv** (`fleet/simenv/__init__.py`, `fleet/simenv/env.py`):
- `WorkloadState` (RUNNING/ISOLATED/QUARANTINED/EGRESS_BLOCKED), `AssetClass`
  (LOW/MEDIUM/HIGH/PROTECTED), `WORKLOADS` seed (web-edge/app-db/revenue-svc/
  identity-svc), `ACTIONS` metadata (`block_egress→EGRESS_BLOCKED LOW`,
  `isolate→ISOLATED HIGH`, `quarantine→QUARANTINED HIGH`), `SimEnv` class with
  `state_of` / `apply`. `apply` enforces one-directional transitions AND the
  PROTECTED second-line defense (containment on identity-svc rejected even on a
  direct call). One-directional: no `EGRESS_BLOCKED→...` transitions defined.

**Policy** (`fleet/layers/incident.py`):
- `Severity` enum; `required_authorization(verification, severity, action,
  workload_id) → AUTO|HUMAN|BLOCKED` (pure, model-independent); `bind_artifact`
  content-addresses the exact transition (sha256 of canonical workload_id+action+
  target_state) and is fed into the existing D17 `Approval.sign`/`verify_approval`
  as `artifact_hash` (extend-not-redesign); `decision_summary` for UI display.

**Integration** (`fleet/layers/runtime.py`, `Operator.act`):
- Adds optional `target_workload`/`action_name`/`simenv` params (dormant for all
  existing callers — 125-test baseline unchanged). When present, the incident
  fork clears FOUR independent gates in order: (1) Evidence HALLUCINATION→block,
  (2) Capability via `request_authority`, (3) Policy `required_authorization`,
  (4) Approval (bound, only when policy==HUMAN). The deterministic SimEnv
  transition executes INSIDE the existing idempotent `_commit`, so a replay
  returns the recorded result instead of double-transitioning. `operator.final`
  audit event carries the real `prev_state→new_state`.

**Tests** (drive the REAL ControlPlane/Runtime/SimEnv):
- `test_simenv.py` (14): pure transitions, idempotency, identity-svc
  prohibition, blast-radius metadata.
- `test_incident_policy.py` (20): full D26 §8 matrix parametrized + property
  checks (hallucination-always-blocked, evidence≠authority, severity and
  confidence are separate axes, stable binding).
- `test_incident_e2e.py` (8): Path A (LOW AUTO), Path B (HIGH revenue-svc
  HUMAN + signed approval), Act 3 (VERIFIED-compromised identity-svc BLOCKED),
  Attack 1 (mis-bound human approval rejected), Attack 2 (capability denial),
  Attack 3 (HALLUCINATION intel blocked), Attack 4 (SimEnv second-line defense),
  idempotent replay.

**UI** (`demo_app.py`, `requirements-ui.txt`): Streamlit 8-panel window outside
the trust boundary. Drives the real stack; decides nothing. UI dependency kept
out of base + GCP audit surfaces (R3).

**Suite:** 205 tests pass (param-expanded; D26 adds 42: 14 SimEnv + 20 policy + 8 e2e on top of the baseline). `incident_remediate` added to the
operator role's granted capabilities in `fleet/layers/policy.py` (additive).
