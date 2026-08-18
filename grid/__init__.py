"""Grid / energy demand-response workload (SIXTH external domain, M0 proof).

The sixth independent consumer of the neutral ``fleet.epistemic`` contract, and a
deliberately different *shape* from the first five:

  * ``exchange/``  finance (prediction-market orders)
  * ``incident/``  security (host remediation)
  * ``supply/``    operations/logistics (reorder)
  * ``hypothesis/`` research (experiment run)
  * ``mirror/``    agent self-observability (self-tune)
  * ``grid/``      energy / demand-response (load balancing)  <-- this package

``grid`` is the only one of the six that describes a *continuous physical-control*
problem: balancing supply against demand on a power grid, with a safety-critical
curtailment action. The substrate never learns what a megawatt, a load factor, or
a demand-response event is — it sees only a neutral Proposition, opaque Evidence,
an advisory Recommendation, and an AuthorizationRequest scoped to ``grid.balance``.

It shares NO imports with the other five domains or ``fleet.epistemic``. Six
unrelated domains, one untouched substrate: the M0 domain-generality claim now
holds across the widest spread of domain shapes yet.
"""
from __future__ import annotations

from .sim import GridSignal, GridPlan

__all__ = ["GridSignal", "GridPlan"]
