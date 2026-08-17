# Epistemic Object Model (EOM) — Round 2A design

> **Status: DESIGN ONLY. No code. No commit.** This document defines the shared
> epistemic vocabulary the next architecture increment builds on. It ratifies three
> forks and specifies a closed-loop object model. Implementation is deferred until
> Round 2B (competing beliefs, calibration) and 2C (adaptation) are modeled on top.

**Why this exists.** Today the repo already has epistemic fragments — `ProbabilityEstimate`
(exchange/quant), `EvaluationArtifact` (fleet/cognition), `QuantEvidence`, `CalibrationRecord`,
`ExecutionReceipt` — but they do not share a type and they do not form a hash-linked lineage.
That blocks the higher-value questions: *two agents cannot be said to believe the same thing*,
*the verifier cannot reconstruct a belief from its evidence*, and *calibration cannot be measured
against outcomes*. The EOM fixes the vocabulary first; code follows only after 2B/2C.

**Ratified forks (Round 2A):**
- **F1 — Structured propositions.** A belief states a *typed* proposition, not free text. This is
  what makes disagreement (2B-6) and calibration (2B-7) computable.
- **F2 — Neutral module home.** The EOM lives in `fleet/epistemic/`, imports **only**
  `fleet.crypto` + stdlib, and is importable by both existing import walls.
- **F3 — Lineage strictness.** Evidence lineage is **mandatory on the financial path**; elsewhere
  it is best-effort and downgrades the trust tier (ASSERTED) when incomplete.

---

## 1. Common primitives

Every EOM object is **frozen, hashable, and content-addressed**:

```python
@dataclass(frozen=True)
class EpistemicObject:
    producer: str          # AgentCert.agent_id of the issuer
    ts: int                # epoch seconds
    content_hash: str      # sha256(canonical_bytes(state())); excludes content_hash itself
    def state(self) -> dict: ...
    def compute_hash(self) -> str: return sha256(canonical_bytes(self.state()))
```

`canonical_bytes` + `sha256` are the existing `fleet.crypto.foundation` primitives already used by
`exchange/quant/probability.py` and `fleet/fin/domain.py`. All objects follow the same signed-
exclusion convention (`state()` omits `signature`/`content_hash`).

---

## 2. The object chain

```text
Observation ─┐
             ├─► Evidence ─► Belief ─► Hypothesis ─► Prediction
             │                 │                        │
             │                 │                        ▼
             │                 │                   Proposal ─► AuthorizationRequest
             │                 │                                  │
   (also) ───┘                 └────────── evidence_refs ─────────┘
                                                         │
                                              AuthorizationDecision (governance)
                                                         │
                                                      Action (ExecutionReceipt)
                                                         │
                                                      Outcome
                                                         │
                                                   Evaluation ─► Calibration
                                                         ▲
                              Calibration feeds back as Evidence (closed loop)
```

Each arrow is a **hash reference**, not an object copy. The verifier can reconstruct any node from
its ancestors without trusting the producer's prose.

### 2.1 Observation (root)
```python
class Observation(EpistemicObject):
    source: str          # "kalshi_feed" | "retrieval" | "log" | "sensor" | "sim"
    kind: str            # "quote" | "document" | "event" | ...
    payload: dict        # source-specific raw content
```
Examples today: `exchange/feeds` quotes, `simenv/` sim states, incident observations. Not yet a
typed node — this makes it one.

### 2.2 Evidence (lineage node) — *Q2*
```python
class Evidence(EpistemicObject):
    kind: Literal["observation","retrieved","statistic","inference",
                  "external_fact","historical_outcome","simulation","derived_math"]
    payload: dict                   # kind-specific
    inputs: list[str]               # hashes of upstream Observation / Evidence
```
`derived_math` covers `MarketProbability` (computed from a quote) and `ExpectedValue`. `inference`
covers model-derived quantities. **Lineage:** verifier walks `inputs` to a reconstructable root.

### 2.3 Belief — *Q1*
```python
class Belief(EpistemicObject):
    proposition: Proposition        # F1: structured (§3)
    estimate: Uncertainty           # Q3: typed union (§4)
    evidence_refs: list[str]        # hashes of Evidence nodes
    model_id: str                   # which intelligence source
    method: str                     # mathematical method used
```
Promotes the existing `ProbabilityEstimate` (frozen, hashable, `p_yes`+`uncertainty`+`model_id`)
into a general form: structured proposition + typed uncertainty + **hash links back to evidence**.
Belief *interprets* evidence under a model for a specific proposition; it is distinct from Evidence.

### 2.4 Hypothesis — *new (ties to D28 Popper)*
```python
class Hypothesis(EpistemicObject):
    proposition: Proposition
    implied_observables: list[str]
    falsifiers: list[str]           # documented falsification attempts
    source_belief_refs: list[str]
```
Carries its own falsifiers (the D28 `EvaluationArtifact.popper` discipline, promoted to a first-class node).

### 2.5 Prediction — *new*
```python
class Prediction(Belief):          # a Belief about a FUTURE event
    horizon: int                   # ts the event resolves at
```
This is the unit calibration (2B-7) measures against outcomes.

### 2.6 Proposal — *Q4 boundary*
```python
class Proposal(EpistemicObject):
    belief_refs: list[str]                   # the belief(s) it rests on
    action_descriptor: ActionDescriptor      # WHAT is intended (descriptor, not a verb)
    rationale: str                           # human-readable only; NOT read by gates
```
Cognition owns this. It references Beliefs; it does **not** contain authorization fields.

### 2.7 AuthorizationRequest — *Q4 seam*
```python
class AuthorizationRequest(EpistemicObject):
    request_id: str
    capability: str               # authority being requested (governance vocabulary)
    action_descriptor: ActionDescriptor   # EXACT action
    conditions: dict              # C — context governance reads
    proposal_ref: str             # hash link to Proposal (NOT embedded belief fields)
```
**Critical:** this type structurally excludes `confidence`, `probability`, `belief`, or any
probabilistic directive. An LLM cannot emit an authorization request that smuggles a probability,
because the schema cannot carry one. Governance reads `capability`, `action_descriptor`,
`conditions`, and its own `authority`/`policy`/`risk_limits`.

### 2.8 AuthorizationDecision — governance owns
```python
class AuthorizationDecision(EpistemicObject):
    request_id: str
    disposition: Literal["AUTO","HUMAN","BLOCKED"]
    reason_code: str
    risk_assessment: RiskAssessment       # deterministic
    authority_ref: str                    # the authority record consulted
```
Pure function of deterministic inputs. M0 holds: identical request + identical deterministic state
→ identical disposition, with or without any cognition present.

### 2.9 Action / Outcome / Evaluation / Calibration
- **Action** = executed step, state-locked (existing `ExecutionReceipt` pattern).
- **Outcome** = measured result (existing settlement).
- **Evaluation** = post-hoc scoring of a Prediction vs its Outcome (extends the existing
  `CalibrationRecord` family).
- **Calibration** = rolling per-`(producer, proposition_template)` reliability (existing
  `rolling_brier`, `reliability_bins`, promoted to a named node).

---

## 3. Proposition (F1 — structured) — *the linchpin*

```python
class Proposition:
    domain: str        # "market_probability" | "incident_compromised" | "research_finding" | ...
    subject: str       # ticker / asset_id / incident_id / entity_id
    predicate: str     # "P_yes" | "is_compromised" | "will_occur" | "has_property"
    params: dict       # auxiliary: horizon, outcome space, etc.
```

Two beliefs are **about the same thing** iff `(domain, subject, predicate, params)` match. This makes:
- **disagreement** (2B-6) a computable relation: competing agents → same Proposition → differing `estimate`.
- **calibration** (2B-7) measurable per `proposition_template`: a producer's `Point(p)` predictions
  for template T are scored against realized outcomes for T.

Without F1, both are impossible — you cannot aggregate or calibrate free text.

---

## 4. Uncertainty (Q3 — typed union, not a field) — *the anti-"confidence: 0.93"*

```python
Uncertainty =
  | Point(p: float in (0,1))                  # single probability (binary market)
  | Interval(lo: float, hi: float, level)     # credible / confidence interval
  | Distribution(samples: list[float] | params: dict)   # full posterior
  | Calibrated(p: float, score: float, n: int)          # p + historical calibration
  | Entropy(h: float)                                  # multi-outcome belief
  | Risk(expected: float, downside: float, var: float) # decision-relevant
```
Each variant carries:
```python
    kind: str            # discriminant
    epistemic: float | None    # REDUCIBLE uncertainty (model-doesn't-know)
    aleatoric: float | None    # INHERENT uncertainty (cannot be reduced by data)
```

Rules:
- **Governance never consumes a bare `confidence` scalar.** It consumes the specific variant a
  claim warrants (e.g. risk math consumes `Risk`, not `Point`).
- **Epistemic vs aleatoric** is recorded because only epistemic uncertainty justifies "collect more
  evidence" (the basis for 2C-4 online learning to matter).
- A `Calibrated` estimate is what `evaluate_quant`/cognition should emit when a producer has a
  calibration history (2B-7).

---

## 5. The Belief→Proposal boundary as a type-level seam (Q4) — *governance can't be collapsed*

Today `ProposalArtifact` uses `governance_surface: Any` so cognition never imports the typed
proposal. The EOM makes the four layers **separate signed types in a neutral module**, so the wall is
visible to the type-checker, not just the runtime:

| Layer | Owner | May import EOM? | May import governance? |
|-------|-------|----------------|------------------------|
| Observation/Evidence/Belief/Hypothesis/Prediction | cognition / quant | yes | **no** |
| Proposal / AuthorizationRequest | cognition (request) | yes | **no** |
| AuthorizationDecision / RiskAssessment | governance | read-only | yes |

The agent cannot return a single LLM blob that is "belief + proposal + decision" because:
1. the request schema physically cannot carry a probability (§2.7), and
2. cognition cannot import the governance module that produces the decision (existing walls + F2 allowlist).

---

## 6. Probabilistic cognition vs deterministic computation (Q5) — *the impossibility guarantee*

Deterministic operations live **only** in modules cognition cannot import. Classification:

| PROBABILISTIC (cognition / quant — never authority) | DETERMINISTIC (governance / fin — cognition cannot import) |
|------------------------------------------------------|-------------------------------------------------------------|
| prediction, classification, Bayesian belief update | position limits, exposure, leverage |
| regime inference, semantic interpretation | available capital, Kelly fraction cap |
| hypothesis generation | drawdown limits, mandate clamp |
| model-derived probability / edge | authorization rules, state transitions |
| (QuantEvidence, ProbabilityEstimate) | settlement, cryptographic verification |
| | RiskLayer.assess, decide_trade |

The system makes it **impossible** for an LLM to replace the right column with the left: the right
column's modules are outside the cognition/quant import walls. Probabilistic outputs are sealed
into Belief/Evidence and are read by governance **only as inputs to deterministic math**, never as
directives. This is the runtime expression of M0 and is already enforced by the existing walls.

---

## 7. Module home and import-wall updates (F2) — *documented, not applied*

New package `fleet/epistemic/`:
- imports ONLY `fleet.crypto.foundation` + stdlib;
- imported by `fleet/cognition/**` and `exchange/quant/**` (requires allowlist updates below);
- imported read-only by `fleet/layers/**` (governance).

Boundary-test changes required (to be made at implementation time, with tests):
- `fleet/tests/test_boundary.py`: add `fleet.cognition.** → fleet.epistemic` to the ALLOW set.
- `exchange/tests/test_boundary_quant.py`: add `exchange.quant.** → fleet.epistemic` to the ALLOW set.

These are the *only* boundary relaxations. `fleet.cognition.**` still may NOT import
`gateway`/`policy`/`runtime`/`fin.domain.assess`/`incident.required_authorization`/`verify`.
`exchange.quant.**` still may NOT import `exchange.governance`/`fleet.fin`/`fleet.cognition`.

---

## 8. Lineage enforcement (F3)

- **Financial path (mandatory):** every `Belief` feeding an `AuthorizationRequest` must have
  complete `evidence_refs`, and each referenced `Evidence` must have a reconstructable `inputs`
  chain to an `Observation`. If not, the request is **BLOCKED** at the evidence gate (D16 HALLUCINATION
  equivalent for lineage).
- **Other domains (best-effort):** incomplete lineage downgrades the trust tier to `ASSERTED`
  (the existing D16 tier) and is logged, never silently trusted, never auto-upgraded to VERIFIED.

This is what makes the lineage a verification primitive rather than a documentation nicety.

---

## 9. Closed loop (the architectural prize)

```text
             ┌───────────────────────────────────────────────┐
             │                                               │
  Observation → Evidence → Belief → Proposal → Authorization │
                         ↑                    │              │
                      Calibration            Action          │
                         ↑                    │              │
                      Evaluation ←────── Outcome ←───────────┘
```

Outcomes are measurable in finance — which is exactly why finance is the preferred *experimental
environment* for this architecture, not its purpose. The same EOM supports incident response,
security ops, research, infra, forecasting, robotics: only the `domain`/`predicate` of
`Proposition` and the `ActionDescriptor` change. **This is where Sovereign Agent Fleet becomes a
general cognitive architecture rather than a governance framework with a trading demo.**

---

## 10. Open for Round 2B / 2C (NOT resolved here)

- **2B-6 Competing beliefs:** `EpistemicAggregation` over `Belief[proposition == P]` → disagreement
  is a first-class relation; the fleet becomes a *reasoning substrate*, not a voter. Builds on F1.
- **2B-7 Calibration:** `Calibration` per `(producer, proposition_template)` consumes `Prediction`
  vs `Outcome`; distinguishes **confidence** from **calibrated confidence**. Uses §3 + §4.
- **2B-8 Prediction vs decision:** decision quality depends on payoff/downside/exposure/etc.; the
  EOM's Belief→Proposal→Authorization separation is what lets a good prediction fail to authorize.
- **2C Adaptation:** regime change, concept drift, online learning, model replacement, learned vs
  formal, D28 runtime integration, cross-domain generalization — all sit *on top of* a stable EOM,
  which is why they come last.

## 11. Status / next step

Design ratified (F1/F2/F3). No code written. After you approve, Round 2B models competing-belief
aggregation + calibration on this model; only then do we implement `fleet/epistemic/` and promote
the existing fragments.
