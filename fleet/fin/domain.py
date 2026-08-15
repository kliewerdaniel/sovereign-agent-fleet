"""Financial domain model + deterministic risk engine (fleet/fin).

PURE, deterministic, no model calls. This module is the financial workload's
Layer-2 risk brain: it takes a proposal, the live account snapshot, the market
data, and a mandate, and returns a recomputable RiskAssessment + authorization
disposition. A verifier imports this exact code to independently recompute.

No security invariant here depends on model behavior (meta-invariant M0).

Constrained to v1 (D27 Round 6): single paper account, equities/ETFs, MARKET +
LIMIT orders, LONG-only. No shorts/options/futures/crypto/FX/leverage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from fleet.crypto.foundation import canonical_bytes, sha256


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class Disposition(str, Enum):
    AUTO = "AUTO"        # execute without human approval
    HUMAN = "HUMAN"      # requires a cryptographically-bound human approval
    BLOCKED = "BLOCKED"  # never permitted under this policy


# ---------------------------------------------------------------------------
# Mandate (risk bounds for the account)
# ---------------------------------------------------------------------------

@dataclass
class Mandate:
    allowed_assets: List[str]
    allowed_sides: List[str] = field(default_factory=lambda: ["BUY"])
    max_position_pct: float = 0.20      # single-position value / total value
    max_order_usd: float = 10_000.0     # notional per order
    max_daily_loss_usd: float = 5_000.0
    max_orders_per_day: int = 25

    def state(self) -> dict:
        return {
            "allowed_assets": list(self.allowed_assets),
            "allowed_sides": list(self.allowed_sides),
            "max_position_pct": self.max_position_pct,
            "max_order_usd": self.max_order_usd,
            "max_daily_loss_usd": self.max_daily_loss_usd,
            "max_orders_per_day": self.max_orders_per_day,
        }


# ---------------------------------------------------------------------------
# Market data (produced by MarketDataAdapter; authenticity signed, not truth)
# ---------------------------------------------------------------------------

@dataclass
class MarketData:
    symbol: str
    ts: int
    bid: float
    ask: float
    last: float
    vol: float
    source_id: str
    snapshot_hash: str = ""

    def __post_init__(self):
        if not self.snapshot_hash:
            self.snapshot_hash = self.compute_hash()

    def compute_hash(self) -> str:
        return sha256(canonical_bytes({
            "symbol": self.symbol, "ts": self.ts, "bid": self.bid,
            "ask": self.ask, "last": self.last, "vol": self.vol,
            "source_id": self.source_id,
        }))

    def state(self) -> dict:
        return {
            "symbol": self.symbol, "ts": self.ts, "bid": self.bid,
            "ask": self.ask, "last": self.last, "vol": self.vol,
            "source_id": self.source_id,
        }


# ---------------------------------------------------------------------------
# Account / Position (paper, simulated settlement only)
# ---------------------------------------------------------------------------

@dataclass
class Position:
    symbol: str
    qty: float
    avg_price: float
    side: str = "BUY"

    def state(self) -> dict:
        return {"symbol": self.symbol, "qty": self.qty,
                "avg_price": self.avg_price, "side": self.side}


@dataclass
class Account:
    account_id: str
    cash: float
    positions: Dict[str, Position]
    base_ccy: str = "USD"
    mandate: Optional[Mandate] = None
    orders_today: int = 0
    daily_realized_pnl: float = 0.0

    def market_value(self, price_of) -> float:
        """Total portfolio value using a price lookup ``price_of(symbol) -> float``."""
        mv = self.cash
        for p in self.positions.values():
            mv += p.qty * price_of(p.symbol)
        return mv

    def position_value(self, symbol: str, price_of) -> float:
        p = self.positions.get(symbol)
        return (p.qty * price_of(symbol)) if p else 0.0

    def state(self) -> dict:
        return {
            "account_id": self.account_id,
            "cash": self.cash,
            "base_ccy": self.base_ccy,
            "positions": {s: p.state() for s, p in sorted(self.positions.items())},
            "orders_today": self.orders_today,
            "daily_realized_pnl": self.daily_realized_pnl,
            "mandate": self.mandate.state() if self.mandate is not None else None,
        }


def account_state_hash(account: Account) -> str:
    return sha256(canonical_bytes(account.state()))


# ---------------------------------------------------------------------------
# Trade proposal (model OUTPUT — proposal only, no authority)
# ---------------------------------------------------------------------------

@dataclass
class TradeProposal:
    symbol: str
    side: str
    qty: float
    price_constraint: dict          # {"type": "MARKET"|"LIMIT", "limit": float, "band": float}
    thesis: str
    confidence: float
    evidence_refs: List[str]
    strategy_id: str

    def state(self) -> dict:
        return {
            "symbol": self.symbol, "side": self.side, "qty": self.qty,
            "price_constraint": self.price_constraint, "thesis": self.thesis,
            "confidence": self.confidence, "evidence_refs": self.evidence_refs,
            "strategy_id": self.strategy_id,
        }


def proposal_hash(proposal: TradeProposal) -> str:
    return sha256(canonical_bytes(proposal.state()))


# ---------------------------------------------------------------------------
# Risk assessment (PURE function output)
# ---------------------------------------------------------------------------

@dataclass
class RiskAssessment:
    position_pct_after: float
    gross_exposure_pct: float
    cash_ok: bool
    asset_allowed: bool
    side_allowed: bool
    size_ok: bool
    price_ok: bool
    data_fresh: bool
    daily_loss_ok: bool
    frequency_ok: bool
    risk_score: float
    reason: str
    risk_assessment_hash: str = ""

    def state(self) -> dict:
        return {
            "position_pct_after": self.position_pct_after,
            "gross_exposure_pct": self.gross_exposure_pct,
            "cash_ok": self.cash_ok,
            "asset_allowed": self.asset_allowed,
            "side_allowed": self.side_allowed,
            "size_ok": self.size_ok,
            "price_ok": self.price_ok,
            "data_fresh": self.data_fresh,
            "daily_loss_ok": self.daily_loss_ok,
            "frequency_ok": self.frequency_ok,
            "risk_score": self.risk_score,
            "reason": self.reason,
        }


MAX_STALE_SEC = 60          # market data older than this is stale
POSITION_WARN_PCT = 0.15    # soft breach threshold for escalating to HUMAN


def _price_of_for(account: Account, market: MarketData):
    """Price lookup that returns the market's last price for the proposal symbol."""
    def _p(symbol: str) -> float:
        return market.last if symbol == market.symbol else 0.0
    return _p


def assess(proposal: TradeProposal, account: Account, market: MarketData,
           mandate: Mandate, now: int) -> RiskAssessment:
    """PURE deterministic risk evaluation. No model, no IO.

    Returns a RiskAssessment; the caller logs it (with canonical inputs) so a
    verifier can recompute. ``risk_assessment_hash`` binds the assessment to
    its exact inputs.
    """
    side = Side(proposal.side)
    price = float(market.last)
    if proposal.price_constraint.get("type") == OrderType.LIMIT.value:
        ref = float(proposal.price_constraint.get("limit", price))
        band = float(proposal.price_constraint.get("band", 0.0))
        price_ok = abs(ref - price) <= band * price if band > 0 else (ref == price)
    else:
        price_ok = True  # MARKET order fills at last; no price constraint to breach

    notional = float(proposal.qty) * price
    asset_allowed = proposal.symbol in mandate.allowed_assets
    side_allowed = proposal.side in mandate.allowed_sides

    price_of = _price_of_for(account, market)
    total_before = account.market_value(price_of)
    pos_after = account.position_value(proposal.symbol, price_of) + notional
    total_after = total_before + notional
    position_pct_after = (pos_after / total_after) if total_after > 0 else 0.0

    gross_exposure = total_before + notional
    gross_exposure_pct = (gross_exposure / total_after) if total_after > 0 else 0.0

    # cash / holdings sufficiency
    if side == Side.BUY:
        cash_ok = account.cash >= notional
    else:  # SELL (only if mandate allows) — cannot sell more than held
        held = account.positions.get(proposal.symbol)
        cash_ok = (held is not None) and (held.qty >= proposal.qty)

    size_ok = notional <= mandate.max_order_usd

    data_fresh = (now - market.ts) <= MAX_STALE_SEC

    # daily loss includes this trade's realized component
    trade_realized = 0.0
    if side == Side.SELL and proposal.symbol in account.positions:
        held = account.positions[proposal.symbol]
        trade_realized = (price - held.avg_price) * proposal.qty
    daily_pnl_after = account.daily_realized_pnl + trade_realized
    daily_loss_ok = daily_pnl_after >= -mandate.max_daily_loss_usd

    frequency_ok = account.orders_today < mandate.max_orders_per_day

    # risk score: 1.0 minus a penalty per soft breach
    soft = 0
    if position_pct_after > POSITION_WARN_PCT:
        soft += 1
    if not asset_allowed:
        soft += 1
    risk_score = round(max(0.0, min(1.0, 1.0 - 0.15 * soft)), 6)

    reasons = []
    if not asset_allowed:
        reasons.append("asset-not-allowed")
    if not side_allowed:
        reasons.append("side-not-allowed")
    if not cash_ok:
        reasons.append("insufficient-cash-or-holdings")
    if not size_ok:
        reasons.append("order-too-large")
    if not price_ok:
        reasons.append("price-out-of-band")
    if not data_fresh:
        reasons.append("stale-market-data")
    if not daily_loss_ok:
        reasons.append("daily-loss-cap")
    if not frequency_ok:
        reasons.append("order-frequency-cap")
    if position_pct_after > POSITION_WARN_PCT:
        reasons.append("position-pct-warning")

    ra = RiskAssessment(
        position_pct_after=round(position_pct_after, 6),
        gross_exposure_pct=round(gross_exposure_pct, 6),
        cash_ok=cash_ok, asset_allowed=asset_allowed, side_allowed=side_allowed,
        size_ok=size_ok, price_ok=price_ok, data_fresh=data_fresh,
        daily_loss_ok=daily_loss_ok, frequency_ok=frequency_ok,
        risk_score=risk_score,
        reason=";".join(reasons) if reasons else "within-limits",
    )
    ra.risk_assessment_hash = sha256(canonical_bytes(ra.state()))
    return ra


# ---------------------------------------------------------------------------
# Authorization disposition (mirrors incident.required_authorization)
# ---------------------------------------------------------------------------

def required_trade_authorization(
    risk: RiskAssessment,
    consensus: Optional[str] = None,
) -> Disposition:
    """PURE policy mapping risk -> AUTO / HUMAN / BLOCKED.

    Consensus is ADVISORY ONLY (Round 4 lock): it may only ESCALATE
    (AUTO -> HUMAN -> BLOCKED), never de-escalate. Two models agreeing can
    never turn a policy violation into an authorized action.
    """
    # Hard breaches always BLOCK (fail-closed).
    if not (risk.asset_allowed and risk.side_allowed and risk.cash_ok
            and risk.size_ok and risk.price_ok and risk.data_fresh
            and risk.daily_loss_ok and risk.frequency_ok):
        return Disposition.BLOCKED

    # Advisory consensus escalation (never rescues a hard breach above).
    if consensus == "severe":
        return Disposition.BLOCKED
    if consensus == "weak":
        return Disposition.HUMAN

    # Soft breach (position concentration warning) escalates to HUMAN.
    if risk.position_pct_after > POSITION_WARN_PCT:
        return Disposition.HUMAN

    return Disposition.AUTO


# ---------------------------------------------------------------------------
# Content-addressing for the trade transition (mirrors incident.bind_artifact)
# ---------------------------------------------------------------------------

def bind_trade(account_id: str, proposal: TradeProposal,
               portfolio_pre_hash: str, market_hash: str,
               risk_hash: str) -> str:
    """Content-address the exact consequential trade transition for approval
    binding (so a human signature binds to the precise proposal + evaluated
    state, not vague text)."""
    return sha256(canonical_bytes({
        "account_id": account_id,
        "proposal_hash": proposal_hash(proposal),
        "portfolio_pre_hash": portfolio_pre_hash,
        "market_hash": market_hash,
        "risk_assessment_hash": risk_hash,
    }))
