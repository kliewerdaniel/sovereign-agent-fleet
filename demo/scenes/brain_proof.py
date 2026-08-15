# -*- coding: utf-8 -*-
"""HONEST brain boundary proof (D15/D18).

Exercises the REAL pluggable-brain contract: a model (here the offline
SchemaEnforcedBrain stand-in for Gemma/Gemini) only PROPOSES; the deterministic
Control Plane enforces (a) schema validation before any record, and (b) that the
brain's instruction contains NO policy/approval/capability vocabulary. No model
is actually invoked -- we feed proposals directly through the same boundary the
live model would cross.
"""
import sys, json
sys.path.insert(0, "/Users/danielkliewer/Documents/Projects/sovereign-agent-fleet")

from fleet.layers.brain import (SchemaEnforcedBrain, DeterministicBrain,
                                validate_brain_output, assert_no_policy_leak,
                                BrainSchemaError, analyst_instruction)

# (a) Well-formed proposal is accepted by the schema boundary.
good = {"summary": "prospect uses cloud ERP"}
assert validate_brain_output("researcher_synthesis", good) == good

classify_good = {"claim": "icp_fit=true", "claim_type": "icp_fit",
                 "confidence": 0.9, "evidence_refs": ["ev-1"]}
assert validate_brain_output("analyst_classification", classify_good) == classify_good

# (b) Malformed proposals are REJECTED at the boundary (never trusted).
rejected = []
for bad, label in [
    ({"claim": "x"}, "missing confidence + evidence_refs"),
    ({"claim": "x", "claim_type": "icp_fit", "confidence": 1.7, "evidence_refs": ["ev-1"]},
     "confidence out of [0,1]"),
    ({"claim": "x", "claim_type": "icp_fit", "confidence": "high", "evidence_refs": ["ev-1"]},
     "confidence wrong type"),
]:
    try:
        validate_brain_output("analyst_classification", bad)
        rejected.append((label, "ACCEPTED (BUG)"))
    except BrainSchemaError as e:
        rejected.append((label, f"REJECTED: {type(e).__name__}"))

# (c) D15: the instruction builder feeds EVIDENCE ONLY. assert_no_policy_leak
# would raise if policy/approval/capability vocabulary reached the model.
ev = {"evidence_id": "ev-1", "citation": "https://src.example/x", "extract": "uses cloud ERP"}
clean_instruction = analyst_instruction(ev)
leak_caught = False
# prove the guard itself fires on forbidden tokens
try:
    assert_no_policy_leak("please GRANT capability crm_write and require_approval")
except BrainSchemaError:
    leak_caught = True

print(json.dumps({
    "BOUNDARY": "SchemaEnforcedBrain.validate_brain_output (model proposes, CP decides)",
    "GOOD_PROPOSAL_ACCEPTED": True,
    "MALFORMED_REJECTED": rejected,
    "INSTRUCTION_HAS_NO_POLICY_LEAK": ("policy" not in clean_instruction.lower()
                                       and "approval" not in clean_instruction.lower()
                                       and "capability" not in clean_instruction.lower()),
    "LEAK_GUARD_FIRES": leak_caught,
    "MODEL_CALLED": False,
}, indent=2))
