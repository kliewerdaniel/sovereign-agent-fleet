"""E5 governance wrap tests: risk matrix + real fleet crypto approval binding.

Imports ``fleet`` as a library — uses the real ``Authorization`` enum and the
real Ed25519 ``Approval.sign`` / ``verify_approval`` for human approvals.
"""
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from exchange.governance import (
    Authorization,
    approve_trade,
    bind_order_artifact,
    classify_risk,
    decide_trade,
    verify_trade_approval,
)
from fleet.crypto.foundation import AgentCert  # type: ignore


def _human():
    key = Ed25519PrivateKey.generate()
    pub_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    cert = AgentCert(
        agent_id="human-1",
        pubkey_pem=pub_pem,
        role="human-approver",
        capabilities=["exchange.trade_execute"],
        issued_at=0,
        expires_at=9999999999,
        cert_seq=1,
        root_sig="test",
    )
    return cert, key


def test_auto_for_small_live_buy():
    d = decide_trade("c1", 1, "BUY", 50, 55, "kalshi", venue_live=True)
    assert d.authorization == Authorization.AUTO
    assert d.requires_approval is False
    assert d.risk.value == "LOW"


def test_blocked_on_hallucination_intel():
    d = decide_trade("c2", 1, "BUY", 10, 55, "kalshi", venue_live=True, intel="HALLUCINATION")
    assert d.authorization == Authorization.BLOCKED
    assert d.requires_approval is False


def test_human_for_large_or_stub_venue():
    big = decide_trade("c3", 1, "BUY", 500, 55, "kalshi", venue_live=True)
    assert big.authorization == Authorization.HUMAN
    assert big.requires_approval is True

    stub = decide_trade("c4", 1, "SELL", 50, 55, "kalshi", venue_live=False)
    assert stub.authorization == Authorization.HUMAN


def test_classify_risk_monotonic():
    assert classify_risk(10, "BUY", True).value == "LOW"
    assert classify_risk(500, "BUY", True).value == "MEDIUM"
    assert classify_risk(2000, "BUY", True).value == "HIGH"
    # stub venue pushes risk up
    assert classify_risk(60, "BUY", False).value == "MEDIUM"


def test_human_approval_roundtrip_binds_exact_order():
    cert, key = _human()
    rec = approve_trade(cert, key, "c5", 1, "BUY", 500, 55, "kalshi")
    assert rec["decision"] == "approve"
    assert rec["human_sig"]
    # verify with the EXACT bound order -> True
    ok = verify_trade_approval(rec, cert, "c5", exchange_id=1, side="BUY", qty=500, limit_cents=55, venue="kalshi")
    assert ok is True


def test_approval_rebinding_fails_closed():
    cert, key = _human()
    rec = approve_trade(cert, key, "c6", 1, "BUY", 500, 55, "kalshi")
    # attempt to rebind to a DIFFERENT order -> fail closed
    rebind = verify_trade_approval(rec, cert, "c6-other", exchange_id=1, side="BUY", qty=500, limit_cents=55, venue="kalshi")
    assert rebind is False
    # tamper the decision -> fail closed
    forged = dict(rec)
    forged["decision"] = "deny"
    assert verify_trade_approval(forged, cert, "c6", exchange_id=1, side="BUY", qty=500, limit_cents=55, venue="kalshi") is False


def test_artifact_hash_is_order_specific():
    a = bind_order_artifact("x", 1, "BUY", 100, 50, "kalshi")
    b = bind_order_artifact("x", 1, "BUY", 100, 51, "kalshi")
    assert a != b
