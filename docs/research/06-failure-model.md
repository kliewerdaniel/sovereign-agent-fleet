# 6. Failure Model

Every failure mode maps to exactly one owning layer. (Q1 accepted as assigned.)

| # | Failure mode | Owning layer | Behavior |
|---|--------------|--------------|----------|
| 1 | Model hallucination | **Verification** | Unsupported-claim detection: asserted claim must resolve to cited `SourcedEvidence`; unresolved claim flagged, not recorded as verified |
| 2 | Tool failure | **Runtime** | Retry w/ backoff + timeout; failure recorded as evidence; action stays in OBSERVATION, not EVIDENCE |
| 3 | Network failure | **Pub/Sub** | Redelivery + idempotency keys; in-flight handoff retried, not duplicated |
| 4 | Stale evidence | **Analyst** | Provenance timestamps; staleness flag; confidence discounted for stale refs |
| 5 | Conflicting evidence | **Analyst** | Confidence lowered; conflict recorded; human/approval escalated if high-stakes |
| 6 | Unauthorized action | **Gateway** | Capability-based deny; signed deny event; no execution |
| 7 | Malicious tool result | **Model Armor** | Signed-envelope check fails → result blocked before model sees it; failure logged |
| 8 | Compromised worker | **Root** | Revoke + live rotate (D14); old entries legacied; new key resumes |
| 9 | Invalid signatures | **Verification** | Reject + alert; entry not chained; Gateway blocks agent |
| 10 | Corrupted state | **Hash-chain + backup** | Chain walk detects break; restore from encrypted backup; verify on reload |
| 11 | Interrupted execution | **Runtime** | Checkpointed lifecycle; resume from last state; no partial FINAL |
| 12 | Duplicate actions | **Operator idempotency** | Idempotency keys on consequential writes; replay ignored |
| 13 | Partial completion | **Lifecycle** | FINAL only after APPROVAL; incomplete → stays in state machine, audit shows gap |

## Notes
- **Content correctness (1,4,5,9-content) ≠ integrity (3,7,10).** Two independent mechanisms; never collapse them.
- **Interrupted + partial** are handled by the same state machine: a checkpoint + the rule "FINAL requires APPROVAL" means a crash mid-flight leaves a resumable, auditable gap rather than a silent half-write.
