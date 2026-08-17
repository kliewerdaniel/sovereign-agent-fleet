"""How to add a domain (M0 preserve): the epistemic-adapter recipe.

This is the standing recipe for adding a NEW external consumer to the frozen
``fleet.epistemic`` substrate WITHOUT ever touching the substrate. It is how
``incident/`` (Phases 3–4), ``supply/`` (Phase 5), and ``hypothesis/`` (Phase 5)
were each wired as independent proof that the substrate is domain-general.

The invariant this recipe preserves: **the substrate cannot tell which domain is
feeding it.** Every new domain is a *bilingual node* — it imports the domain
package AND ``fleet.epistemic``, but neither of those trees imports the adapter.

Prerequisites
-------------
- The substrate (``fleet/epistemic/``) is frozen: it imports ONLY
  ``fleet.crypto.foundation`` + stdlib (enforced by
  ``fleet/tests/test_boundary_epistemic.py``). Do not modify it to "support" a
  domain. If you find yourself wanting to, the design is wrong — fix the adapter.
- Your domain must NOT import ``fleet.epistemic`` from inside its own runtime
  package (that would make the substrate importable-by-accident and break the
  directionality test RISK 7). Only the adapter imports both sides.

Step 1 — Domain package (the "foreign" side)
--------------------------------------------
Create ``<domain>/`` with its own runtime objects. They import NOTHING from
``fleet.epistemic``, the other domains, or ``fleet.layers``.

    <domain>/__init__.py
    <domain>/sim.py          # e.g. DomainSignal + DomainPlan (frozen dataclasses)
    <domain>/tests/__init__.py

``DomainSignal`` carries the raw domain cognition (e.g. severity, p_value,
stockout_prob). ``DomainPlan`` carries the proposed action (advisory only — it is
NEVER a permission). Give the plan a ``recommendation`` property returning a
neutral classification string ("RUN"/"HOLD", "REORDER"/"HOLD", "REMEDIATE"/"HOLD").

Step 2 — Adapter package (the bilingual node)
---------------------------------------------
Create ``<domain>/epistemic_adapter/``:

    __init__.py     # re-exports the public surface (see below)
    authority.py    # GovernanceAuthority + issue_grant (holds the Ed25519 key)
    translate.py    # pure domain -> neutral mappings

Public surface to re-export (mirror ``exchange/incident/supply/hypothesis``):
    GovernanceAuthority, issue_grant,
    build_capability_scope, build_authorization_scope,
    build_governance_constraints,
    signal_to_proposition, signal_to_evidence,
    plan_to_recommendation, plan_to_assessment, plan_to_request,
    decide_<domain>_action,
    CAP_<DOMAIN>_<ACTION> = "<domain>.<action>"   # capability strings

authority.py — verbatim mirror of any existing adapter's ``authority.py``; only
the default ``governance_role`` string changes. It holds the trusted issuer key
and signs ``AuthorityGrant`` objects. The substrate NEVER sees the private key.

translate.py — pure functions:
  * ``signal_to_proposition(sig)`` -> ``Proposition(domain=..., subject=...,
    predicate=..., params=...)``. This is the linchpin: choose neutral
    domain/subject/predicate that identify the statement deterministically.
  * ``signal_to_evidence(sig, prop)`` -> ``Evidence(payload={...})``. ALL domain
    metrics (severity, p_value, stockout_prob, lead_time) live ONLY inside
    ``payload`` as opaque data. The substrate hashes the object; it never reads
    them.
  * ``plan_to_recommendation(plan, prop)`` -> ``Recommendation(authority="NONE",
    ...)``. The substrate's own ``__post_init__`` forces authority to NONE, so
    this can never become a permission.
  * ``plan_to_assessment(plan)`` -> ``Assessment(result=plan.recommendation, ...)``
    — a classification, not a permission.
  * ``plan_to_request(...)`` -> ``AuthorizationRequest(capability=CAP_..., ...)``.
  * ``decide_<domain>_action(...)`` — the ONE place ``decide()`` is called. Pass
    a fully generic ``identity`` + signed ``grant`` + ``authorization_scope`` +
    ``request`` + ``constraints`` + ``trusted_issuer_pubkey_pem``.

Step 3 — Tests (spec = the boundary)
-------------------------------------
Create ``<domain>/tests/test_epistemic_adapter_phaseN.py`` mirroring
``hypothesis/tests/test_epistemic_adapter_phase5.py``. It MUST contain:

  A. CONSUMER PROOF (>=4 tests): drive real domain objects through the adapter
     into ``decide()``; assert correct ``AuthorizationDecision`` using only
     generic inputs; assert domain metrics stay in Evidence.payload only; assert
     Recommendation stays advisory (authority=="NONE"); assert Assessment is a
     classification.

  B. REVERSE-BOUNDARY ADVERSARIAL (8 RISKS):
    1. DomainPlan is not an epistemic authority object (not AuthorityGrant /
       AuthorizationDecision).
    2. Domain metrics cannot influence the verdict (same verdict fed hi vs lo).
    3. Domain object identifiers cannot appear as CODE in ``fleet/epistemic``
       (AST identifier scan).
    4. Domain capability is not a universal authorization (scoped grant cannot
       authorize ``system.shutdown`` -> BLOCKED).
    5. Cannot bypass ``decide()`` (adapter sources ``decide(`` and substrate
       sources ``AuthorizationDecision(``).
    6. Cannot self-sign a valid grant (forged grant -> BLOCKED /
       invalid_grant_signature).
    7. ``fleet.epistemic`` does not import this adapter (AST import scan across
       ALL known domain/adapter packages).
    8. Substrate works with ALL adapters removed from ``sys.modules``.

  C. CROSS-DOMAIN GENERALITY (M0 proof): build a generic ``_neutral_decision``
     and assert the SAME verdict across ALL existing domains under equal policy,
     and that ALL domains flip AUTO->HUMAN together on a policy change. This is
     the test that keeps the substrate honest: add your domain's capability to
     the cross-domain list.

Step 4 — Verify (isolated env, no PYTHONPATH leak)
--------------------------------------------------
    cd /path/to/sovereign-agent-fleet
    env -i PATH="$PWD/.venv/bin:/usr/bin:/bin" HOME="$HOME" PYTHONPATH="$PWD" \
      python -m pytest <domain>/tests/test_epistemic_adapter_phaseN.py -q
    # then the full suite:
    env -i PATH="$PWD/.venv/bin:/usr/bin:/bin" HOME="$HOME" PYTHONPATH="$PWD" \
      python -m pytest -q

The frozen substrate suite (``fleet/tests/test_*epistemic*.py``) must stay at its
current count and ALL GREEN. The full repo suite grows by your new tests; no
regressions anywhere.

Step 5 — Document
-----------------
- Add a row to the README repo-layout table and a bullet under "What's
  implemented" describing the new consumer + its M0 proof.
- Bump the "N passing tests" figures.
- Add the new capability string to the cross-domain generality test in EVERY
  existing domain's suite (so all domains stay mutually checked).

The M0 meta-invariant
---------------------
No security invariant depends on model behavior. The model may lie/hallucinate;
authority stays at the governance boundary. The substrate decides on
(grant, scope, policy) — never on the domain that uttered the request.
