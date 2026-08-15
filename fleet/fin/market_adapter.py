"""MarketDataAdapter — trusted normalization boundary for market data.

Two sources, one normalized output (D27 Round 3/6):

  External Feed A ─┐
                   ├─ MarketDataAdapter → cross-validate (when ≥2) → normalized
  External Feed B ┘                                                          snapshot
                                                                             │
  Bundled deterministic snapshot ───────────────────────────────────────┘
                                                                             │
                                                                  signed local snapshot

A signature proves provenance (authenticity), NOT truth (D27 I16). The adapter
verifies the feed envelope with the SAME Model Armor primitive the rest of the
fleet uses (verify_tool_envelope), then projects to declared structured fields
so no free-text injection surface reaches the model (sanitize_tool_result).

The deterministic replay fixture is AUTHORITATIVE for the demo and requires no
network. Live feeds are an optional realism layer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from fleet.crypto.foundation import canonical_bytes, sha256
from fleet.layers.armor import (
    InjectionError,
    sanitize_tool_result,
    verify_tool_envelope,
)
from fleet.layers.runtime import RuntimeError_  # reuse fleet's runtime error
from fleet.fin.domain import MarketData


ALLOWED_MARKET_FIELDS = ["symbol", "ts", "bid", "ask", "last", "vol"]


def _normalize(raw: dict, source_id: str, ts_floor: int = 0) -> MarketData:
    """Project a raw tool result to a structured MarketData snapshot."""
    structured = sanitize_tool_result(raw, ALLOWED_MARKET_FIELDS)
    return MarketData(
        symbol=structured["symbol"],
        ts=int(structured.get("ts", ts_floor)),
        bid=float(structured["bid"]),
        ask=float(structured["ask"]),
        last=float(structured["last"]),
        vol=float(structured.get("vol", 0.0)),
        source_id=source_id,
    )


def from_feed_envelope(tool_envelope, registry) -> MarketData:
    """Ingest a signed feed envelope. Proves authenticity (not truth)."""
    tool_cert = registry.get_cert(tool_envelope.tool_id)
    if tool_cert is None:
        raise RuntimeError_("market feed identity unknown to registry")
    if not verify_tool_envelope(tool_envelope, tool_cert.pubkey_pem):
        raise RuntimeError_("market feed envelope failed signature verification")
    raw = json.loads(tool_envelope.output.decode("utf-8"))
    return _normalize(raw, source_id=tool_envelope.tool_id)


def cross_validate(feeds: List[MarketData], tol_pct: float = 0.01) -> Dict[str, object]:
    """Cross-feed consistency check (D27 I16). Logs discrepancy when ≥2 feeds,
    but does NOT reject — authenticity is proven per-feed; truth is out of scope.
    Returns the first feed's snapshot as the working reference + a discrepancy flag.
    """
    if len(feeds) < 2:
        return {"reference": feeds[0] if feeds else None, "discrepancy": False}
    ref = feeds[0].last
    discrepancy = any(abs(f.last - ref) > tol_pct * ref for f in feeds[1:])
    return {"reference": feeds[0], "discrepancy": discrepancy}


# ---------------------------------------------------------------------------
# Authoritative offline replay fixture
# ---------------------------------------------------------------------------

@dataclass
class ReplayFixture:
    """Bundled deterministic market snapshot. Always works offline; authoritative
    for the demo. A verifier reproduces it byte-for-byte."""
    symbol: str
    ts: int
    bid: float
    ask: float
    last: float
    vol: float
    source_id: str = "replay"

    def to_market_data(self) -> MarketData:
        return MarketData(symbol=self.symbol, ts=self.ts, bid=self.bid,
                          ask=self.ask, last=self.last, vol=self.vol,
                          source_id=self.source_id)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol, "ts": self.ts, "bid": self.bid,
            "ask": self.ask, "last": self.last, "vol": self.vol,
            "source_id": self.source_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ReplayFixture":
        return cls(symbol=d["symbol"], ts=int(d["ts"]), bid=float(d["bid"]),
                   ask=float(d["ask"]), last=float(d["last"]),
                   vol=float(d.get("vol", 0.0)), source_id=d.get("source_id", "replay"))


def load_replay(path: str) -> ReplayFixture:
    with open(path, "r") as f:
        return ReplayFixture.from_dict(json.load(f))
