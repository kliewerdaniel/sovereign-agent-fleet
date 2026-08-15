# D23 — Multi-Brain Consensus Gate (Extension E2, D21 Phase 3)

## Thesis fit
> "Do not trust the model. Trust the execution protocol."

A single probabilistic brain can be confidently wrong. E2 requires **two
independently-configured Brain backends to agree** on a VERIFIED-tier claim before
the verification gate (D16) accepts it as VERIFIED. Disagreement does not crash the
pipeline — it is itself a **signed audit event**, and the claim is downgraded to
ASSERTED (human escalation), exactly as D16 prescribes.

The model stays **proposal-only**. The `ConsensusGate` is deterministic: it compares
two structured proposals and applies the policy. No Brain ever grants authority,
signs, approves, or writes the ledger.

## Construction
```
ConsensusGate(brain_a, brain_b, conf_tolerance=0.1)

evaluate(task, instruction, schema_hint, input_refs) -> dict:
    pa = validate_brain_output(task, brain_a.propose(task, instruction, schema_hint))
    pb = validate_brain_output(task, brain_b.propose(task, instruction, schema_hint))
    # compare the verdict-bearing fields
    agree = same_verdict(pa, pb) and |pa.confidence - pb.confidence| <= conf_tolerance
    if agree:
        return {status: "consensus", verdict: pa.verdict, confidence: mean(pa,pb),
                disagreement: False}
    else:
        log_audit("consensus.disagreement", who="consensus",
                  a=..., b=..., input_refs=input_refs)   # SIGNED, verifiable
        return {status: "disagreement", verdict: "ASSERTED", confidence: 0.0,
                disagreement: True, reason: "brains disagreed -> human escalation"}
```

`same_verdict` compares the task-specific verdict field:
  * `analyst_classification` → `claim_type`
  * `analyst_entity_resolution` → `resolved_entity`
  * generic → `verdict` if present.

The `ConsensusGate` **reuses** `validate_brain_output` (D15 schema enforcement) so a
malformed proposal from either brain is rejected before comparison — no schema
escape. Two different `DeterministicBrain` verdict tables (or, in production, two
local models with different seeds/temperature) make the disagreement path
exercisable offline.

## Trust boundary (unchanged)
- Both brains: probabilistic, proposal-only (D15/D18).
- `ConsensusGate`: deterministic Control Plane component.
- On disagreement: never auto-VERIFY; downgrade to ASSERTED + signed event.

## Files
- `fleet/layers/consensus.py` — `ConsensusGate`, `same_verdict`.
- `fleet/tests/test_consensus_phase3.py` — agree → VERIFIED; disagree → ASSERTED +
  signed `consensus.disagreement` event; malformed proposal rejected; tolerance
  respected.

## Rejected alternative
Routing the SAME brain instance twice would silently double-count as "two" backends
and give false assurance — the gate rejects `brain_a is brain_b` fail-closed. Two
distinct instances with identical *config* cannot be detected by the gate (it cannot
infer a backend's weights/seed), so the caller is responsible for wiring two genuinely
independent backends. The gate enforces the structural invariant; backend independence
is a deployment contract, documented here rather than faked.
