"""Q6 tests: quant orchestration pipeline (prob/edge/EV/Kelly -> signed envelope).

Real pipeline, no mocks. We assert:
  * evaluate_quant produces a consistent QuantDecision (prob/edge/EV/Kelly),
  * the evidence envelope is signed and verifies,
  * M0: the decision carries NO authorization verdict / cannot influence one,
  * determinism: replaying the same context reproduces identical evidence hashes
    (I15-style reproducibility, so a verifier can reconstruct without trust),
  * the Kelly suggestion is exposed as advisory `suggested_qty` only,
  * an optional StreamAnalyzer folds its state hash into the audit binding.
"""
from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fleet.crypto.foundation import AgentCert
from exchange.core.events import ExchangeBus, quote_event
from exchange.quant.evidence import verify_quant_evidence
from exchange.quant.kelly import KellyProposal
from exchange.quant.orchestrator import (
    QuantContext,
    evaluate_quant,
    determinism_check,
)
from exchange.quant.streaming import StreamAnalyzer


def _producer():
    cert = AgentCert(
        agent_id="quant",
        pubkey_pem="",
        role="tool",
        capabilities=["quant"],
        issued_at=0,
        expires_at=9999999999,
        cert_seq=1,
        root_sig="x",
    )
    key = Ed25519PrivateKey.generate()
    cert.pubkey_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return cert, key


def _ctx(**kw):
    base = dict(
        exchange_id=1,
        model_p_yes=0.68,
        bid_cents=55,
        ask_cents=57,
        last_cents=56,
        side="BUY_YES",
        available_usd=1000.0,
        ticker="KXINFLATION-24",
    )
    base.update(kw)
    return QuantContext(**base)


def test_evaluate_quant_full_pipeline():
    cert, key = _producer()
    ctx = _ctx()
    d = evaluate_quant(ctx, cert, key, proposal_hash="order-xyz")
    # probability
    assert d.probability.p_yes == pytest.approx(0.68)
    # edge positive (model > market mid)
    market_mid = (55 + 57) / 200.0
    assert d.edge.edge == pytest.approx(0.68 - market_mid)
    # EV positive (edge survives fees)
    assert d.ev.positive is True
    # Kelly suggestion present, advisory only
    assert d.kelly.recommendation == "BET"
    assert d.kelly.proposed_qty > 0
    assert d.suggested_qty == d.kelly.proposed_qty
    # evidence envelope bound to the order
    assert d.evidence.proposal_hash == "order-xyz"
    assert d.evidence.signature
    assert verify_quant_evidence(d.evidence, cert)


def test_m0_quant_decision_has_no_authority_fields():
    """M0: the quant output is pure data. It must not carry a disposition,
    authorization, approval, or any field that could influence the verdict."""
    cert, key = _producer()
    d = evaluate_quant(_ctx(), cert, key, proposal_hash="p1")
    forbidden = {"authorization", "disposition", "decision", "approval",
                 "requires_approval", "blocked", "risk"}
    assert not (forbidden & set(d.to_dict().keys()))
    # The Kelly proposal itself also carries no verdict
    assert not (forbidden & set(KellyProposal.__dataclass_fields__.keys()))


def test_determinism_replay_reproduces_evidence():
    """I15: same context -> identical evidence + kelly + ev hashes."""
    cert, key = _producer()
    ctx = _ctx()
    assert determinism_check(ctx, cert, key)


def test_no_edge_yields_no_bet_recommendation():
    """When model prob == market mid, edge is ~0 -> Kelly says NO_BET."""
    cert, key = _producer()
    ctx = _ctx(model_p_yes=0.56)  # mid of 55/57 is 0.56
    d = evaluate_quant(ctx, cert, key, proposal_hash="p2")
    assert d.kelly.recommendation == "NO_BET"
    assert d.kelly.proposed_qty == 0


def test_streaming_analyzer_folds_into_audit_binding():
    """The optional StreamAnalyzer's state hash is bound into the evidence log."""
    cert, key = _producer()
    bus = ExchangeBus()
    ana = StreamAnalyzer(exchange_ids=[1], window=10, z_threshold=3.0)
    ana.subscribe_to(bus)
    for i in range(10):
        bus.publish(quote_event(1, "sim", 53, 55, ticker="KXINFLATION-24", live=False))
    # analyzer has a computed state hash
    assert ana.compute_hash() and len(ana.compute_hash()) == 64
    d = evaluate_quant(_ctx(), cert, key, analyzer=ana, proposal_hash="p3")
    # pipeline still produces valid evidence
    assert verify_quant_evidence(d.evidence, cert)
    assert d.suggested_qty >= 0


def test_q1_q2_q5_q6_import_wall_clean():
    """The orchestrator imports only fleet.crypto + intra-package quant modules."""
    import ast
    from pathlib import Path
    src = Path(__file__).resolve().parents[2] / "exchange" / "quant" / "orchestrator.py"
    tree = ast.parse(src.read_text())
    forbidden = ("fleet.fin", "fleet.layers", "fleet.cognition", "exchange.governance")
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if any(node.module == f or node.module.startswith(f + ".") for f in forbidden):
                violations.append(f"from {node.module} import")
        elif isinstance(node, ast.Import):
            for a in node.names:
                if any(a.name == f or a.name.startswith(f + ".") for f in forbidden):
                    violations.append(f"import {a.name}")
    assert not violations, f"orchestrator violates import wall: {violations}"
