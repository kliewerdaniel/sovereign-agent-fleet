"""D28 Phase 2 — CompiledKnowledge producer + envelope validation.

Proves by construction:
  * SKC deterministically compiles verified SourcedEvidence into a signed
    CompiledKnowledge Handoff with resolvable provenance lineage.
  * The envelope validator (handoff.py) rejects a CompiledKnowledge that
    leaks governance vocabulary (structural D-A guarantee).
  * A CompiledKnowledge whose source ids do NOT resolve is rejected (D-D:
    citation resolution is verifiable; the verifier checks lineage, not truth).
"""
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fleet.crypto.foundation import IdentityRoot
from fleet.crypto.chriscrypt.store import JsonStore
from fleet.layers import ControlPlane, Handoff, HandoffError
from fleet.cognition.compiler import CompiledKnowledge


@pytest.fixture
def env(tmp_path):
    master = b"p2-cognition-master"
    audit = Ed25519PrivateKey.from_private_bytes(b"\x01" * 32)
    cp = ControlPlane(master, audit, store=JsonStore(str(tmp_path / "audit.json")),
                      now_fn=lambda: 1_000)
    skc = cp.publish_agent("skc-1", "analyst", ["compile"])
    return {"cp": cp, "skc": skc}


def _evidence(eid: str, extract: str) -> dict:
    return {
        "evidence_id": eid,
        "agent_id": "researcher-1",
        "citation": f"https://src/{eid}",
        "extract": extract,
        "source_hash": f"h-{eid}",
        "collected_at": 1_000,
    }


def test_compile_is_deterministic_and_signed(env):
    ev = [_evidence("ev1", "Acme Corp uses Cloud ERP"),
          _evidence("ev2", "Globex reported strong Cloud revenue")]
    ck1 = CompiledKnowledge.from_evidence("ck_a", env["skc"].cert, ev)
    ck2 = CompiledKnowledge.from_evidence("ck_a", env["skc"].cert, ev)
    assert ck1.to_payload() == ck2.to_payload()          # deterministic

    h = ck1.sign(env["skc"].cert, env["skc"].key)
    assert h.payload_type == "CompiledKnowledge"
    assert h.payload["compiler_cert_id"] == "skc-1"
    # provenance anchors every source id to a real artifact hash
    src_ids = {p["source_id"] for p in h.payload["provenance"]}
    assert src_ids == {"ev1", "ev2"}
    # consume verifies signature + schema + lineage resolution
    h.consume(env["cp"].registry, known_evidence={"ev1", "ev2"},
             known_compiled=set())


def test_compiled_knowledge_rejects_governance_leak(env):
    # mirror a CompiledKnowledge dict but inject a governance field
    bad = {
        "compile_id": "ck_bad",
        "compiler_cert_id": "skc-1",
        "entities": ["Acme Corp"],
        "provenance": [{"source_id": "ev1", "source_hash": "h-ev1",
                        "retrieved_at": 1_000}],
        "disposition": "AUTO",           # forbidden governance token
    }
    with pytest.raises(HandoffError):
        Handoff(payload_type="CompiledKnowledge", payload=bad,
                sender_cert=env["skc"].cert, sender_sig="x").consume(
            env["cp"].registry, known_evidence={"ev1"})


def test_unresolved_lineage_rejected(env):
    ev = [_evidence("ev1", "Acme Corp uses Cloud ERP")]
    ck = CompiledKnowledge.from_evidence("ck_c", env["skc"].cert, ev)
    h = ck.sign(env["skc"].cert, env["skc"].key)
    # cert authentic, schema valid, but provenance cites an unknown source
    with pytest.raises(HandoffError):
        h.consume(env["cp"].registry, known_evidence={"some_other_id"},
                  known_compiled=set())
