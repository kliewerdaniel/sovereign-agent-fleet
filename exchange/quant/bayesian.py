"""Bayesian belief updating for P_model(Y=1) (Q3, Layer-1 evidence).

Q3 part 1: a *conjugate* Beta-Bernoulli belief over the binary YES/NO outcome.

The Brain emits a point probability (``ctx.model_p_yes``). That is a single soft
observation, not a realized outcome. We maintain a proper Bayesian belief about
the *true* base rate P_model(Y=1) that:

    * starts from an explicit prior (default uniform Beta(1,1)),
    * absorbs a soft point estimate as pseudo-evidence (weight = pseudo-counts),
    * absorbs hard realized outcomes (Kalshi settlements) as exact Bernoulli draws,
    * reports a posterior mean + credible interval + evidence strength, and
    * is fully deterministic + hashable (a verifier can replay it).

Why Beta-Bernoulli (not a Gaussian/particle filter): the outcome is binary
($0/$1 per contract), so Beta is the *conjugate* prior — the posterior is exact
and closed-form, needs no scipy/numpy, and stays reproducible bit-for-bit. This
is the temporal sibling of Q1's static ``ProbabilityEstimate``: Q1 snapshots one
belief; Q3 tracks how that belief *evolves* with evidence.

BOUNDARY (same wall as the rest of exchange/quant): imports ONLY
``fleet.crypto`` + intra-package modules. Never imports ``fleet.fin``,
``exchange.governance``, ``fleet.layers.*``, or ``fleet.cognition``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from fleet.crypto.foundation import canonical_bytes, sha256

# Probability bounds (open interval, like Q1).
_PROB_EPS = 1e-9
# 95% two-sided normal-approx z (erf^-1(0.95) ... 1.959963984540054).
_Z95 = 1.959963984540054


def _clamp_prob(p: float) -> float:
    if p <= 0.0:
        return _PROB_EPS
    if p >= 1.0:
        return 1.0 - _PROB_EPS
    return float(p)


@dataclass(frozen=True)
class BayesianBelief:
    """A Beta(alpha, beta) posterior over P_model(Y=1).

    ``prior_alpha``/``prior_beta`` record the prior this posterior was built on
    (so a verifier can reconstruct the update). ``alpha``/``beta`` are the
    posterior parameters. ``posterior_p_yes`` is the posterior mean.
    """

    exchange_id: int
    alpha: float
    beta: float
    prior_alpha: float = 1.0
    prior_beta: float = 1.0
    method: str = "beta_bernoulli"
    model_id: str = "unknown"
    ts: int = 0
    belief_hash: str = ""

    def __post_init__(self):
        object.__setattr__(self, "alpha", float(self.alpha))
        object.__setattr__(self, "beta", float(self.beta))
        object.__setattr__(self, "prior_alpha", float(self.prior_alpha))
        object.__setattr__(self, "prior_beta", float(self.prior_beta))
        if not self.belief_hash:
            object.__setattr__(self, "belief_hash", self.compute_hash())

    # -- posterior summaries -------------------------------------------------
    @property
    def posterior_p_yes(self) -> float:
        """Posterior mean = alpha / (alpha + beta)."""
        return _clamp_prob(self.alpha / (self.alpha + self.beta))

    @property
    def posterior_var(self) -> float:
        """Beta variance = alpha*beta / ((a+b)^2*(a+b+1))."""
        a, b = self.alpha, self.beta
        s = a + b
        return (a * b) / (s * s * (s + 1.0))

    @property
    def evidence_strength(self) -> float:
        """Total pseudo-count mass (alpha+beta) = how much evidence the belief rests on."""
        return self.alpha + self.beta

    @property
    def odds_ratio(self) -> float:
        return self.alpha / self.beta if self.beta > 0 else float("inf")

    @property
    def log_odds(self) -> float:
        import math

        if self.beta <= 0:
            return float("inf")
        return math.log(self.alpha / self.beta)

    def credible_interval(self, conf: float = 0.95) -> Tuple[float, float]:
        """Equal-tail credible interval (normal approximation of the Beta).

        Exact Beta quantiles need scipy; we use a deterministic normal approx
        (mean +- z*sigma) and clamp to the open (0,1) interval. Labeled `_approx`
        because it is an approximation, not a bound — sufficient for *advisory*
        evidence (M0: never an input to the gate).
        """
        mean = self.posterior_p_yes
        std = max(0.0, self.posterior_var) ** 0.5
        z = _Z95 if conf >= 0.95 else 1.6448536269514722  # 90% fallback
        lo = _clamp_prob(mean - z * std)
        hi = _clamp_prob(mean + z * std)
        return lo, hi

    # -- provenance ----------------------------------------------------------
    def state(self) -> dict:
        return {
            "exchange_id": self.exchange_id,
            "alpha": self.alpha,
            "beta": self.beta,
            "prior_alpha": self.prior_alpha,
            "prior_beta": self.prior_beta,
            "method": self.method,
            "model_id": self.model_id,
            "ts": self.ts,
        }

    def compute_hash(self) -> str:
        return sha256(canonical_bytes(self.state()))

    # -- update algebra (pure, return new frozen belief) ---------------------
    def update_outcome(self, outcome: int, *, ts: int = 0) -> "BayesianBelief":
        """Absorb one realized Bernoulli draw (outcome in {0,1}) exactly.

        Posterior: Beta(alpha + o, beta + (1 - o)). This is the exact conjugate
        update — no approximation.
        """
        if outcome not in (0, 1):
            raise ValueError("outcome must be 0 or 1")
        return BayesianBelief(
            exchange_id=self.exchange_id,
            alpha=self.alpha + outcome,
            beta=self.beta + (1 - outcome),
            prior_alpha=self.prior_alpha,
            prior_beta=self.prior_beta,
            method=self.method,
            model_id=self.model_id,
            ts=ts,
        )

    def update_point_estimate(self, p: float, weight: float = 1.0, *, ts: int = 0) -> "BayesianBelief":
        """Absorb a soft model probability as pseudo-evidence.

        A point estimate ``p`` is treated as ``weight`` pseudo-Bernoulli draws
        with mean ``p``: alpha += weight*p, beta += weight*(1-p). This lets a
        single Brain prediction move the belief proportionally to how much we
        trust it (weight), without fabricating hard outcomes.
        """
        pc = _clamp_prob(p)
        w = max(0.0, float(weight))
        return BayesianBelief(
            exchange_id=self.exchange_id,
            alpha=self.alpha + w * pc,
            beta=self.beta + w * (1.0 - pc),
            prior_alpha=self.prior_alpha,
            prior_beta=self.prior_beta,
            method=self.method,
            model_id=self.model_id,
            ts=ts,
        )


def prior_belief(
    exchange_id: int,
    *,
    prior_alpha: float = 1.0,
    prior_beta: float = 1.0,
    model_id: str = "unknown",
    ts: int = 0,
) -> BayesianBelief:
    """Uniform (or custom) prior belief before any evidence."""
    return BayesianBelief(
        exchange_id=exchange_id,
        alpha=prior_alpha,
        beta=prior_beta,
        prior_alpha=prior_alpha,
        prior_beta=prior_beta,
        method="beta_bernoulli",
        model_id=model_id,
        ts=ts,
    )


def update_belief(
    prior: BayesianBelief,
    model_p_yes: float,
    *,
    weight: float = 1.0,
    outcomes: Optional[list] = None,
    ts: int = 0,
) -> BayesianBelief:
    """Combine a prior belief with one soft model estimate (and optional hard outcomes).

    Order matters and is deterministic: the soft point estimate is folded first,
    then any realized outcomes in sequence. Returns the resulting posterior.
    """
    b = prior.update_point_estimate(model_p_yes, weight=weight, ts=ts)
    for o in (outcomes or []):
        b = b.update_outcome(int(o), ts=ts)
    return b


__all__ = [
    "BayesianBelief",
    "prior_belief",
    "update_belief",
]
