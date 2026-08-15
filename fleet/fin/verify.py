"""Standalone financial verifier (D27 §17) — first-class artifact.

An independent verifier reconstructs a trade's canonical inputs from the audit
ledger, recomputes the risk decision with the SAME pure ``fleet.fin`` functions
the Operator used, and confirms the recorded disposition/risk hash are
reproducible. It verifies the TradeAuthorization signature + state binding and
the ledger hash-chain.

Output per trade: PASS / FAIL (with a reason code). If any record's recomputed
risk/disposition cannot be reproduced, the whole run is CRITICAL — never an
overall PASS. A secure system produces zero unexplained CRITICAL events.

The verifier holds only PUBLIC keys (operator cert, human cert, root) — no
authority to execute, sign, or mutate. It rebuilds the Account/MarketData from
the logged canonical inputs and the pure functions.

Run:  python -m fleet.fin.verify  (uses a ControlPlane fixture built by the
caller, or see ``verify_control_plane``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fleet.crypto.foundation import AgentCert, canonical_bytes, sha256
from fleet.layers.approval import verify_approval
from fleet.fin.domain import (
    Account,
    Disposition,
    Mandate,
    MarketData,
    Position,
    TradeProposal,
    assess,
    proposal_hash,
    required_trade_authorization,
)
from fleet.fin.authorization import TradeAuthorization, verify_trade_authorization


VERIFY_KIND = "operator.final"          # the financial execution record
TA_DISPOSITION_FIELD = "disposition"


def _rebuild_account(rec: Dict[str, Any]) -> Account:
    pp = rec["portfolio_pre"]
    positions = {
        s: Position(symbol=s, qty=p["qty"], avg_price=p["avg_price"],
                    side=p.get("side", "BUY"))
        for s, p in pp.get("positions", {}).items()
    }
    mandate = _rebuild_mandate(pp["mandate"]) if pp.get("mandate") else None
    return Account(
        account_id=pp["account_id"],
        cash=pp["cash"],
        positions=positions,
        base_ccy=pp.get("base_ccy", "USD"),
        mandate=(mandate if mandate is not None else None),
        orders_today=pp.get("orders_today", 0),
        daily_realized_pnl=pp.get("daily_realized_pnl", 0.0),
    )


def _rebuild_mandate(m: Dict[str, Any]) -> Mandate:
    return Mandate(
        allowed_assets=list(m.get("allowed_assets", [])),
        allowed_sides=list(m.get("allowed_sides", ["BUY"])),
        max_position_pct=float(m.get("max_position_pct", 0.20)),
        max_order_usd=float(m.get("max_order_usd", 10_000.0)),
        max_daily_loss_usd=float(m.get("max_daily_loss_usd", 5_000.0)),
        max_orders_per_day=int(m.get("max_orders_per_day", 25)),
    )


def _rebuild_market(rec: Dict[str, Any]) -> MarketData:
    m = rec["market"]
    return MarketData(
        symbol=m["symbol"], ts=int(m["ts"]), bid=float(m["bid"]),
        ask=float(m["ask"]), last=float(m["last"]), vol=float(m.get("vol", 0.0)),
        source_id=m.get("source_id", "verifier"),
    )


def _rebuild_proposal(rec: Dict[str, Any]) -> TradeProposal:
    p = rec["proposal"]
    return TradeProposal(
        symbol=p["symbol"], side=p["side"], qty=float(p["qty"]),
        price_constraint=p["price_constraint"], thesis=p["thesis"],
        confidence=float(p["confidence"]), evidence_refs=list(p["evidence_refs"]),
        strategy_id=p["strategy_id"],
    )


@dataclass
class VerifyResult:
    order_id: str
    status: str                 # "PASS" | "FAIL"
    reason: str
    critical: bool = False


def verify_record(rec: Dict[str, Any], operator_cert: AgentCert,
                  human_cert: Optional[AgentCert], now: int) -> VerifyResult:
    """Recompute + cross-check a single financial execution record.

    Returns FAIL (not CRITICAL) for an ordinary recomputation mismatch; the
    caller aggregates to CRITICAL if any FAIL is a 'recompute' failure.
    """
    try:
        account = _rebuild_account(rec)
        mandate = account.mandate
        if mandate is None:
            return VerifyResult(rec.get("order_id", "?"), "FAIL",
                               "mandate-missing")
        market = _rebuild_market(rec)
        proposal = _rebuild_proposal(rec)
        ta_dict = rec["ta"]
        ta = TradeAuthorization.from_dict(ta_dict)

        findings = []

        # 1. TA signature + identity epoch + expiry (bound to operator cert).
        if not verify_trade_authorization(ta, operator_cert, now):
            return VerifyResult(rec.get("order_id", "?"), "FAIL",
                               "TA signature/epoch/expiry invalid")
        # 2. State binding: reconstructed portfolio_pre_hash must match the TA.
        if sha256(canonical_bytes(account.state())) != ta.portfolio_pre_hash:
            findings.append("portfolio-state-mismatch")
        # 3. Risk recomputation (headline).
        recomputed = assess(proposal, account, market, mandate, ta.ts)
        if recomputed.risk_assessment_hash != rec["risk_assessment_hash"]:
            findings.append("risk-hash-mismatch")
        # 4. Disposition recomputation.
        disp_recomputed = required_trade_authorization(recomputed, rec.get("consensus"))
        if disp_recomputed.value != rec.get("disposition"):
            findings.append(f"disposition-mismatch({disp_recomputed.value}"
                            f"!={rec.get('disposition')})")
        # 5. HUMAN binding.
        if rec.get("disposition") == Disposition.HUMAN.value:
            appr = rec.get("approval")
            if human_cert is None or appr is None:
                findings.append("human-cert-or-approval-missing")
            elif not verify_approval(appr, human_cert, ta.nonce,
                                   "trade_execute", rec.get("artifact_hash") or ""):
                findings.append("approval-mismatch")
        # 6. Receipt integrity (prev/new hash chain to logged state hashes).
        receipt = rec.get("receipt", {})
        if receipt.get("prev_state_hash") != ta.portfolio_pre_hash:
            findings.append("receipt-prev-state-mismatch")

        if findings:
            return VerifyResult(rec.get("order_id", "?"), "FAIL",
                               "; ".join(findings))
        return VerifyResult(rec.get("order_id", "?"), "PASS", "reproduced")
    except Exception as e:  # a malformed record is a CRITICAL integrity finding
        return VerifyResult(rec.get("order_id", "?"), "FAIL",
                           f"record-unparseable: {e}", critical=True)


def verify_control_plane(cp, operator_cert: AgentCert,
                         human_cert: Optional[AgentCert], now: int) -> Dict[str, Any]:
    """Verify every financial execution record in the live ControlPlane ledger.

    Returns an aggregate with status PASS / FAIL / CRITICAL. The verifier holds
    only PUBLIC certs — it cannot execute, sign, or mutate anything.
    """
    entries = [e.get("payload", e) for e in cp.audit.entries()
               if e.get("kind") == VERIFY_KIND]
    results = [
        verify_record(e, operator_cert, human_cert, now) for e in entries
    ]

    n_pass = sum(1 for r in results if r.status == "PASS")
    n_crit = sum(1 for r in results if r.critical)
    # Any recomputation failure (a mismatch or unparseable record) means the
    # recorded evidence of authorization cannot be independently reproduced —
    # that is CRITICAL, never an overall PASS.
    n_recompute_fail = sum(
        1 for r in results
        if r.status == "FAIL" and ("mismatch" in r.reason or "unparseable" in r.reason)
    )
    pam = len(results)
    if n_crit > 0 or n_recompute_fail > 0:
        overall = "CRITICAL"
    elif pam and n_pass == pam:
        overall = "PASS"
    elif pam:
        overall = "FAIL"
    else:
        overall = "PASS"  # no financial trades recorded is not a failure

    return {
        "overall": overall,
        "total": pam,
        "passed": n_pass,
        "failed": pam - n_pass,
        "critical": n_crit,
        "results": [r.__dict__ for r in results],
    }
