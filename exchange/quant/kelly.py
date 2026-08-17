"""Q5: Kelly sizing proposal (advisory position sizing).

Produces a *proposed* position size from a probability / edge estimate. The
output is ADVISORY ONLY: it is bound to the trade proposal as a suggested `qty`;
the existing ``RiskLayer`` / ``decide_trade`` in ``exchange/governance.py`` and
``fleet/fin/domain.py`` independently re-check it against ``max_order_usd``,
position and size limits and may downsize or block. M0 preserved: the
authorization outcome is identical with or without this proposal attached.

Deterministic, hashable Layer-1 evidence. Imports ONLY ``fleet.crypto``
(foundation) plus the sibling ``probability`` module in this same package.
No authority-layer imports (``fleet.fin``/``governance``/``incident``/...).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

from fleet.crypto.foundation import AgentCert, canonical_bytes, sha256

from exchange.quant.probability import ProbabilityEstimate


@dataclass(frozen=True)
class KellyProposal:
    """A deterministic, hashable Kelly size proposal (Layer-1 evidence).

    ``p_win`` is the probability that the *bought side* wins (caller flips for
    NO). ``price`` is the contract price in dollars, (0, 1). The proposal is
    advisory; it never executes or authorizes anything.
    """

    p_win: float
    price: float
    available_usd: float
    side: str = "YES"  # "YES" or "NO"
    kelly_fraction_cap: float = 0.5  # 1.0 = full Kelly, 0.5 = half-Kelly
    max_position_fraction: float = 0.20  # supplied by Mandate.max_position_pct at call time
    basis: str = "kelly"
    # computed (filled in __post_init__)
    raw_fraction: float = 0.0
    capped_fraction: float = 0.0
    proposed_usd: float = 0.0
    proposed_qty: int = 0
    edge_bps: float = 0.0
    recommendation: str = "NO_BET"
    sizing_hash: str = ""

    def __post_init__(self) -> None:
        p = float(self.p_win)
        c = float(self.price)
        # guard: invalid inputs -> explicit no-bet, still hashable
        if not (0.0 < c < 1.0) or not (0.0 <= p <= 1.0) or self.available_usd <= 0:
            object.__setattr__(self, "sizing_hash", sha256(canonical_bytes(self.state())))
            return
        # Kelly fraction for the bought side:
        #   f* = p_win - (1 - p_win) * c / (1 - c)
        f_star = p - (1.0 - p) * c / (1.0 - c)
        f_capped = f_star * self.kelly_fraction_cap
        f_clamped = max(0.0, min(f_capped, self.max_position_fraction))
        proposed_usd = round(self.available_usd * f_clamped, 2)  # cents, no float dust
        proposed_qty = int(math.floor(round(proposed_usd / c, 9))) if c > 0 else 0
        edge_bps = (p - c) * 10000.0
        rec = "BET" if f_clamped > 0 else "NO_BET"
        object.__setattr__(self, "raw_fraction", f_star)
        object.__setattr__(self, "capped_fraction", f_clamped)
        object.__setattr__(self, "proposed_usd", proposed_usd)
        object.__setattr__(self, "proposed_qty", proposed_qty)
        object.__setattr__(self, "edge_bps", edge_bps)
        object.__setattr__(self, "recommendation", rec)
        object.__setattr__(self, "sizing_hash", sha256(canonical_bytes(self.state())))

    def state(self) -> dict:
        """Deterministic serialization (excludes the hash itself)."""
        return {
            "p_win": self.p_win,
            "price": self.price,
            "available_usd": self.available_usd,
            "side": self.side,
            "kelly_fraction_cap": self.kelly_fraction_cap,
            "max_position_fraction": self.max_position_fraction,
            "basis": self.basis,
            "raw_fraction": self.raw_fraction,
            "capped_fraction": self.capped_fraction,
            "proposed_usd": self.proposed_usd,
            "proposed_qty": self.proposed_qty,
            "edge_bps": self.edge_bps,
            "recommendation": self.recommendation,
        }

    def compute_hash(self) -> str:
        return self.sizing_hash


def propose_kelly_from_estimate(
    est: ProbabilityEstimate,
    price: float,
    available_usd: float,
    side: str = "YES",
    kelly_fraction_cap: float = 0.5,
    max_position_fraction: float = 0.20,
) -> KellyProposal:
    """Build a Kelly proposal straight from a Q1 ``ProbabilityEstimate``.

    ``side="YES"`` uses ``est.agent_prob`` directly; ``side="NO"`` flips it.
    """
    p_win = est.p_yes if side == "YES" else (1.0 - est.p_yes)
    return KellyProposal(
        p_win=p_win,
        price=price,
        available_usd=available_usd,
        side=side,
        kelly_fraction_cap=kelly_fraction_cap,
        max_position_fraction=max_position_fraction,
    )


def build_kelly_evidence(cert: AgentCert, key, kelly: KellyProposal, proposal_hash: str = "") -> dict:
    """Signed envelope binding the Kelly proposal (mirrors build_quant_evidence)."""
    body = {
        "proposal_hash": proposal_hash,
        "sizing_hash": kelly.sizing_hash,
        "p_win": kelly.p_win,
        "price": kelly.price,
        "side": kelly.side,
        "capped_fraction": kelly.capped_fraction,
        "proposed_qty": kelly.proposed_qty,
        "ts": int(time.time()),
    }
    sig = key.sign(sha256(canonical_bytes(body)).encode())
    return {
        "body": body,
        "signature": sig.hex(),
        "signer": cert.agent_id,
        "cert": cert.to_dict(),
    }


def verify_kelly_evidence(envelope: dict, pubkey) -> bool:
    """Verify the signature over a Kelly evidence envelope."""
    try:
        body = envelope["body"]
        pubkey.verify(bytes.fromhex(envelope["signature"]), sha256(canonical_bytes(body)).encode())
        return True
    except Exception:
        return False


__all__ = [
    "KellyProposal",
    "propose_kelly_from_estimate",
    "build_kelly_evidence",
    "verify_kelly_evidence",
]
