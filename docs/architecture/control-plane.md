# The Control Plane — Layers, Components, Trust Model

## The three-layer trust model

Each layer trusts only the interface immediately below it. This is the central conceptual
architecture (from `research/D27`);

```text
┌─────────────────────────────┐
│  LAYER 1 — INTELLIGENCE     │  observe, reason, propose, disagree, err.
│  (may be wrong / compromised)│  NO authority.
└──────────────┬──────────────┘
               │ proposal (schema-validated, evidence-grounded)
               ▼
┌─────────────────────────────┐
│  LAYER 2 — DETERMINISTIC    │  identity, capability, policy, risk,
│       GOVERNANCE            │  approval requirement, cryptographic binding.
│  (model-agnostic; never     │  NO reasoning, NO execution.
│   reasons about the model)  │
└──────────────┬──────────────┘
               │ signed, state-bound authorization
               ▼
┌─────────────────────────────┐
│  LAYER 3 — CONSEQUENTIAL    │  verifies authorization, verifies state,
│     ENVIRONMENT (paper)     │  performs transition, issues receipt.
│  (does NOT trust the model) │
└──────────────┬──────────────┘
               │ ExecutionReceipt
               ▼
        INDEPENDENT VERIFIER (public keys only)
```

| Layer | Trusts | Does NOT trust | Responsibility |
|-------|--------|---------------|----------------|
| 1 Intelligence | its own inputs (evidence) | the environment; the ledger | observe, reason, propose, err, be compromised |
| 2 Governance | identity registry + its own pure policy/risk functions | the model's reasoning or "confidence" | authenticate, authorize, bind cryptographically |
| 3 Environment | the signed authorization + current state | the model | validate, transition, receipt |

## Components (implemented in `fleet/`)

| Component | Module | Role |
|-----------|--------|------|
| Root of trust | `fleet/crypto/foundation.py` | Argon2id master → root Ed25519; per-agent certs; signed hash-chain `AuditTrail` |
| Ledger crypto | `fleet/crypto/chriscrypt/` (vendored, MIT) | XChaCha20-Poly1305 envelopes, HKDF per-record, Ed25519 hash-chain |
| Registry | `fleet/layers/registry.py` | publish / version / discover / revoke / rotate |
| Policy engine | `fleet/layers/policy.py` | `(role, capability) → GRANT / REQUIRE_APPROVAL / DENY` — pure, never calls the model |
| Capability gateway | `fleet/layers/gateway.py` | `request_authority`, cert auth, signed deny events, idempotency |
| Evidence gate | `fleet/layers/verification.py` | `VERIFIED / ASSERTED / HALLUCINATION` |
| Human approval | `fleet/layers/approval.py` (+ `D17`) | Ed25519-bound `ApprovalRecord`; fail-closed rebinding |
| Consensus | `fleet/layers/consensus.py` | two distinct brains must agree to VERIFY; advisory only, escalation-only |
| Incident matrix | `fleet/layers/incident.py` | `verification × severity × blast × asset → AUTO/HUMAN/BLOCKED` |
| Cognition | `fleet/cognition/` | D28 layered reasoning — see [`../cognition/`](../cognition/); import-walled |
| Runtime | `fleet/layers/runtime.py` | workers (Researcher/Analyst/Operator), 4-gate fork, idempotency |
| GCP mirror | `fleet/gcp/` | Firestore/Pub-Sub mirror + Cloud Run approval console — **local by default**, verify-only |

## The six-stage security framing

```
Model:              "What should we do?"            (untrusted, proposal-only)
Evidence system:    "What do we know, and can the proposal be grounded?"
Policy/risk engine: "What authority does this action require?"
Operator:          "Can I construct a valid authorization?"
Environment:        "Is this authorization valid for the state that exists right now?"
Verifier:           "Can I independently prove what happened?"
```

## Import-wall guarantees (structural, not aspirational)

- `fleet/cognition/**` must not import `gateway`, `policy`, `runtime.act_trade`, `fin.domain.assess`, `incident.required_authorization`, or `verify`. (`fleet/tests/test_boundary.py`.)
- `exchange/quant/**` must not import `exchange.governance`, `fleet/fin`, or `fleet.cognition`. (`exchange/tests/test_boundary_quant.py`.)

These make "the model cannot authorize" a build failure, not a code-review hope.
