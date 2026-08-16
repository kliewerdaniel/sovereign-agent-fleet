"""Exchange governance wrap — risk-tiered authorization over the venue.

This is the sovereign control surface for the exchange: it decides whether an
order is AUTO-executed, requires a cryptographically-bound HUMAN approval, or is
BLOCKED. It mirrors the thesis of ``fleet.layers.incident`` (D26): *do not trust
the model; trust the execution protocol.* The decision is a PURE function of
risk axes — it executes nothing on its own.

Crucially, this module imports ``fleet`` as a **library** (the literal-rebuild
boundary): it reuses ``fleet.layers.incident.Authorization`` as the decision
vocabulary and ``fleet.layers.runtime.Approval`` / ``fleet.layers.approval`` for
the real Ed25519 human-approval binding. It does NOT reimplement crypto or
policy — only the exchange-specific risk matrix.

Risk axes for a trade (vs the incident matrix's verification/severity/blast):
    * size      -- contracts/qty; larger = higher risk
    * side      -- SELL of a large position can be higher-risk than BUY
    * venue     -- a NOT_LIVE (stub) venue is higher risk than a live one
    * intent    -- HALLUCINATION-class intel always BLOCKED (same as fleet)

The HUMAN tier produces an ``artifact_hash`` bound to the exact order so a human
signature cannot be rebound to a different order (same guarantee as D17).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

# Reuse fleet's decision vocabulary — we are a consumer, not a reimplementation.
from fleet.layers.incident import Authorization  # type: ignore
from fleet.crypto.foundation import AgentCert, canonical_bytes, sha256  # type: ignore


class TradeRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# size thresholds in contracts; tune per market
AUTO_MAX_QTY = 100
HUMAN_MAX_QTY = 1000


def classify_risk(qty: int, side: str, venue_live: bool) -> TradeRisk:
    """Map trade attributes to a risk tier.

    Larger size and non-live venues raise risk. A SELL is treated one notch
    higher than a BUY of the same size (realization/liquidation risk).
    """
    base = qty
    if side == "SELL":
        base = int(qty * 1.5)
    if not venue_live:
        base = int(base * 2)  # stub venue = execution uncertainty
    if base <= AUTO_MAX_QTY:
        return TradeRisk.LOW
    if base <= HUMAN_MAX_QTY:
        return TradeRisk.MEDIUM
    return TradeRisk.HIGH


def bind_order_artifact(
    client_order_id: str,
    exchange_id: int,
    side: str,
    qty: int,
    limit_cents: Optional[int],
    venue: str,
) -> str:
    """Content-address the exact order for approval binding (D17-style)."""
    return sha256(
        canonical_bytes(
            {
                "client_order_id": client_order_id,
                "exchange_id": exchange_id,
                "side": side,
                "qty": qty,
                "limit_cents": limit_cents,
                "venue": venue,
            }
        )
    )


@dataclass
class TradeDecision:
    authorization: Authorization
    risk: TradeRisk
    reason: str
    artifact_hash: str
    requires_approval: bool

    def to_dict(self) -> dict:
        return {
            "authorization": self.authorization.value,
            "risk": self.risk.value,
            "reason": self.reason,
            "artifact_hash": self.artifact_hash,
            "requires_approval": self.requires_approval,
        }


def decide_trade(
    client_order_id: str,
    exchange_id: int,
    side: str,
    qty: int,
    limit_cents: Optional[int],
    venue: str,
    venue_live: bool,
    intel: str = "VERIFIED",  # HALLUCINATION-class intel blocks by policy
) -> TradeDecision:
    """Pure risk-tiered authorization decision for a single order.

    Returns a :class:`TradeDecision`. AUTO orders may execute immediately; HUMAN
    orders must be approved via :func:`approve_trade` before execution; BLOCKED
    orders must never execute.
    """
    artifact = bind_order_artifact(client_order_id, exchange_id, side, qty, limit_cents, venue)

    # Evidence gate: a hallucinated/unbacked intent is never authorized.
    if intel == "HALLUCINATION":
        return TradeDecision(
            authorization=Authorization.BLOCKED,
            risk=TradeRisk.HIGH,
            reason="HALLUCINATION-class intel -> BLOCKED (unbacked claim)",
            artifact_hash=artifact,
            requires_approval=False,
        )

    risk = classify_risk(qty, side, venue_live)
    if risk == TradeRisk.LOW:
        return TradeDecision(
            authorization=Authorization.AUTO,
            risk=risk,
            reason=f"{side} {qty} on {'live' if venue_live else 'stub'} venue -> AUTO",
            artifact_hash=artifact,
            requires_approval=False,
        )
    # MEDIUM/HIGH -> human approval required
    return TradeDecision(
        authorization=Authorization.HUMAN,
        risk=risk,
        reason=f"{side} {qty} (risk {risk.value}) -> HUMAN approval required",
        artifact_hash=artifact,
        requires_approval=True,
    )


def approve_trade(
    human_cert: AgentCert,
    human_key,  # Ed25519PrivateKey
    client_order_id: str,
    exchange_id: int,
    side: str,
    qty: int,
    limit_cents: Optional[int],
    venue: str,
    capability: str = "exchange.trade_execute",
    reason: str = "human approved via sovereign control surface",
) -> dict:
    """Cryptographically bind a human approval to the exact order.

    Returns a signed approval record (dict) using fleet's ``Approval.sign`` so
    the signature and binding semantics are identical to the D17 path — the
    exchange reuses the fleet approval primitive rather than reimplementing it.
    """
    # imported lazily to keep the crypto binding close to where it is used
    from fleet.layers.runtime import Approval  # type: ignore

    artifact = bind_order_artifact(client_order_id, exchange_id, side, qty, limit_cents, venue)
    ts = int(time.time())
    rec = Approval.sign(
        human_cert=human_cert,
        human_key=human_key,
        agent_id="exchange-operator",
        action_id=client_order_id,
        capability=capability,
        artifact_hash=artifact,
        decision="approve",
        reason=reason,
        ts=ts,
    )
    return {
        "approval_id": rec.approval_id,
        "agent_id": rec.agent_id,
        "action_id": rec.action_id,
        "capability": rec.capability,
        "artifact_hash": rec.artifact_hash,
        "decision": rec.decision,
        "reason": rec.reason,
        "human_id": rec.human_id,
        "human_sig": rec.human_sig,
        "ts": rec.ts,
    }


def verify_trade_approval(
    record: dict,
    human_cert: AgentCert,
    client_order_id: str,
    capability: str = "exchange.trade_execute",
    exchange_id: int = 0,
    side: str = "",
    qty: int = 0,
    limit_cents: Optional[int] = None,
    venue: str = "",
) -> bool:
    """Fail-closed verification of a trade approval (rebinding impossible)."""
    from fleet.layers.approval import verify_approval  # type: ignore

    expected_artifact = bind_order_artifact(client_order_id, exchange_id, side, qty, limit_cents, venue)
    return verify_approval(
        record=record,
        human_cert=human_cert,
        action_id=client_order_id,
        capability=capability,
        artifact_hash=expected_artifact,
    )


__all__ = [
    "Authorization",
    "TradeRisk",
    "TradeDecision",
    "classify_risk",
    "bind_order_artifact",
    "decide_trade",
    "approve_trade",
    "verify_trade_approval",
]
