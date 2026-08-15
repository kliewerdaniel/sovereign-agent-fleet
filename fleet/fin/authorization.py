"""TradeAuthorization — the cryptographically bound authorization object.

Built by the Operator after the four governance gates clear. Signed by the
Operator key. In HUMAN tier, additionally bound to a human ApprovalRecord.

The ExchangeSim re-verifies this object at apply time (signature, identity
epoch, expiration, portfolio_pre_hash, order constraints) BEFORE mutating the
account. This is the financial analog of SimEnv's PROTECTED second-line defense.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from fleet.crypto.foundation import AgentCert, canonical_bytes, sha256
from fleet.fin.domain import Disposition


def ta_sign_body(ta: Dict[str, Any]) -> bytes:
    """Reconstruct the exact canonical body the Operator signs (excludes sig)."""
    body = {k: v for k, v in ta.items() if k not in ("signature",)}
    return canonical_bytes(body)


@dataclass
class TradeAuthorization:
    agent_id: str
    identity_epoch: int
    strategy_id: str
    account_id: str
    symbol: str
    side: str
    qty: float
    price_constraint: dict
    proposal_hash: str
    portfolio_pre_hash: str
    market_hash: str
    risk_assessment_hash: str
    policy_id: str
    disposition: str
    approval_id: Optional[str]
    nonce: str
    ts: int
    expiration: int
    order_hash: str
    signature: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "identity_epoch": self.identity_epoch,
            "strategy_id": self.strategy_id,
            "account_id": self.account_id,
            "symbol": self.symbol,
            "side": self.side,
            "qty": self.qty,
            "price_constraint": self.price_constraint,
            "proposal_hash": self.proposal_hash,
            "portfolio_pre_hash": self.portfolio_pre_hash,
            "market_hash": self.market_hash,
            "risk_assessment_hash": self.risk_assessment_hash,
            "policy_id": self.policy_id,
            "disposition": self.disposition,
            "approval_id": self.approval_id,
            "nonce": self.nonce,
            "ts": self.ts,
            "expiration": self.expiration,
            "order_hash": self.order_hash,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TradeAuthorization":
        # Deserialize from a known-good ledger record; values are guaranteed present.
        return cls(
            agent_id=str(d.get("agent_id")),
            identity_epoch=int(d.get("identity_epoch", 0)),
            strategy_id=str(d.get("strategy_id")),
            account_id=str(d.get("account_id")),
            symbol=str(d.get("symbol")),
            side=str(d.get("side")),
            qty=float(d.get("qty", 0.0)),
            price_constraint=dict(d.get("price_constraint") or {}),
            proposal_hash=str(d.get("proposal_hash")),
            portfolio_pre_hash=str(d.get("portfolio_pre_hash")),
            market_hash=str(d.get("market_hash")),
            risk_assessment_hash=str(d.get("risk_assessment_hash")),
            policy_id=str(d.get("policy_id")),
            disposition=str(d.get("disposition")),
            approval_id=(str(d.get("approval_id")) if d.get("approval_id") is not None else None),
            nonce=str(d.get("nonce")),
            ts=int(d.get("ts", 0)),
            expiration=int(d.get("expiration", 0)),
            order_hash=str(d.get("order_hash")),
            signature=str(d.get("signature", "")),
        )


MAX_ORDER_TTL_SEC = 300  # an authorization older than this at evaluation is stale


def build_trade_authorization(
    operator_cert: AgentCert,
    operator_key: Ed25519PrivateKey,
    strategy_id: str,
    account_id: str,
    symbol: str,
    side: str,
    qty: float,
    price_constraint: dict,
    proposal_hash: str,
    portfolio_pre_hash: str,
    market_hash: str,
    risk_assessment_hash: str,
    policy_id: str,
    disposition: Disposition,
    approval_id: Optional[str],
    nonce: str,
    ts: int,
) -> TradeAuthorization:
    """Construct + sign a TradeAuthorization. The signature binds every field
    except itself (signature exclusion mirrors Approval/Handoff convention).

    ``qty`` is normalized to float so the canonical signed body is byte-stable
    across the JSON store round-trip (int ``10`` vs ``10.0`` would otherwise
    break signature verification at audit time)."""
    qty = float(qty)  # normalize before hashing + signing for JSON-stable body
    order_hash = sha256(canonical_bytes({
        "account_id": account_id, "symbol": symbol, "side": side,
        "qty": qty, "price_constraint": price_constraint,
    }))
    raw = TradeAuthorization(
        agent_id=operator_cert.agent_id, identity_epoch=operator_cert.cert_seq,
        strategy_id=strategy_id, account_id=account_id, symbol=symbol, side=side,
        qty=qty, price_constraint=price_constraint, proposal_hash=proposal_hash,
        portfolio_pre_hash=portfolio_pre_hash, market_hash=market_hash,
        risk_assessment_hash=risk_assessment_hash, policy_id=policy_id,
        disposition=disposition.value if isinstance(disposition, Disposition) else disposition,
        approval_id=approval_id, nonce=nonce, ts=ts,
        expiration=ts + MAX_ORDER_TTL_SEC, order_hash=order_hash,
    )
    body = ta_sign_body(raw.to_dict())
    raw.signature = operator_key.sign(body).hex()
    return raw


def verify_trade_authorization(ta: TradeAuthorization, operator_cert: AgentCert,
                               now: int) -> bool:
    """Fail-closed verification of a TA against the live Operator cert.

    Checks, in order:
      1. disposition is a valid enum (BLOCKED never reaches here, but guard).
      2. operator signature verifies under the live cert's pubkey.
      3. the cert's identity_epoch matches the TA (no epoch drift).
      4. not expired (expiration > now).
      5. nonce is present (replay defense signal).
    """
    if ta.disposition == Disposition.BLOCKED.value:
        return False
    if not ta.signature:
        return False
    try:
        pub = serialization.load_pem_public_key(operator_cert.pubkey_pem.encode())
        if not isinstance(pub, Ed25519PublicKey):
            return False
        pub.verify(bytes.fromhex(ta.signature), ta_sign_body(ta.to_dict()))
    except (InvalidSignature, ValueError):
        return False
    if operator_cert.cert_seq != ta.identity_epoch:
        return False
    if now > ta.expiration:
        return False
    if not ta.nonce:
        return False
    return True
