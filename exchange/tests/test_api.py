"""E6 API integration tests: order lifecycle across all authorization tiers.

Uses FastAPI TestClient. Exercises the real governance + matching + bus
end-to-end through HTTP, asserting the front end has zero authority (BLOCKED
and HUMAN tiers never execute without the server's decision).
"""
import json

from fastapi.testclient import TestClient

from exchange.api import app
from exchange.core.events import EventType
from exchange.governance import approve_trade
from fleet.crypto.foundation import AgentCert  # type: ignore

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _client():
    return TestClient(app)


def _human():
    key = Ed25519PrivateKey.generate()
    pub_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    cert = AgentCert(
        agent_id="human-1", pubkey_pem=pub_pem, role="human-approver",
        capabilities=["exchange.trade_execute"], issued_at=0,
        expires_at=9999999999, cert_seq=1, root_sig="test",
    )
    return cert, key, pub_pem


def test_health():
    c = _client()
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "sovereign-exchange"


def test_auto_order_executes_and_emits_trade():
    c = _client()
    # flip to live venues so the matrix permits AUTO execution on both sides
    from exchange.api import _state, get_exchange

    get_exchange().live_venues = True
    # seed a resting BUY at 0.50 so a SELL at 0.45 (limit) can cross it at 0.50
    seed = c.post("/order", json={"side": "BUY", "qty": 50, "limit_cents": 50, "subaccount_id": "maker"})
    assert seed.json()["authorization"] == "AUTO"
    # the resting buy should be in the book
    assert _state[1].book.depth() == 1
    # SELL limit 45 crosses the 50 bid (seller gets 50 >= 45 limit)
    r = c.post("/order", json={"side": "SELL", "qty": 50, "limit_cents": 45, "subaccount_id": "taker"})
    assert r.status_code == 200
    body = r.json()
    assert body["authorization"] == "AUTO"
    assert body["executed_qty"] == 50
    assert len(body["fills"]) == 1
    # venue route result is labeled NOT_LIVE (stub)
    assert body["route"]["legs"][0]["result"]["status"] == "not_live"


def test_blocked_on_hallucination_intel():
    c = _client()
    r = c.post("/order", json={
        "side": "BUY", "qty": 10, "limit_cents": 55, "subaccount_id": "t",
        "intel": "HALLUCINATION",
    })
    assert r.status_code == 403
    assert "BLOCKED" in r.json()["detail"]


def test_human_order_returns_token_then_executes_with_signature():
    c = _client()
    cert, key, pub_pem = _human()
    # a large buy -> HUMAN tier
    r = c.post("/order", json={"side": "BUY", "qty": 500, "limit_cents": 55, "subaccount_id": "t"})
    assert r.status_code == 200
    body = r.json()
    assert body["authorization"] == "HUMAN"
    token = body["approval_token"]
    assert token is not None

    # pending list shows the token
    pend = c.get("/approvals/pending").json()
    assert any(p["token"] == token for p in pend)

    # sign a real approval bound to this exact order
    # recover the artifact_hash from the pending record
    meta = next(p for p in pend if p["token"] == token)
    rec = approve_trade(cert, key, meta["client_order_id"], meta["exchange_id"],
                        meta["side"], meta["qty"], meta["limit_cents"], meta["venue"])
    # submit the signed decision
    r2 = c.post(f"/approvals/{token}/decide", json={
        "token": token,
        "human_id": cert.agent_id,
        "human_sig": rec["human_sig"],
        "human_pubkey_pem": pub_pem,
        "approval_id": rec["approval_id"],
        "capability": rec["capability"],
        "artifact_hash": rec["artifact_hash"],
        "decision": rec["decision"],
        "reason": rec["reason"],
        "ts": rec["ts"],
    })
    assert r2.status_code == 200
    assert r2.json()["accepted"] is True
    # token consumed
    assert all(p["token"] != token for p in c.get("/approvals/pending").json())


def test_human_order_rejected_with_bad_signature():
    c = _client()
    cert, key, pub_pem = _human()
    r = c.post("/order", json={"side": "SELL", "qty": 500, "limit_cents": 55, "subaccount_id": "t"})
    token = r.json()["approval_token"]
    # submit a garbage signature -> fail-closed
    r2 = c.post(f"/approvals/{token}/decide", json={
        "token": token, "human_id": "x", "human_sig": "deadbeef",
        "human_pubkey_pem": pub_pem, "approval_id": "a", "capability": "exchange.trade_execute",
        "artifact_hash": "wrong", "decision": "approve", "ts": 1,
    })
    assert r2.json()["accepted"] is False


def test_instruments_endpoint_exposes_venue_alias():
    c = _client()
    r = c.get("/instruments")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    inst = body["instruments"][0]
    # the seeded instrument carries a real Kalshi alias
    assert inst["venue"] == "kalshi"
    assert inst["venue_ticker"] == "KXFEDDECISION-26JUN-C25"
    assert inst["venue_alias_resolved"] is True


def test_quotes_endpoint_honest_liveness():
    c = _client()
    r = c.get("/quotes")
    assert r.status_code == 200
    body = r.json()
    # sim feed is not live; quotes carry an honest live flag + resolved ticker
    assert body["live"] is False
    assert body["feed"] == "sim"
    q = body["quotes"][0]
    assert q["venue"] == "sim"
    assert q["live"] is False
    assert 1 <= q["bid_cents"] <= q["ask_cents"] <= 99


def test_quotes_tick_publishes_quote_event_on_bus():
    from exchange.api import Exchange, get_exchange
    from exchange.core.events import EventType

    ex = Exchange(1)  # fresh instance, isolated bus
    seen: list[str] = []
    ex.bus.subscribe(lambda e: seen.append(e.type.value) if e.type == EventType.QUOTE else None)
    ex.publish_quotes()
    assert "quote" in seen
    # the published quote carries the resolved alias ticker + honest liveness
    assert ex.feed.quote(1, ticker="KXFEDDECISION-26JUN-C25").live is False
