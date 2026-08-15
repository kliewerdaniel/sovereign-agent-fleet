# 12. Data Model (field-level)

All records are content-addressed and signed. Types: `AgentCert`, `SourcedEvidence`, `QualifiedIntel`, `ApprovalRecord`, `AuditEntry`, `ToolEnvelope`.

## 12.1 AgentCert (root-signed identity)
```
AgentCert {
  agent_id:       str
  pubkey:         Ed25519_pub            # agent identity public key
  role:           "researcher"|"analyst"|"operator"|"human"|"tool"
  capabilities:   [Capability]           # e.g. "emit_evidence","qualify","crm_write","approve_deny"
  issued_at:      int (unix)
  expires_at:     int (unix)
  cert_seq:       int                    # increments on rotation
  root_sig:       Ed25519_sig(root)       # over canonical(bytes except root_sig)
}
```
- Gateway validates `root_sig` + unrevoked + `capabilities ⊇ requested action`.

## 12.2 SourcedEvidence (Researcher output)
```
SourcedEvidence {
  evidence_id:    str                    # e.g. "ev_/uuid"
  agent_id:       str                    # researcher
  citation:       str                    # source locator (url/doc id)
  extract:        str                    # structured extracted text (schema-validated)
  source_hash:    SHA256                 # hash of retrieved source at retrieval time
  retrieval_prov: { tool, ts, query }    # provenance
  collected_at:   int
  body:           bytes?                 # optional encrypted payload (XChaCha20)
  agent_sig:      Ed25519_sig(agent)     # over canonical(...)
}
```
- Researcher is **forbidden** from emitting `classification`/`confidence` fields here (capability separation, D8).

## 12.3 QualifiedIntel (Analyst output)
```
QualifiedIntel {
  intel_id:       str
  agent_id:       str                    # analyst
  target_id:      str                    # prospect/entity
  predicates: [{
      claim:      str                    # e.g. "icp_fit=true"
      claim_type: "icp_fit"|"role"|"budget_auth"|...
      evidence_refs: [evidence_id]       # MUST cite ≥1 valid SourcedEvidence
  }]
  confidence:     float [0,1]            # distinct_supporting_refs / required_weight[claim_type]
  verification:    "VERIFIED"|"ASSERTED"|"HALLUCINATION"
      # VERIFIED: every predicate has valid refs AND confidence>=threshold(0.6)
      # ASSERTED: refs present but confidence<threshold -> requires approval
      # HALLUCINATION: a predicate has zero valid evidence_ref -> flagged, not consumed
  staleness_ok:    bool                   # all refs within 30d window
  agent_sig:      Ed25519_sig(analyst)
}
```
- Verification gate = D16. Operator may only consume `VERIFIED` (auto low-risk) or `ASSERTED` post-approval. `HALLUCINATION` blocked at boundary.

## 12.4 ApprovalRecord (human decision, D17)
```
ApprovalRecord {
  approval_id:    str
  agent_id:       str                    # agent requesting action
  action_id:      str                    # the consequential action (e.g. crm_write)
  artifact_hash:  SHA256                 # hash of the artifact to be executed
  decision:       "approve"|"deny"
  reason:         str
  human_id:       str                    # human approver agent_id
  human_sig:      Ed25519_sig(human)     # human key device-bound, local (D17)
  ts:             int
}
```

## 12.5 AuditEntry (hash-chain, tamper-evident)
```
AuditEntry {
  seq:            int
  prev_hash:      SHA256                 # = SHA256(prev AuditEntry), genesis=root_anchor
  event: {
    who:          agent_id
    what:         action/state_transition
    when:         int
    why:          policy_id + capability
    tool:         tool_id?
    evidence_refs:[evidence_id]?
    result:       "ok"|"denied"|"blocked"|"approved"|"tamper_detected"|...
    verified:     verification_method
    approved_by:  human_id?
  }
  body_hash:      SHA256                 # hash of event payload
  sig:            Ed25519_sig(actor)     # agent or human
}
```
- Tamper = `SHA256(entry) != next.prev_hash` → chain walk fails at that seq (adversarial beat 6).

## 12.6 ToolEnvelope (Model Armor, D12)
```
ToolEnvelope {
  tool_id:        str
  output_hash:    SHA256
  output:         bytes                  # schema-validated structured result
  tool_sig:       Ed25519_sig(tool)      # over (tool_id, output_hash)
}
```
- Runtime verifies `tool_sig` before model sees `output`. Forged/failed → blocked (failure #7).

## 12.7 Canonical serialization rule
All signing hashes computed over a deterministic canonical byte encoding (sorted keys / fixed field order, no whitespace). Defined once; reused by every signer + verifier.
