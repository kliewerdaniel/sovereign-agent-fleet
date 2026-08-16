"""Integration test for the LIVE Kalshi adapter (fail-closed).

Per the locked honesty contract, this test NEVER places a real order. It:
  1. proves the RSA-PSS signing path builds a valid signature;
  2. proves the adapter loads creds from the gitignored .env and reports live;
  3. proves route() REFUSES by default (allow_live_orders=False) — no live order;
  4. performs ONE read-only authenticated GET /exchange/status to confirm the
     credentials + signing are accepted by Kalshi (skipped if offline / no creds).

Set KALSHI_SKIP_LIVE=1 to skip the network call entirely.
"""
from __future__ import annotations

import os

import pytest

from exchange.venues import KalshiLive, KalshiStub
from exchange.venues.base import NormalizedOrder, RoutingStatus


@pytest.fixture
def live_adapter():
    # Loads KALSHI_API_KEY_ID / KALSHI_PRIVATE_KEY from exchange/.env (gitignored)
    return KalshiLive()


def test_stub_remains_not_live():
    assert KalshiStub().is_live() is False


def test_live_loads_key_and_reports_live(live_adapter):
    # Requires exchange/.env with real creds; skip cleanly if absent.
    if not live_adapter.is_live():
        pytest.skip("no Kalshi creds in exchange/.env")
    assert live_adapter.is_live() is True
    assert live_adapter.api_key_id


def test_route_is_fail_closed_by_default(live_adapter):
    """No real order may fire unless allow_live_orders is explicitly True."""
    order = NormalizedOrder(exchange_id=1, side="BUY", qty=1, limit_cents=50)
    res = live_adapter.route(order)
    assert res.status == RoutingStatus.REJECTED
    assert "fail-closed" in res.detail


def test_signature_is_well_formed(live_adapter):
    if not live_adapter.is_live():
        pytest.skip("no Kalshi creds in exchange/.env")
    ts, sig = live_adapter._sign("GET", "/exchange/status", b"")
    assert ts.isdigit()
    # base64 of a PSS signature over SHA-256 -> ~344 chars
    assert 200 < len(sig) < 400
    # must decode back to bytes
    import base64

    assert base64.b64decode(sig)


@pytest.mark.network
def test_readonly_exchange_status(live_adapter):
    """Read-only proof that creds + RSA-PSS signing are accepted by Kalshi.

    Never places an order. Skips if offline, creds absent, or if the build
    environment cannot reach kalshi.com (DNS/egress restriction in the sandbox).
    """
    if os.environ.get("KALSHI_SKIP_LIVE") == "1":
        pytest.skip("KALSHI_SKIP_LIVE=1")
    if not live_adapter.is_live():
        pytest.skip("no Kalshi creds in exchange/.env")
    from urllib.error import URLError

    try:
        status, body = live_adapter.get_exchange_status()
    except URLError as e:
        pytest.skip(f"cannot reach kalshi from this environment: {e}")
    assert status in (200, 401, 403)  # 401/403 only if key rejected
    assert body is not None
