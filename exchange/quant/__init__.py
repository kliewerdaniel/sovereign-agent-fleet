"""Quantitative probability / edge intelligence layer (exchange/quant).

This package is Layer-1 *evidence* for the Sovereign Exchange: it produces
typed, hashable, signed probability / edge / expected-value / calibration
records. It is **never** an authority path.

HARD BOUNDARY (enforced by ``exchange/tests/test_boundary_quant.py``):
    ``exchange/quant`` may import ONLY:
        * ``fleet.crypto``                  (sign / verify / audit primitives)
        * ``exchange.core.instrument``      (read instrument model)
        * ``exchange.feeds``                (read Quote / PriceFeed)
        * ``exchange.core.events``          (read market events, Q2+)
        * ``cryptography``                  (Ed25519 primitive, same lib fleet.crypto uses)
    It must NEVER import ``fleet.fin`` (RiskLayer / TradeAuthorization /
    ExchangeSim), ``exchange.governance`` (decide_trade), ``fleet.layers.*``
    (gateway/policy/runtime/incident/approval/registry), or
    ``fleet.cognition``. Doing so is a build failure.

Rationale: the exchange governance / risk engine already decides authorization.
If the quant layer could import them it could *become* authority, breaking the
meta-invariant M0 ("no security invariant may depend on model/quant behavior").
The import wall makes that structural, not conventional — mirroring
``fleet/tests/test_boundary.py``.

The quant outputs are carried as a signed ``QuantEvidence`` envelope bound to
the proposal's ``proposal_hash`` (D28-style enrichment): the governance surface
(the TradeProposal / order) is unchanged; the envelope is logged, integrity-
verifiable, and IGNORED by the gates. See docs/planning/D29-quant-probability-layer.md.
"""
from __future__ import annotations

from fleet.crypto.foundation import AgentCert, canonical_bytes, sha256

__all__ = ["AgentCert", "canonical_bytes", "sha256"]
