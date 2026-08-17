"""Q5 tests: Kelly sizing proposal (advisory, M0-preserving).

Real math, no mocks. We assert:
  * full-Kelly is capped to half-Kelly (capital-preservation),
  * a fair/negative edge yields NO_BET (never bet without an edge),
  * the Mandate position cap clamps the fraction (authority constraint, passed in),
  * the YES/NO side flip is correct,
  * invalid inputs degrade to an explicit, hashable NO_BET,
  * the signed evidence envelope verifies and breaks on tamper,
  * M0: the proposal is pure data and changes only the suggested qty, never the
    disposition verdict.
"""
from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fleet.crypto.foundation import AgentCert, canonical_bytes, sha256
from exchange.quant.kelly import (
    KellyProposal,
    build_kelly_evidence,
    propose_kelly_from_estimate,
    verify_kelly_evidence,
)
from exchange.quant.probability import ProbabilityEstimate


def _cert_key():
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


def _est(p_yes: float):
    return ProbabilityEstimate(exchange_id=1, p_yes=p_yes, model_id="demo", method="demo")


def test_kelly_fraction_formula_and_half_kelly_cap():
    # p=0.6, price=0.5 -> f* = 0.6 - 0.4*0.5/0.5 = 0.2 ; half-Kelly -> 0.1
    k = KellyProposal(p_win=0.6, price=0.5, available_usd=1000.0)
    assert k.raw_fraction == pytest.approx(0.2)
    assert k.capped_fraction == pytest.approx(0.1)  # half-Kelly cap default
    assert k.proposed_usd == pytest.approx(100.0)
    assert k.proposed_qty == 200  # floor(100 / 0.5)
    assert k.recommendation == "BET"


def test_full_kelly_cap_configurable():
    k = KellyProposal(
        p_win=0.6, price=0.5, available_usd=1000.0, kelly_fraction_cap=1.0
    )
    assert k.capped_fraction == pytest.approx(0.2)
    assert k.proposed_usd == pytest.approx(200.0)


def test_no_bet_without_edge():
    # fair price == probability -> f* = 0
    k = KellyProposal(p_win=0.5, price=0.5, available_usd=1000.0)
    assert k.raw_fraction == pytest.approx(0.0)
    assert k.recommendation == "NO_BET"
    assert k.proposed_qty == 0
    # negative edge -> clamped to NO_BET
    k2 = KellyProposal(p_win=0.3, price=0.5, available_usd=1000.0)
    assert k2.recommendation == "NO_BET"


def test_mandate_position_cap_clamps():
    # raw half-Kelly fraction would be 0.1, but Mandate cap 0.05 wins
    k = KellyProposal(
        p_win=0.6, price=0.5, available_usd=1000.0, max_position_fraction=0.05
    )
    assert k.capped_fraction == pytest.approx(0.05)
    assert k.proposed_usd == pytest.approx(50.0)


def test_side_flip_for_no():
    est = _est(0.6)
    yes = propose_kelly_from_estimate(est, price=0.5, available_usd=1000.0, side="YES")
    no = propose_kelly_from_estimate(est, price=0.5, available_usd=1000.0, side="NO")
    assert yes.p_win == pytest.approx(0.6)
    assert no.p_win == pytest.approx(0.4)


def test_invalid_inputs_degrade_to_no_bet_and_remain_hashable():
    k = KellyProposal(p_win=0.6, price=1.0, available_usd=1000.0)  # price must be in (0,1)
    assert k.recommendation == "NO_BET"
    assert k.sizing_hash and len(k.sizing_hash) == 64
    assert k.sizing_hash == sha256(canonical_bytes(k.state()))


def test_kelly_proposal_is_deterministic():
    a = KellyProposal(p_win=0.62, price=0.55, available_usd=2500.0)
    b = KellyProposal(p_win=0.62, price=0.55, available_usd=2500.0)
    assert a.sizing_hash == b.sizing_hash
    assert a.proposed_qty == b.proposed_qty


def test_kelly_evidence_envelope_signs_and_verifies():
    cert, key = _cert_key()
    est = _est(0.6)
    k = propose_kelly_from_estimate(est, price=0.5, available_usd=1000.0, side="YES")
    env = build_kelly_evidence(cert, key, k, proposal_hash="abc")
    assert env["signature"] and env["body"]["sizing_hash"]
    pub = key.public_key()
    assert verify_kelly_evidence(env, pub)
    env["body"]["sizing_hash"] = "tampered"
    assert not verify_kelly_evidence(env, pub)


def test_m0_proposal_is_advisory_not_authority():
    """M0: the Kelly proposal is pure data; it changes the suggested qty,
    never the disposition. We assert the proposal carries no verdict and the
    sizing math is a pure function of (p, price, capital, caps)."""
    k_small = KellyProposal(p_win=0.7, price=0.4, available_usd=500.0)
    k_big = KellyProposal(p_win=0.7, price=0.4, available_usd=5000.0)
    assert k_big.proposed_qty == 10 * k_small.proposed_qty
    forbidden = {"disposition", "authorization", "approval", "signature", "risk"}
    assert not (forbidden & set(k_big.state().keys()))
