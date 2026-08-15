"""Standalone incident verifier (D26 §verification) — first-class artifact.

An independent verifier reconstructs an incident remediation's canonical inputs
from the audit ledger, recomputes the policy decision with the SAME pure
``fleet.layers.incident.required_authorization`` the Operator used, and confirms
the recorded authorization is reproducible. It also runs the D28 M0 proof:
any cognition enrichment attached to the record is verified for binding +
integrity only (D-D) and proven to leave the verdict unchanged (Run A = Run B).

The verifier holds only PUBLIC keys — no authority to execute, sign, or mutate.

This is the WORKLOAD-AGNOSTIC half of the M0 proof: the financial verifier
(``fleet.fin.verify``) covers the trade workload; this covers the incident
remediation workload. Together they prove M0 holds regardless of which
workload reached the boundary (ratified refinement #3).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fleet.crypto.foundation import AgentCert
from fleet.layers.incident import Authorization, Severity, required_authorization
from fleet.cognition.evaluation import verify_enrichment_block


VERIFY_KIND = "operator.final"          # the incident execution record


@dataclass
class IncidentVerifyResult:
    record_id: str
    status: str                 # "PASS" | "FAIL"
    reason: str
    critical: bool = False
    m0_ok: bool = True          # D28 M0: cognition did not change the verdict


def verify_record(rec: Dict[str, Any], operator_cert: AgentCert,
                  now: int = 0, registry=None) -> IncidentVerifyResult:
    """Recompute + cross-check a single incident execution record."""
    try:
        verification = rec.get("verification")
        if verification is None:
            findings_early = ["verification-missing"]
        else:
            findings_early = []
        verification = verification or "HALLUCINATION"
        severity = rec.get("severity") or "LOW"
        action = rec.get("action")
        target = rec.get("target")
        if action is None or target is None:
            return IncidentVerifyResult(rec.get("who", "?"), "FAIL",
                                        "missing-action-or-target")
        recorded = rec.get("authorization")

        # 1. Policy recomputation (pure fn; model-independent).
        recomputed = required_authorization(
            verification, Severity(severity), action, target
        ).value
        findings = list(findings_early)
        if recomputed != recorded:
            findings.append(f"authorization-mismatch({recomputed}!={recorded})")

        # 2. D28 M0 proof over the incident gate.
        m0_ok = True
        enrichment_block = rec.get("enrichment")
        if enrichment_block is not None:
            producer_id = enrichment_block.get("enrichment_producer")
            producer_cert = (registry.discover(producer_id)
                            if (registry is not None and producer_id is not None)
                            else None)
            if producer_cert is None:
                findings.append("enrichment-producer-unresolved")
            else:
                try:
                    verify_enrichment_block(enrichment_block, producer_cert)
                except Exception as e:
                    findings.append(f"enrichment-integrity-fail: {e}")
            # The gate receives ONLY (verification, severity, action, target).
            # Cognition enrichment is never an argument (D-A). Run A == Run B.
            from fleet.cognition.evaluation import enrichment_m0_invariant
            gate_inputs = (verification, Severity(severity), action, target)
            def _inc_gate(gi):
                return required_authorization(gi[0], gi[1], gi[2], gi[3]).value
            try:
                proven = enrichment_m0_invariant(gate_inputs, _inc_gate,
                                                 enrichment=None)
                if proven != recorded:
                    m0_ok = False
                    findings.append("m0-verdict-mismatch")
            except AssertionError:
                m0_ok = False
                findings.append("m0-violation")

        if findings:
            return IncidentVerifyResult(rec.get("who", "?"), "FAIL",
                                       "; ".join(findings), m0_ok=m0_ok)
        return IncidentVerifyResult(rec.get("who", "?"), "PASS", "reproduced",
                                    m0_ok=m0_ok)
    except Exception as e:
        return IncidentVerifyResult(rec.get("who", "?"), "FAIL",
                                    f"record-unparseable: {e}", critical=True)


def verify_control_plane(cp, operator_cert: AgentCert,
                         now: int = 0) -> Dict[str, Any]:
    """Verify every incident execution record in the live ControlPlane ledger."""
    entries = [e.get("payload", e) for e in cp.audit.entries()
               if e.get("kind") == VERIFY_KIND and e.get("target") is not None]
    results = [verify_record(e, operator_cert, now, registry=cp.registry)
               for e in entries]

    n_pass = sum(1 for r in results if r.status == "PASS")
    n_crit = sum(1 for r in results if r.critical)
    n_m0 = sum(1 for r in results if not r.m0_ok)
    n_recompute_fail = sum(
        1 for r in results
        if r.status == "FAIL" and ("mismatch" in r.reason
                                   or "unparseable" in r.reason)
    )
    pam = len(results)
    if n_crit > 0 or n_recompute_fail > 0 or n_m0 > 0:
        overall = "CRITICAL"
    elif pam and n_pass == pam:
        overall = "PASS"
    elif pam:
        overall = "FAIL"
    else:
        overall = "PASS"

    return {
        "overall": overall,
        "total": pam,
        "passed": n_pass,
        "failed": pam - n_pass,
        "critical": n_crit,
        "m0_violations": n_m0,
        "results": [r.__dict__ for r in results],
    }
