"""FIFTH external consumer — agent self-observability / introspection (M0 proof).

This package is the decisive FIFTH external consumer of the frozen
``fleet.epistemic`` substrate. It is a completely different domain *shape* from
the other four (finance, incident/security, supply/logistics, hypothesis/
research): rather than describing an external world-state, it describes the
agent reasoning about *itself* — self-health signals and self-tuning proposals.

Its special purpose: it exercises the **L0 ladder** end-to-end through the
adapter boundary —

    Proposition -> Assessment -> Recommendation -> Proposal -> AuthorizationRequest

— and proves the promotion steps carry **no silent authority**. A self-
reflection becomes a ``Recommendation`` (advisory, ``authority="NONE"``), and at
most a ``Proposal`` (intent, bounded by ``ProposalScope``). Neither is ever a
permission: authorization still requires an externally-signed ``AuthorityGrant``
verified by ``decide()``. The adapter enforces the promotion gate fail-closed,
because the frozen substrate itself is domain-neutral and intentionally does not
read ``ProposalScope``.

It follows the exact bilingual pattern of the other four consumers: it imports
the domain package AND ``fleet.epistemic``, but neither restricted tree imports
it. Zero substrate edits.
"""
