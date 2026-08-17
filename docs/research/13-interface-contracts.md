# 13. Interface Contracts

Interfaces are explicit because the fleet is multi-process and the audit story depends on them. Three contract families.

## 13.1 Agent → Gateway (authority request)
```
request_authority(agent_id, capability, action_spec) -> {
  granted: bool,
  policy_id: str,
  deny_reason: str?,
  require_approval: bool,
  signed_deny_event?: AuditEntry
}
```
- Gateway is the ONLY issuer of authority. Evaluates `AgentCert.capabilities` + policy. Never calls Gemini.

## 13.2 Agent → Agent (handoff, signed envelopes)
```
Researcher.publish(SourcedEvidence) -> evidence_id        # Gateway records, signs
Analyst.consume([evidence_id]) -> QualifiedIntel          # schema-enforced; cites refs
Operator.consume(QualifiedIntel) -> Artifact + request_authority(crm_write)
```
- Cross-agent messages carry `sender_sig` (Ed25519). Receiver verifies identity cert before trusting content (Model Armor injection defense). A message with invalid/unsigned sender is dropped.

## 13.3 Control Plane → GCP (replication, verifiable only)
```
replicate(entry: AuditEntry | AgentCert | ApprovalRecord) -> Firestore doc { id, payload, sig, prev_hash }
publish_task(handoff) -> Pub/Sub topic                      # R→A→O async
serve_console() -> Cloud Run HTTPS                         # approval UI (D17)
```
- Only signed/verifiable artifacts leave local runtime. No private key, no plaintext secret crosses the boundary (D3/D6).

## 13.4 Gemini (brain only, D15)
```
gemini.complete(prompt, schema) -> structured_text
```
- Called **only** inside R (synthesis), A (classification/confidence), O (draft outreach). Wrapped so output is schema-validated before becoming any record. Never receives policy/approval context as decision input.

## 13.5 Gemma (local bonus, D2)
```
gemma.local(prompt) -> entity_resolution_draft   # Analyst sub-task, local process
```
- Used for one Analyst sub-task (entity resolution draft) to earn Gemma bonus. Output still passes D16 verification gate.

## 13.6 Google agent framework — RESOLVED (D20)
- Framework requirement satisfied via the **GenAI SDK** (Gemini API called directly). Sovereign Worker is the orchestration + enforcement layer; it calls Gemini directly for the probabilistic brain (D15). ADK is not required.
- Dev uses local abliterated Gemma4 behind the same brain interface; swap to Gemini 3.5 Flash for the submission demo (D18). Brain is a pluggable interface; model choice is config, not code.

## 13.7 Idempotency
- Every consequential `action_id` carries an idempotency key; Gateway dedupes replays (failure #12).
