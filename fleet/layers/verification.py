"""Analyst verification gate (D16 / 12.3 / 14.4).

Deterministic boundary: an Analyst's QualifiedIntel is only as trustworthy as
the evidence it actually cites. The gate maps a structured intel object to one
of three verdicts:

  * VERIFIED      every predicate cites >=1 valid SourcedEvidence AND the
                  weakest claim's confidence >= 0.6  -> auto-allow (low-risk)
  * ASSERTED      refs present but weakest confidence < 0.6 -> human approval
  * HALLUCINATION a predicate cites ZERO valid evidence -> flagged, NEVER
                  consumed by the Operator (content-correctness, distinct from
                  signature integrity)

This is NOT a confidence free-for-all: the confidence number is derived
deterministically from counted, resolved evidence refs (D16), so the protocol
can enforce it at the Operator boundary rather than trusting the model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

# Required supporting-evidence weight per claim type (D16 ADR).
REQUIRED_WEIGHT: Dict[str, int] = {
    "icp_fit": 2,       # need >=2 distinct sources to call a fit
    "role": 1,          # one source suffices for a role assertion
    "budget_auth": 2,   # need >=2 distinct sources for budget authority
}
DEFAULT_WEIGHT = 1

STALENESS_WINDOW_DAYS = 30
STALE_DISCOUNT = 0.5
VERIFIED_THRESHOLD = 0.6

VERIFIED = "VERIFIED"
ASSERTED = "ASSERTED"
HALLUCINATION = "HALLUCINATION"


@dataclass
class VerificationResult:
    verification: str
    confidence: float          # overall (conservative: min over predicates)
    staleness_ok: bool
    per_claim: List[dict]
    reason: str


def _claim_confidence(n_distinct_refs: int, claim_type: str, stale: bool) -> float:
    weight = REQUIRED_WEIGHT.get(claim_type, DEFAULT_WEIGHT)
    if not weight:
        return 0.0
    conf = min(1.0, n_distinct_refs / weight)
    if stale:
        conf *= STALE_DISCOUNT
    return round(conf, 6)


def evaluate_intel(
    intel: Dict[str, Any],
    evidence_meta: Dict[str, Dict[str, Any]],
    now: int,
) -> VerificationResult:
    """Evaluate a QualifiedIntel against known/valid evidence metadata.

    `evidence_meta`: evidence_id -> {"collected_at": <unix seconds>}.
    Returns the deterministic verification verdict.
    """
    known = set(evidence_meta)
    per_claim: List[dict] = []
    has_hallucination = False
    confidence_floor = 1.0  # conservative: weakest predicate governs trust

    for pred in intel.get("predicates", []) or []:
        claim_type = pred.get("claim_type", "")
        refs = [r for r in (pred.get("evidence_refs") or []) if r in known]
        n_distinct = len(set(refs))
        stale = any(
            (now - int(evidence_meta[r].get("collected_at", 0)))
            > STALENESS_WINDOW_DAYS * 86400
            for r in refs
        )
        conf = _claim_confidence(n_distinct, claim_type, stale)
        if n_distinct == 0:
            has_hallucination = True
            per_claim.append({
                "claim_type": claim_type,
                "valid_refs": refs,
                "confidence": 0.0,
                "hallucination": True,
                "stale": stale,
            })
        else:
            confidence_floor = min(confidence_floor, conf)
            per_claim.append({
                "claim_type": claim_type,
                "valid_refs": refs,
                "confidence": conf,
                "hallucination": False,
                "stale": stale,
            })

    staleness_ok = all(not c["stale"] for c in per_claim)

    if has_hallucination:
        return VerificationResult(
            HALLUCINATION, 0.0, staleness_ok, per_claim,
            "a predicate cites zero valid evidence refs",
        )
    if not per_claim:
        return VerificationResult(
            HALLUCINATION, 0.0, staleness_ok, per_claim, "intel carries no predicates"
        )
    if confidence_floor >= VERIFIED_THRESHOLD:
        return VerificationResult(
            VERIFIED, confidence_floor, staleness_ok, per_claim,
            "all predicates supported; weakest confidence >= 0.6",
        )
    return VerificationResult(
        ASSERTED, confidence_floor, staleness_ok, per_claim,
        "weakest claim confidence < 0.6; requires human approval",
    )


def stamp(intel: Dict[str, Any], evidence_meta, now: int) -> Dict[str, Any]:
    """Compute and attach the verification fields to a QualifiedIntel dict."""
    res = evaluate_intel(intel, evidence_meta, now)
    out = dict(intel)
    out["confidence"] = res.confidence
    out["verification"] = res.verification
    out["staleness_ok"] = res.staleness_ok
    return out
