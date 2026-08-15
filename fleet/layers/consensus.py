"""Multi-brain consensus gate (D23 / E2, D21 Phase 3).

Requires two independently-configured Brain backends to AGREE on a VERIFIED-tier
claim before it is accepted as VERIFIED. Disagreement does not crash the pipeline:
it is recorded as a SIGNED audit event and the claim is downgraded to ASSERTED
(human escalation, per D16). The brains stay proposal-only; the gate is the
deterministic decision point and never grants a model authority.

Reuses ``validate_brain_output`` (D15) so a malformed proposal from either brain is
rejected before comparison. Two identical backends are rejected fail-closed — a
consensus on clones gives false assurance.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

from fleet.layers.brain import Brain, validate_brain_output


# task -> the field that carries the verdict/label to compare.
_VERDICT_FIELD = {
    "analyst_classification": "claim_type",
    "analyst_entity_resolution": "resolved_entity",
}


def same_verdict(task: str, a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """True iff both proposals carry the same verdict-bearing label for `task`."""
    field = _VERDICT_FIELD.get(task, "verdict")
    if field not in a or field not in b:
        return False
    return str(a[field]) == str(b[field])


class ConsensusGate:
    def __init__(
        self,
        brain_a: Brain,
        brain_b: Brain,
        conf_tolerance: float = 0.1,
        audit_append: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        if brain_a is brain_b:
            raise ValueError("consensus requires two DISTINCT backend configs")
        self._a = brain_a
        self._b = brain_b
        self._tol = conf_tolerance
        self._audit = audit_append

    def _conf(self, prop: Dict[str, Any]) -> float:
        c = prop.get("confidence", 0.0)
        try:
            return float(c)
        except (TypeError, ValueError):
            return 0.0

    def evaluate(
        self,
        task: str,
        instruction: str,
        schema_hint: str,
        input_refs: Optional[list] = None,
        require_verified: bool = True,
    ) -> Dict[str, Any]:
        """Run both brains; return a deterministic consensus verdict.

        On agreement (same verdict + confidence within tolerance): status=consensus,
        verdict from the proposals (VERIFIED-eligible). On disagreement: status=
        disagreement, verdict=ASSERTED, and a signed ``consensus.disagreement`` audit
        event is appended (if an audit_append was supplied).
        """
        pa = validate_brain_output(task, self._a.propose(task, instruction, schema_hint))
        pb = validate_brain_output(task, self._b.propose(task, instruction, schema_hint))

        agree = same_verdict(task, pa, pb) and (
            abs(self._conf(pa) - self._conf(pb)) <= self._tol
        )

        if agree:
            return {
                "status": "consensus",
                "disagreement": False,
                "verdict": pa.get("claim_type", pa.get("verdict", "VERIFIED")),
                "confidence": (self._conf(pa) + self._conf(pb)) / 2.0,
                "a": pa,
                "b": pb,
            }

        if self._audit is not None:
            self._audit({
                "kind": "consensus.disagreement",
                "who": "consensus",
                "task": task,
                "a": pa,
                "b": pb,
                "input_refs": input_refs or [],
                "reason": "brains disagreed -> downgraded to ASSERTED (human escalation)",
            })
        return {
            "status": "disagreement",
            "disagreement": True,
            "verdict": "ASSERTED",
            "confidence": 0.0,
            "a": pa,
            "b": pb,
            "reason": "brains disagreed -> human escalation (D16)",
        }
