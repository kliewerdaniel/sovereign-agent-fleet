"""fleet/fin — financial agent reference workload (D27).

Second consequential domain for the same local-first authorization substrate.
Demonstrates: the domain changes, the authority protocol does not.
"""
from fleet.fin.domain import (
    Account,
    Disposition,
    Mandate,
    MarketData,
    Position,
    RiskAssessment,
    Side,
    TradeProposal,
    account_state_hash,
    assess,
    bind_trade,
    proposal_hash,
    required_trade_authorization,
)
from fleet.fin.authorization import (
    TradeAuthorization,
    build_trade_authorization,
    verify_trade_authorization,
)
from fleet.fin.exchange_sim import ExchangeSim, ExecutionReceipt, ApplyResult

__all__ = [
    "Account", "Disposition", "Mandate", "MarketData", "Position",
    "RiskAssessment", "Side", "TradeProposal", "account_state_hash",
    "assess", "bind_trade", "proposal_hash", "required_trade_authorization",
    "TradeAuthorization", "build_trade_authorization", "verify_trade_authorization",
    "ExchangeSim", "ExecutionReceipt", "ApplyResult",
]
