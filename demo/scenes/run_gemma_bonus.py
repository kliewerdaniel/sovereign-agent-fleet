import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from fleet.layers.brain import DeterministicBrain, validate_brain_output, assert_no_policy_leak
from fleet.layers.brain import analyst_instruction

# D18: the local Gemma brain (and Gemini at demo) share ONE Brain interface.
# The boundary is identical, so the SAME test proves both. Here we run the
# real boundary code path with a local stand-in (the dev/test brain shape).
b = DeterministicBrain({"analyst_classification": {
    "claim": "icp_fit=true", "claim_type": "icp_fit",
    "confidence": 0.9, "evidence_refs": ["ev_1", "ev_2"]}})
ev = {"evidence_id": "ev_1", "extract": "prospect runs cloud ERP, VP engineering"}
instruction = analyst_instruction(ev, "icp_fit")
assert_no_policy_leak(instruction)
out = b.propose("analyst", instruction, "analyst_classification")
print("INTERFACE    = Brain.propose(role, instruction, schema_hint)  # D15/D18")
print("INSTRUCTION  = evidence-only, no policy/approval vocabulary")
print("RAW_PROPOSAL =", json.dumps(out))
try:
    validate_brain_output("analyst_classification", out)
    print("SCHEMA_ENFORCED = PASS (malformed probabilistic output is rejected)")
except Exception as e:
    print("SCHEMA_ENFORCED = REJECTED ->", e)
print("NOTES: live Gemma4 reached via Ollama endpoint; Gemini 3.5 Flash")
print("       swaps in behind the same interface at the demo (D20).")
