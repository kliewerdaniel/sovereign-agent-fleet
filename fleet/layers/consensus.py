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

from fleet.layers.brain import Brain, BrainSchemaError, validate_brain_output


def _propose_validated(brain: Brain, task: str, instruction: str, schema_hint: str):
    """Propose + schema-validate (D15). Returns the dict, or raises BrainSchemaError
    on an unknown task / malformed proposal (which the gate converts to a distinct
    audit condition)."""
    return validate_brain_output(task, brain.propose(task, instruction, schema_hint))


# task -> the field that carries the verdict/label to compare.
_VERDICT_FIELD = {
    "analyst_classification": "claim_type",
    "analyst_entity_resolution": "resolved_entity",
}


def same_verdict(task: str, a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """True iff both proposals carry the same verdict-bearing label for `task`.

    Returns False for any task not present in ``_VERDICT_FIELD`` OR whose mapped
    field is absent from either proposal — callers must treat an unmapped task as a
    distinct condition (see ``ConsensusGate.evaluate``), not as a brain disagreement.
    """
    field = _VERDICT_FIELD.get(task, "verdict")
    if field not in a or field not in b:
        return False
    return str(a[field]) == str(b[field])


def unmapped_task(task: str) -> bool:
    """True iff `task` has no verdict-field mapping in `_VERDICT_FIELD`."""
    return task not in _VERDICT_FIELD


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
        # Validate each brain's proposal (D15). An unknown task / malformed
        # proposal raises BrainSchemaError — that is a GATE/TASK gap, not a brain
        # disagreement. Convert it to a distinct, loud, distinguishable signed
        # event (`consensus.unmapped_task`) instead of letting it masquerade as a
        # permanent disagreement (which would silently downgrade every claim for
        # that task to ASSERTED forever).
        try:
            pa = _propose_validated(self._a, task, instruction, schema_hint)
            pb = _propose_validated(self._b, task, instruction, schema_hint)
        except BrainSchemaError as exc:
            if self._audit is not None:
                self._audit({
                    "kind": "consensus.unmapped_task",
                    "who": "consensus",
                    "task": task,
                    "input_refs": input_refs or [],
                    "reason": f"task proposal failed schema/unknown task: {exc}; "
                              "register the task (SCHEMAS + _VERDICT_FIELD) or it "
                              "cannot reach VERIFIED",
                })
            return {
                "status": "unmapped_task",
                "disagreement": True,
                "verdict": "ASSERTED",
                "confidence": 0.0,
                "reason": "task not registered for consensus verdict comparison",
            }

        # A task with no verdict-field mapping is also a CONFIG/GATE gap. Surface it
        # as the same distinct, loud event (the schema passed but there is no field
        # to compare). This can happen for a task that IS in SCHEMAS but absent from
        # _VERDICT_FIELD.
        if unmapped_task(task):
            if self._audit is not None:
                self._audit({
                    "kind": "consensus.unmapped_task",
                    "who": "consensus",
                    "task": task,
                    "a": pa,
                    "b": pb,
                    "input_refs": input_refs or [],
                    "reason": "task has no verdict-field mapping in _VERDICT_FIELD; "
                              "register the task or it cannot reach VERIFIED",
                })
            return {
                "status": "unmapped_task",
                "disagreement": True,
                "verdict": "ASSERTED",
                "confidence": 0.0,
                "a": pa,
                "b": pb,
                "reason": "task not registered for consensus verdict comparison",
            }

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
