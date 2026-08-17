# Governance — identity, policy, capability, approval, consensus

Governance is the deterministic core of the control plane. It never calls the model; it is a
set of pure functions over authenticated inputs. This is where authority is decided.

## The decision vocabulary

Both financial workloads and the incident workload reduce to the same verdict shape:

```
AUTO     → execute immediately
HUMAN    → require a cryptographically-bound human ApprovalRecord (D17)
BLOCKED  → fail-closed (no execution)
```

## Components

| Concern | Module | Notes |
|---------|--------|-------|
| Identity / root of trust | `fleet/crypto/foundation.py` | Argon2id master → root Ed25519; per-agent `AgentCert` signed by root. |
| Registry | `fleet/layers/registry.py` | publish / version / discover / revoke / rotate. Revoked cert → discovery returns None. |
| Capability gateway | `fleet/layers/gateway.py` | `request_authority`; root-signed cert auth; signed deny events; idempotency. |
| Policy engine | `fleet/layers/policy.py` | `(role, capability) → GRANT / REQUIRE_APPROVAL / DENY`. Default-deny property. |
| Evidence gate | `fleet/layers/verification.py` | `VERIFIED / ASSERTED / HALLUCINATION`. |
| Human approval | `fleet/layers/approval.py` (D17) | Ed25519-bound `ApprovalRecord`; rebound/reuse rejected fail-closed. |
| Consensus | `fleet/layers/consensus.py` (D23) | two distinct brains must agree to VERIFY; advisory only, escalation-only. |
| Incident matrix | `fleet/layers/incident.py` (D26) | `verification × severity × blast × asset → AUTO/HUMAN/BLOCKED`. |
| Financial risk | `fleet/fin/domain.py` + `exchange/governance.py` | `RiskLayer.assess` / `decide_trade` → AUTO/HUMAN/BLOCKED. |
| Runtime | `fleet/layers/runtime.py` | Researcher→Analyst→Operator; 4-gate fork; idempotent commit. |

## Uniform fail-closed taxonomy

Missing, malformed, expired, unverifiable, or contradictory security input → a **non-executing**
result. No gate reads absence as permission.

| Gate | On missing / invalid / contradictory input |
|------|--------------------------------------------|
| Evidence (D16) | HALLUCINATION → BLOCKED |
| Gateway (capability) | unknown role/cap → DENY; revoked/expired cert → DENY |
| Risk | no portfolio/market → BLOCKED; breach → BLOCKED/HUMAN |
| Approval (human) | no record → DENY (if HUMAN tier); bad sig/rebound → DENY |
| Environment | no authorization / no account → REFUSE; sig fail / state mismatch / limit breach → REFUSE |

## Key documents

- [`research/04-security-model.md`](../research/04-security-model.md)
- [`research/D26-incident-triage-usecase.md`](../research/D26-incident-triage-usecase.md)
- [`research/D27-financial-workload-architecture-lock.md`](../research/D27-financial-workload-architecture-lock.md) (10 risk dimensions, I1–I17 invariants)
- [`../security/`](../security/)
