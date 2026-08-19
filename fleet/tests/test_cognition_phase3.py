"""D28 Phase 3 — EvaluationArtifact + deterministic escalation adapter.

Proves by construction:
  * EvaluationArtifact carries OBSERVED SIGNALS only: building one and
    validating rejects any governance-flag field (D-H correction #1:
    "signals, never flags").
  * ``escalate_to_asserted`` is a PURE FUNCTION of signals: it never imports a
    gate, never reads gateway/policy, and only ever RAISES scrutiny (D-B).
  * ``to_gateway_intent`` passes the governance surface through untouched and
    returns only a boolean escalation signal (the single seam).
  * ``ProposalArtifact.bind`` produces a signed enrichment block with a content
    hash for binding/integrity verification (D-D: verifier proves present,
    unaltered, signed -- never semantic correctness).
"""
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fleet.crypto.foundation import IdentityRoot
from fleet.crypto.chriscrypt.store import JsonStore
from fleet.layers import ControlPlane, HandoffError
from fleet.cognition.evaluation import (
    EvaluationArtifact,
    ProposalArtifact,
    escalate_to_asserted,
    to_gateway_intent,
    validate_evaluation_payload,
)


@pytest.fixture
def env(tmp_path):
    master = b"p3-cognition-master"
    audit = Ed25519PrivateKey.from_private_bytes(b"\x02" * 32)
    cp = ControlPlane(master, audit, store=JsonStore(str(tmp_path / "audit.json")),
                      now_fn=lambda: 1_000)
    eval_agent = cp.publish_agent("evaluator-1", "analyst", ["evaluate"])
    return {"cp": cp, "eval_agent": eval_agent}


def _artifact(**over):
    producer_cert_id = over.pop("producer_cert_id", "evaluator-1")
    uncertainty = over.pop("uncertainty", 0.1)
    popper = over.pop("popper", {"falsifiers": ["f1"], "passed": 1, "failed": 0})
    evidence_quality = over.pop("evidence_quality", {"authenticity": 0.9})
    needs_met = over.pop("needs_met",
                         {"intent": True, "constraints_satisfied": True, "gaps": []})
    persona_analyses = over.pop("persona_analyses",
                                [{"role": "skeptic", "stance": "doubt", "claim_refs": []}])
    contradiction_count = over.pop("contradiction_count", 0)
    return EvaluationArtifact(
        producer_cert_id=producer_cert_id,
        uncertainty=uncertainty,
        popper=popper,
        evidence_quality=evidence_quality,
        needs_met=needs_met,
        persona_analyses=persona_analyses,
        contradiction_count=contradiction_count,
    )


def test_signals_not_flags(env):
    # An evaluation payload that smuggles an instruction field is rejected.
    bad = _artifact().to_payload()
    bad["requires_human_review"] = True
    with pytest.raises(HandoffError):
        validate_evaluation_payload(bad)


def test_escalation_adapter_is_pure_and_raises_scrutiny_only(env):
    # clean -> no escalation
    assert escalate_to_asserted(_artifact()) is False
    # high uncertainty -> escalate (and only because a threshold crossed)
    assert escalate_to_asserted(_artifact(uncertainty=0.85)) is True
    # failed falsification -> escalate
    assert escalate_to_asserted(_artifact(popper={"falsifiers": ["x"], "passed": 0, "failed": 1})) is True
    # contradiction -> escalate
    assert escalate_to_asserted(_artifact(contradiction_count=2)) is True


def test_gateway_intent_passthrough(env):
    surface = {"intel_id": "iq_1"}  # opaque; cognition never types it
    intel, force = to_gateway_intent(surface, _artifact(uncertainty=0.9))
    assert intel is surface          # untouched passthrough
    assert force is True             # only a boolean signal escapes


def test_enrichment_signed_and_bound(env):
    art = _artifact()
    pa = ProposalArtifact(governance_surface={"intel_id": "iq_1"}, enrichment=art)
    block = pa.bind(env["eval_agent"].cert, env["eval_agent"].key)
    # signed + hashed for binding/integrity (D-D)
    assert block["enrichment_producer"] == "evaluator-1"
    assert block["enrichment_hash"] == art.enrichment_hash
    # verifier-side: signature verifies under the claimed producer cert
    assert art.verify_sig(block["enrichment_sig"], env["eval_agent"].cert) is True
    # tamper -> hash mismatch is detectable
    tampered = dict(block)
    tampered["enrichment_hash"] = "deadbeef"
    assert tampered["enrichment_hash"] != art.enrichment_hash


def test_evaluation_rejects_unknown_imports():
    # structural guarantee: evaluation.py must not import authority modules.
    import ast
    from pathlib import Path
    # Resolve the repo root from this file (works on any checkout path,
    # including CI runners whose working dir differs from the author's).
    here = Path(__file__).resolve()
    repo_root = here
    while repo_root.name != "sovereign-agent-fleet" and repo_root != repo_root.parent:
        repo_root = repo_root.parent
    eval_path = repo_root / "fleet" / "cognition" / "evaluation.py"
    assert eval_path.exists(), f"expected evaluation.py at {eval_path}"
    src = eval_path.read_text()
    tree = ast.parse(src)
    forbidden = ("fleet.layers.gateway", "fleet.layers.policy",
                 "fleet.layers.runtime", "fleet.fin", "fleet.simenv",
                 "fleet.gcp", "fleet.layers.incident")
    for node in ast.walk(tree):
        mod = None
        if isinstance(node, ast.Import):
            for a in node.names:
                mod = a.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
        if mod and any(mod.startswith(f) for f in forbidden):
            raise AssertionError(f"evaluation.py imports forbidden module: {mod}")
