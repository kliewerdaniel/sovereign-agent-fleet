"""Q6: Quant orchestration — the probability/edge intelligence pipeline.

This module is the *intelligence* layer: it takes a market quote + a model
probability + (optionally) a streaming analyzer's anomaly state, and produces a
single signed :class:`QuantEvidence` envelope plus a :class:`KellyProposal`.

It is the bridge between the quant building blocks (Q1/Q2/Q5) and the authority
surface (``exchange/governance.decide_trade``), but it is **decoupled** from
governance: it never imports ``exchange.governance`` or ``fleet.fin``. It emits
evidence; the caller binds ``QuantEvidence.proposal_hash`` to whatever trade
record it decides on. M0 preserved: a ``QuantDecision`` carries no verdict — only
advisory ``suggested_qty`` and the signed evidence; ``decide_trade``'s outcome is
identical whether or not this ran.

Determinism: ``QuantContext`` records the exact inputs used; replaying the same
context reproduces the identical hashes (I15-style reproducibility), so a
verifier can reconstruct the evidence without trusting the producer.

Import wall (enforced by ``test_boundary_quant.py``): only ``fleet.crypto`` and
intra-package ``exchange.quant.*`` are imported here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from fleet.crypto.foundation import AgentCert

from exchange.quant.calibration import CalibrationRecord
from exchange.quant.expected_value import ExpectedValue, expected_value
from exchange.quant.evidence import (
    QuantEvidence,
    bind_quant_log,
    build_quant_evidence,
    verify_quant_evidence,
)
from exchange.quant.kelly import KellyProposal, propose_kelly_from_estimate
from exchange.quant.probability import (
    EdgeEstimate,
    MarketProbability,
    ProbabilityEstimate,
    estimate_edge,
)
from exchange.quant.streaming import StreamAnalyzer
from exchange.quant.bayesian import BayesianBelief, prior_belief as _uniform_prior_belief, update_belief
from exchange.quant.regime import RegimeDetector, RegimeState, detect_regime
from exchange.quant.eventgraph import EventGraph, info_gain_from_series


@dataclass(frozen=True)
class QuantContext:
    """The exact inputs to one quant evaluation (deterministic + replayable)."""

    exchange_id: int
    model_p_yes: float
    bid_cents: int
    ask_cents: int
    last_cents: Optional[int] = None
    side: str = "BUY_YES"
    available_usd: float = 1000.0
    kelly_fraction_cap: float = 0.5
    max_position_fraction: float = 0.20
    fee_per_contract_cents: float = 0.07
    half_spread_cents: float = 1.0
    execution_prob: float = 1.0
    market_live: bool = False
    ticker: Optional[str] = None
    model_id: str = "unknown"
    method: str = "unspecified"
    ts: int = 0
    # --- Q3 (Bayesian + regime) advisory inputs ---
    bayes_prior_alpha: float = 1.0
    bayes_prior_beta: float = 1.0
    bayes_weight: float = 1.0       # pseudo-count weight for the soft model estimate
    bayes_outcomes: tuple = ()      # realized Bernoulli draws (0/1) since last eval
    regime_observations: tuple = ()  # recent mid-prob stream for regime detection
    event_p_yes_series: tuple = ()   # Q4: P(YES) snapshots to fold into an event graph

    def to_dict(self) -> dict:
        return {
            "exchange_id": self.exchange_id,
            "model_p_yes": self.model_p_yes,
            "bid_cents": self.bid_cents,
            "ask_cents": self.ask_cents,
            "last_cents": self.last_cents,
            "side": self.side,
            "available_usd": self.available_usd,
            "kelly_fraction_cap": self.kelly_fraction_cap,
            "max_position_fraction": self.max_position_fraction,
            "fee_per_contract_cents": self.fee_per_contract_cents,
            "half_spread_cents": self.half_spread_cents,
            "execution_prob": self.execution_prob,
            "market_live": self.market_live,
            "ticker": self.ticker,
            "model_id": self.model_id,
            "method": self.method,
            "ts": self.ts,
            "bayes_prior_alpha": self.bayes_prior_alpha,
            "bayes_prior_beta": self.bayes_prior_beta,
            "bayes_weight": self.bayes_weight,
            "bayes_outcomes": list(self.bayes_outcomes),
            "regime_observations": list(self.regime_observations),
            "event_p_yes_series": list(self.event_p_yes_series),
        }


def _most_informative_id(graph: "EventGraph") -> Optional[str]:
    """None-safe accessor for the most-informative event id (M0-safe helper)."""
    top = graph.most_informative_event()
    return top.event_id if top is not None else None


@dataclass
class QuantDecision:
    """The full advisory output of one quant evaluation.

    Pure data. No authorization verdict. ``suggested_qty`` is the Kelly proposal;
    ``evidence`` is the signed, hashable envelope.
    """

    context: QuantContext
    probability: ProbabilityEstimate
    market: MarketProbability
    edge: EdgeEstimate
    ev: ExpectedValue
    kelly: KellyProposal
    belief: "BayesianBelief"
    regime: "RegimeState"
    graph: "EventGraph"
    evidence: QuantEvidence
    suggested_qty: int = 0

    def to_dict(self) -> dict:
        return {
            "context": self.context.to_dict(),
            "probability_hash": self.probability.p_hash,
            "market_prob_hash": self.market.mp_hash,
            "edge_hash": self.edge.edge_hash,
            "ev_hash": self.ev.ev_hash,
            "kelly": {
                "p_win": self.kelly.p_win,
                "price": self.kelly.price,
                "capped_fraction": self.kelly.capped_fraction,
                "proposed_qty": self.kelly.proposed_qty,
                "recommendation": self.kelly.recommendation,
            },
            "belief": {
                "posterior_p_yes": self.belief.posterior_p_yes,
                "alpha": self.belief.alpha,
                "beta": self.belief.beta,
                "evidence_strength": self.belief.evidence_strength,
                "ci_lo": self.belief.credible_interval()[0],
                "ci_hi": self.belief.credible_interval()[1],
                "belief_hash": self.belief.belief_hash,
            },
            "regime": {
                "regime": self.regime.regime,
                "confidence": self.regime.confidence,
                "drift": self.regime.drift,
                "regime_hash": self.regime.regime_hash,
            },
            "event_graph": {
                "event_count": self.graph.event_count(),
                "total_information_gain_bits": self.graph.total_information_gain(),
                "final_entropy_bits": self.graph.cumulative_entropy(),
                "most_informative_event": _most_informative_id(self.graph),
                "graph_hash": self.graph.compute_hash(),
            },
            "suggested_qty": self.kelly.proposed_qty,
            "evidence_proposal_hash": self.evidence.proposal_hash,
            "evidence_signature": self.evidence.signature,
        }


def evaluate_quant(
    ctx: QuantContext,
    producer_cert: AgentCert,
    producer_key,
    *,
    analyzer: Optional[StreamAnalyzer] = None,
    proposal_hash: str = "",
    prior_belief: Optional["BayesianBelief"] = None,
) -> QuantDecision:
    """Run the full probability/edge/EV/Kelly pipeline for one context.

    Args:
        ctx: the deterministic input snapshot.
        producer_cert / producer_key: the quant producer's Ed25519 identity
            (signs the evidence envelope).
        analyzer: optional ``StreamAnalyzer`` already subscribed to the bus;
            its current anomaly state is folded into the evidence binding.
        proposal_hash: the sha256(canonical(TradeProposal)) this evidence
            informs. Empty is allowed (evaluate-then-bind), but production must
            bind it before the envelope is meaningful.
        prior_belief: optional learned ``BayesianBelief`` (D30) used as the base
            belief instead of a flat uniform prior. Advisory only — never changes
            the verdict (M0).

    Returns a :class:`QuantDecision` carrying the signed evidence + suggested qty.
    """
    prob = ProbabilityEstimate(
        exchange_id=ctx.exchange_id,
        p_yes=ctx.model_p_yes,
        model_id=ctx.model_id,
        method=ctx.method,
        ts=ctx.ts,
    )
    market = MarketProbability(
        exchange_id=ctx.exchange_id,
        mid_prob=(ctx.bid_cents + ctx.ask_cents) / 200.0,
        bid_prob=ctx.bid_cents / 100.0,
        ask_prob=ctx.ask_cents / 100.0,
        last_prob=(ctx.last_cents / 100.0) if ctx.last_cents is not None else None,
        venue="kalshi",
        live=ctx.market_live,
        ticker=ctx.ticker,
        ts=ctx.ts,
    )
    edge = estimate_edge(prob, market, basis="mid", ts=ctx.ts)
    ev = expected_value(
        edge,
        side=ctx.side,
        fill_price_cents=ctx.ask_cents if ctx.side == "BUY_YES" else ctx.bid_cents,
        fee_per_contract_cents=ctx.fee_per_contract_cents,
        half_spread_cents=ctx.half_spread_cents,
        execution_prob=ctx.execution_prob,
        model_id=ctx.model_id,
        ts=ctx.ts,
    )
    kelly = propose_kelly_from_estimate(
        prob,
        price=ev.fill_price_cents / 100.0,
        available_usd=ctx.available_usd,
        side="YES" if ctx.side == "BUY_YES" else "NO",
        kelly_fraction_cap=ctx.kelly_fraction_cap,
        max_position_fraction=ctx.max_position_fraction,
    )
    # Q3: Bayesian belief update (soft model estimate + optional realized outcomes)
    if prior_belief is not None:
        prior = prior_belief  # D30: learned base belief (advisory)
    else:
        prior = _uniform_prior_belief(
            ctx.exchange_id, prior_alpha=ctx.bayes_prior_alpha,
            prior_beta=ctx.bayes_prior_beta, model_id=ctx.model_id, ts=ctx.ts,
        )
    belief = update_belief(
        prior, ctx.model_p_yes, weight=ctx.bayes_weight,
        outcomes=list(ctx.bayes_outcomes), ts=ctx.ts,
    )
    # Q3: regime detection over the recent mid-prob stream
    if ctx.regime_observations:
        regime = detect_regime(
            list(ctx.regime_observations), exchange_id=ctx.exchange_id, ts=ctx.ts,
        )
    else:
        regime = RegimeDetector(exchange_id=ctx.exchange_id).handle(
            (ctx.bid_cents + ctx.ask_cents) / 200.0, ts=ctx.ts,
        )
    # Optional streaming/anomaly binding (fold analyzer hash into the envelope log)
    analyzer_hash = analyzer.compute_hash() if analyzer is not None else ""
    evidence = build_quant_evidence(
        producer_cert,
        producer_key,
        proposal_hash=proposal_hash,
        exchange_id=ctx.exchange_id,
        probability_hash=prob.p_hash,
        market_prob_hash=market.mp_hash,
        edge_hash=edge.edge_hash,
        ev_hash=ev.ev_hash,
        model_id=ctx.model_id,
        method=ctx.method,
        ts=ctx.ts,
        calibration_hash=belief.belief_hash,  # bind the posterior into the envelope
    )
    # Q4: temporal event graph + information gain over a P(YES) trajectory.
    # Pure advisory: a derived metric of how much belief movement occurred.
    if ctx.event_p_yes_series:
        graph = info_gain_from_series(
            ctx.exchange_id, list(ctx.event_p_yes_series),
            ticker=ctx.ticker or "DEFAULT", model_id=ctx.model_id,
        )
    else:
        graph = EventGraph(ctx.exchange_id, model_id=ctx.model_id)
    # Close the loop: bind envelope + constituent hashes into one audit log hash.
    _audit_log_hash = bind_quant_log(
        evidence,
        p_hash=prob.p_hash,
        mp_hash=market.mp_hash,
        edge_hash=edge.edge_hash,
        ev_hash=ev.ev_hash,
    )
    return QuantDecision(
        context=ctx,
        probability=prob,
        market=market,
        edge=edge,
        ev=ev,
        kelly=kelly,
        belief=belief,
        regime=regime,
        graph=graph,
        evidence=evidence,
        suggested_qty=kelly.proposed_qty,
    )


def determinism_check(ctx: QuantContext, cert: AgentCert, key) -> bool:
    """I15: replaying the same context yields byte-identical evidence hashes."""
    a = evaluate_quant(ctx, cert, key)
    b = evaluate_quant(ctx, cert, key)
    return (
        a.evidence.signature == b.evidence.signature
        and a.kelly.sizing_hash == b.kelly.sizing_hash
        and a.ev.ev_hash == b.ev.ev_hash
    )


__all__ = [
    "QuantContext",
    "QuantDecision",
    "evaluate_quant",
    "determinism_check",
    "CalibrationRecord",
]
