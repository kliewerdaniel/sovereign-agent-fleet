"""Q6-live: quant advisory enrichment wired into the exchange REST surface.

Proves the demo loop closes through the real API while preserving M0:
  * POST /order with model_p_yes returns a signed, verified `quant` blob,
  * the `quant` blob is ADVISORY ONLY — it never changes authorization/risk/qty,
  * a BLOCKED order (HALLUCINATION intel) still returns 403 with no quant leak,
  * the executed qty uses req.qty, never the Kelly suggestion.
No live orders, no changes to the verdict path in exchange/governance.py.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from exchange.api import get_exchange


def _client():
    return TestClient(__import__("exchange.api", fromlist=["app"]).app)


def _reset(exchange_id: int = 1):
    from exchange.api import _state
    _state.pop(exchange_id, None)
    return get_exchange(exchange_id)


def test_order_with_quant_enrichment_attaches_signed_evidence():
    _reset()
    c = _client()
    # seed a resting SELL at 55 so the BUY@60 crosses and executes
    c.post("/order", json={"side": "SELL", "qty": 20, "limit_cents": 55, "subaccount_id": "maker"})
    r = c.post("/order", json={
        "side": "BUY", "qty": 10, "limit_cents": 60,
        "subaccount_id": "t", "model_p_yes": 0.70, "available_usd": 1000.0,
    })
    assert r.status_code == 200
    body = r.json()
    # verdict path unaffected
    assert body["authorization"] == "AUTO"
    assert body["executed_qty"] == 10           # req.qty, NOT the kelly suggestion
    assert body["risk"] == "LOW"
    # advisory enrichment present and signed
    q = body["quant"]
    assert q is not None and q["advisory"] is True
    assert q["model_p_yes"] == 0.70
    assert q["edge"] is not None
    assert q["envelope"]["signature"]
    assert q["envelope"]["verified"] is True
    assert q["envelope"]["proposal_hash"] == body["order_id"]


def test_quant_is_advisory_only_qty_unchanged_when_kelly_disagrees():
    _reset()
    c = _client()
    # seed a resting SELL at 45 so the BUY@50 crosses and executes
    c.post("/order", json={"side": "SELL", "qty": 20, "limit_cents": 45, "subaccount_id": "maker"})
    # Model prob == market mid => edge ~0 => Kelly NO_BET; order still executes at qty 10
    r = c.post("/order", json={
        "side": "BUY", "qty": 10, "limit_cents": 50,
        "subaccount_id": "t", "model_p_yes": 0.50, "available_usd": 1000.0,
    })
    body = r.json()
    assert body["authorization"] == "AUTO"
    assert body["executed_qty"] == 10
    assert body["quant"]["kelly_recommendation"] == "NO_BET"
    assert body["quant"]["suggested_qty"] == 0   # advisory, ignored by execution


def test_order_without_model_p_yes_has_no_quant_blob():
    _reset()
    c = _client()
    r = c.post("/order", json={"side": "BUY", "qty": 10, "limit_cents": 60, "subaccount_id": "t"})
    body = r.json()
    assert body["quant"] is None


def test_quant_enrichment_never_leaks_into_blocked_order():
    _reset()
    c = _client()
    r = c.post("/order", json={
        "side": "BUY", "qty": 10, "limit_cents": 55, "subaccount_id": "t",
        "intel": "HALLUCINATION", "model_p_yes": 0.70,
    })
    # blocked before quant is attached (and quant is advisory, never consulted)
    assert r.status_code == 403
    assert "BLOCKED" in r.json()["detail"]


def test_quant_enrichment_on_human_tier_is_advisory_only():
    _reset()
    c = _client()
    r = c.post("/order", json={
        "side": "BUY", "qty": 500, "limit_cents": 55, "subaccount_id": "t",
        "model_p_yes": 0.70,
    })
    body = r.json()
    assert body["authorization"] == "HUMAN"
    assert body["quant"] is not None
    assert body["quant"]["advisory"] is True
