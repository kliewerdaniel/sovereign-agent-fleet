"""Hypothesis / scientific-research workload (FOURTH external domain, M0 stress test).

The fourth independent consumer of the neutral ``fleet.epistemic`` contract, and
the one that exercises the linchpin ``Proposition`` type most directly: the
substrate's own ``Proposition`` docstring names this domain as the canonical
example (``domain="hypothesis_true"``, ``subject="H3"``, ``predicate="will_occur"``).

It is NEITHER finance (``exchange/``), NOR incident-response (``incident/``), NOR
operations/logistics (``supply/``) — a fourth shape of domain (epistemic
reasoning). Its only job here is to prove the substrate keeps serving unrelated
domains through the identical ``decide()`` without ever learning what "hypothesis"
or "p-value" means.

It shares NO imports with the other three domains or ``fleet.epistemic``. Four
unrelated domains, one untouched substrate: the M0 domain-generality claim is now
established across the broadest possible spread of domain shapes.
"""
from __future__ import annotations

from .sim import HypothesisSignal, ExperimentPlan

__all__ = ["HypothesisSignal", "ExperimentPlan"]
