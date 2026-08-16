"""Kalshi venue adapters.

Two adapters live here:

* :class:`KalshiStub` — the sim-first STUB (unchanged). It records intents and
  never touches the real Kalshi REST API. ``is_live()`` is always ``False``.
* :class:`KalshiLive` — a REAL, credentialed execution leg to Kalshi's REST API
  using Kalshi's RSA-PSS request signing. ``is_live()`` is ``True`` only when a
  private key was successfully loaded.

HONESTY / FAIL-CLOSED CONTRACT (mirrors PLANNING.md, §4):
  * Credentials are loaded from the environment (``KALSHI_API_KEY_ID`` /
    ``KALSHI_PRIVATE_KEY``), never from code or committed files. ``.env`` is
    gitignored.
  * ``KalshiLive.route()`` will NOT place an order unless ``allow_live_orders``
    is explicitly True on the instance. By default it refuses (REJECTED) so the
    exchange core cannot silently execute a real order.
  * Real execution is opt-in and the operator's legal responsibility. The agent
    will never flip it on without an explicit, separate confirmation.
  * Kalshi holds all funds / custody; we are a pass-through execution leg and
    our internal ledger is the shadow/attribution source of truth.

Kalshi request signing (per their API docs):
  message = timestamp_ms + METHOD + path(+query) + body
  signature = RSA-PSS(SHA-256, MGF1-SHA-256, salt=32) over message, base64.
  headers: Kalshi-API-Key, Kalshi-Request-Timestamp, Kalshi-Signature.
"""
from __future__ import annotations

import base64
import json
import os
import time
import uuid
from typing import Dict, List, Optional
from urllib import request as urllib_request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from .base import (
    NormalizedOrder,
    RouteResult,
    RoutingStatus,
    VenueAdapter,
    VenueFill,
)


def _load_env_file(path: str = ".env") -> None:
    """Minimal .env loader (no dependency); existing os.environ wins.

    Handles multi-line double-quoted values (e.g. a PEM private key spanning
    several lines) so the RSA key is loaded intact.
    """
    import re

    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except FileNotFoundError:
        return
    # Match: KEY="multi
    # line value"  or  KEY=value (single line)
    for m in re.finditer(
        r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*("(?:\\.|[^"\\])*"|[^#\r\n]*)',
        raw,
        re.MULTILINE,
    ):
        k = m.group(1)
        v = m.group(2)
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1].replace('\\"', '"')
        else:
            v = v.strip().strip("'")
        os.environ.setdefault(k, v)


class KalshiStub(VenueAdapter):
    name = "kalshi"
    venue = "Kalshi"

    def __init__(self, simulate: bool = True):
        self.simulate = simulate
        self.routed: List[NormalizedOrder] = []
        # venue_order_id -> last status, for cancel()
        self._orders: Dict[str, str] = {}

    def is_live(self) -> bool:
        return False

    def route(self, order: NormalizedOrder) -> RouteResult:
        self.routed.append(order)
        vid = f"kalshi_{uuid.uuid4().hex[:12]}"
        self._orders[vid] = "open"
        fills: List[VenueFill] = []
        detail = "stub: recorded intent only (not live)"
        if self.simulate and order.limit_cents is not None:
            # Deterministic sim fill: full qty at the limit price.
            fills.append(
                VenueFill(
                    venue_order_id=vid,
                    exchange_id=order.exchange_id,
                    price_cents=order.limit_cents,
                    qty=order.qty,
                    side=order.side,
                    ts=time.time(),
                )
            )
            detail = "stub: simulated fill (not live)"
        return RouteResult(
            status=RoutingStatus.NOT_LIVE,
            venue_order_id=vid,
            fills=fills,
            detail=detail,
        )

    def cancel(self, venue_order_id: str) -> RouteResult:
        if venue_order_id in self._orders:
            self._orders[venue_order_id] = "cancelled"
            return RouteResult(status=RoutingStatus.NOT_LIVE, venue_order_id=venue_order_id, detail="stub: cancelled")
        return RouteResult(status=RoutingStatus.REJECTED, detail="unknown venue order id")


class KalshiLive(VenueAdapter):
    """Real Kalshi REST execution leg.

    Fail-closed: ``is_live()`` is True only if a private key loaded. ``route()``
    refuses unless ``allow_live_orders`` is set True on the instance.
    """

    name = "kalshi"
    venue = "Kalshi"

    # Kalshi v2 demo (risk-free) by default. Production: external-api.kalshi.com/trade-api/v2
    DEFAULT_BASE_URL = "https://external-api.demo.kalshi.co/trade-api/v2"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key_id: Optional[str] = None,
        private_key_pem: Optional[str] = None,
        allow_live_orders: bool = False,
    ):
        # Load gitignored creds FIRST so the package's exchange/.env wins.
        # venues/ -> ../ = exchange/ ; ../.env = exchange/.env. No-op if absent.
        _load_env_file(os.path.join(os.path.dirname(__file__), "..", ".env"))
        _load_env_file(".env")

        self.base_url = (base_url or os.environ.get("KALSHI_BASE_URL") or self.DEFAULT_BASE_URL).rstrip("/")
        self.api_key_id = api_key_id or os.environ.get("KALSHI_API_KEY_ID")
        self.private_key_pem = private_key_pem or os.environ.get("KALSHI_PRIVATE_KEY")
        self.allow_live_orders = allow_live_orders

        self._key = None
        if self.private_key_pem:
            self._key = serialization.load_pem_private_key(
                self.private_key_pem.encode("utf-8"), password=None
            )
        self._orders: Dict[str, str] = {}

    # -- liveness -----------------------------------------------------------
    def is_live(self) -> bool:
        return self._key is not None

    # -- signing ------------------------------------------------------------
    def _sign(self, method: str, path: str, body: bytes) -> tuple[str, str]:
        if self._key is None:
            raise RuntimeError("KalshiLive has no private key loaded")
        ts = str(int(time.time() * 1000))
        msg = ts + method.upper() + path + (body.decode("utf-8") if body else "")
        sig = self._key.sign(
            msg.encode("utf-8"),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
            hashes.SHA256(),
        )
        return ts, base64.b64encode(sig).decode("ascii")

    # -- transport ----------------------------------------------------------
    def _signed_request(self, method: str, path: str, body: Optional[dict] = None) -> urllib_request.Request:
        if not self.is_live():
            raise RuntimeError("KalshiLive has no private key loaded")
        url = self.base_url + path
        data = json.dumps(body).encode("utf-8") if body is not None else b""
        ts, sig = self._sign(method, path, data)
        headers = {
            "Kalshi-API-Key": self.api_key_id,
            "Kalshi-Request-Timestamp": ts,
            "Kalshi-Signature": sig,
            "Content-Type": "application/json",
        }
        return urllib_request.Request(url, data=data or None, headers=headers, method=method.upper())

    def _request(self, method: str, path: str, body: Optional[dict] = None):
        if not self.is_live():
            return RouteResult(status=RoutingStatus.REJECTED, detail="no kalshi credentials loaded")
        try:
            with urllib_request.urlopen(self._signed_request(method, path, body), timeout=15) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib_request.HTTPError as e:
            try:
                b = json.loads(e.read().decode("utf-8")) if e.fp else None
            except Exception:
                b = None
            return e.code, b
        except Exception as e:
            return RouteResult(status=RoutingStatus.REJECTED, detail=f"kalshi request error: {e}")

    # -- read-only proof (no order) -----------------------------------------
    def get_exchange_status(self) -> tuple[int, Optional[dict]]:
        """Read-only: proves RSA-PSS auth + request headers are accepted by Kalshi.

        Always returns ``(status, body)``; ``(401, None)`` when not live.
        """
        if not self.is_live():
            return 401, None
        return self._get_readonly("/exchange/status")

    def get_market(self, ticker: str) -> tuple[int, Optional[dict]]:
        """Read-only: fetch a market's price (yes_bid/yes_ask). No order.

        Always returns ``(status, body)``; ``(401, None)`` when not live so
        callers don't have to special-case a RouteResult.
        """
        if not self.is_live():
            return 401, None
        return self._get_readonly(f"/markets/{ticker}")

    def _get_readonly(self, path: str) -> tuple[int, Optional[dict]]:
        """Authenticated GET that ALWAYS returns (status, body). No order."""
        if not self.is_live():
            return 401, None
        try:
            with urllib_request.urlopen(self._signed_request("GET", path), timeout=15) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib_request.HTTPError as e:
            try:
                body = json.loads(e.read().decode("utf-8")) if e.fp else None
            except Exception:
                body = None
            return e.code, body
        except Exception:
            return 0, None

    # -- write paths (fail-closed) ------------------------------------------
    def route(self, order: NormalizedOrder) -> RouteResult:
        if not self.allow_live_orders:
            return RouteResult(
                status=RoutingStatus.REJECTED,
                detail="KalshiLive.allow_live_orders is False (fail-closed; no real order placed)",
            )
        if not self.is_live():
            return RouteResult(status=RoutingStatus.REJECTED, detail="no kalshi credentials loaded")
        payload = {
            # Real Kalshi ticker resolved from the canonical exchange_id via the
            # InstrumentRegistry (router stamps venue_ticker). Falls back to the
            # id only when no alias mapping exists (still fail-closed otherwise).
            "ticker": order.venue_ticker or str(order.exchange_id),
            "action": order.side.lower(),
            "type": "limit",
            "side": order.side.lower(),
            "count": order.qty,
            "yes_price": (order.limit_cents // 100) if order.limit_cents else None,
            "client_order_id": order.client_order_id,
        }
        try:
            status, body = self._request("POST", "/orders", payload)
        except Exception as e:  # noqa: BLE001 — surface, never swallow
            return RouteResult(status=RoutingStatus.REJECTED, detail=f"kalshi order error: {e}")
        if not isinstance(body, dict):
            return RouteResult(status=RoutingStatus.REJECTED, detail=f"kalshi order unexpected response: {status}")
        vid = body.get("order_id") or body.get("order", {}).get("order_id")
        if not vid:
            return RouteResult(status=RoutingStatus.REJECTED, detail=f"kalshi order no order_id (status {status})")
        self._orders[vid] = "open"
        return RouteResult(
            status=RoutingStatus.ROUTED,
            venue_order_id=vid,
            detail=f"live kalshi order posted ({self.base_url})",
        )

    def cancel(self, venue_order_id: str) -> RouteResult:
        if not self.is_live():
            return RouteResult(status=RoutingStatus.REJECTED, detail="no kalshi credentials loaded")
        try:
            status, body = self._request("DELETE", f"/orders/{venue_order_id}")
        except Exception as e:  # noqa: BLE001
            return RouteResult(status=RoutingStatus.REJECTED, detail=f"kalshi cancel error: {e}")
        self._orders[venue_order_id] = "cancelled"
        return RouteResult(status=RoutingStatus.ROUTED, venue_order_id=venue_order_id, detail="live kalshi cancel")


__all__ = ["KalshiStub", "KalshiLive"]
