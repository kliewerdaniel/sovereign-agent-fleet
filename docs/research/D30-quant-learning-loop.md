# D30 — Quant Learning Loop (close the evidence→belief loop)

> **Status:** IMPLEMENTED & TESTED (`exchange/quant/learning.py` + `test_quant_d30.py`; N tests).
> **Depends on:** D29 (Q1 calibration, Q3 Beta-Bernoulli belief + regime, Q6 orchestrator).
> **Meta-invariant:** M0 — the learner is advisory evidence only; it never changes a
> `decide_trade` verdict or an executed `qty`.

## 1. Problem

D29 built the quant layer as a *stateless* per-request estimator: every `evaluate_quant`
call starts from a flat uniform prior `Beta(1,1)` and combines the incoming `model_p_yes`
with market quotes. That means the system **forgets everything between requests** — the
same model that was wrong 50 times in a row still starts each call from the same ignorant
prior, and the operator has no signal that the model is systematically miscalibrated.

A real quant substrate should *learn*: as Kalshi markets settle, the realized outcomes
(0/1) are hard Bernoulli evidence about the true base rate of `P_model(Y=1)`. Folding them
into a running prior turns the quant layer from a point-estimate mirror into a *calibrated
belief* that carries historical performance. This is the "evidence → belief" loop:
forecast → settlement → updated belief → better next forecast.

## 2. Scope

In scope:
- A deterministic, replayable **learner** holding the running learned prior + a
  `CalibrationRecord` history (reuses D29 `calibration.py`).
- Feeding a settlement into the learner (realized Bernoulli draw → conjugate update) +
  calibration bookkeeping (Brier / reliability).
- Injecting the learned prior into `evaluate_quant` as an *advisory* base belief, so the
  `quant` blob's Bayesian posterior reflects learned history (never the verdict).
- A REST surface to (a) observe a settlement and (b) read the calibration report.
- Regime fold-in: a settled outcome that beats the model's stated probability nudges the
  regime drift monitor (reuses D29 `regime.py`).

Out of scope:
- Any change to `decide_trade` / `governance.py` / `fleet/fin/` (locked layers).
- Auto-trading on the learned belief — the learner is evidence, the protocol still decides.
- Real-ZK attestation of the learned prior (scoped D24, unimplemented elsewhere).

## 3. ADRs

### ADR-D30-1 — Learner is advisory-only, M0 preserved
The learned prior is **evidence**. `evaluate_quant` computes the verdict path (governance)
first and attaches `quant` after; the learner only changes the *advisory* `belief` field.
Executed `qty` stays `req.qty`. **Rationale:** identical to D29's Q6-live contract; keeps
the quant layer outside the authority path. **Rejected alternative:** feed the learned
prior into `decide_trade` — violates M0 and the import wall.

### ADR-D30-2 — Reuse the existing conjugate Beta-Bernoulli algebra
The learned prior IS a `BayesianBelief`. A settlement is folded with the existing
`BayesianBelief.update_outcome(outcome)` (exact conjugate Beta update, no new math) and a
forecast with `update_point_estimate`. **Rationale:** D29 already shipped the precise,
hashable, numpy-free algebra; the learner is orchestration, not new theory.

### ADR-D30-3 — Settlements use the `CalibrationRecord` shape
`observe_settlement(ticker, model_p_yes, outcome, ts)` appends a `CalibrationRecord`
(`predicted_prob=model_p_yes`, `outcome=outcome`). **Rationale:** the calibration module
(D29 Q1) already understands this shape; reuse avoids a second ledger. Calibration report
(Brier / rolling / reliability) is computed from these records.

### ADR-D30-4 — Learner state is explicit + opt-in on `Exchange`
`Exchange` holds `self._quant_learner: Optional[QuantLearner] = None`, lazily created on
first `POST /quant/observe`. `evaluate_quant` takes `prior_belief: Optional[BayesianBelief]`
= None; the API passes `ex._quant_learner.prior()` when the learner exists. **Rationale:**
keeps the stateless path the default (D29 unchanged for callers that don't opt in); the
learner is a capability the venue operator turns on.

### ADR-D30-5 — Deterministic + hashable learner (replayable)
`QuantLearner` is constructed from a `state()` dict (exchange_id, prior α/β, prior α/β,
records, model_id, ts) + `compute_hash()` via `fleet.crypto.foundation.sha256(canonical_bytes)`.
Replaying the same settlements yields byte-identical prior hashes (I15 determinism).
**Rationale:** matches D29's audit/replay contract; a verifier can recompute the learned
prior from the settlement sequence.

### ADR-D30-6 — REST surface wrapped so it can never break the order path
`POST /quant/observe` and `GET /quant/calibration` are new routes isolated from `/order`.
The advisory enrichment in `place_order` already runs in `try/except` (D29); adding the
learned prior there is inside that guard. **Rationale:** learning is best-effort evidence;
a learner failure must not affect a single order.

## 4. Module surface (`exchange/quant/learning.py`)

```
QuantLearner(exchange_id, *, model_id="unknown", prior_alpha=1.0, prior_beta=1.0, ts=0)
  .observe_settlement(ticker, model_p_yes, outcome, *, ts=0) -> "QuantLearner"   # chainable
  .prior() -> BayesianBelief            # the running learned prior
  .calibration_records() -> tuple[CalibrationRecord, ...]
  .calibration_report() -> dict         # brier, last_rolling_brier, calibration_error, reliability_bins
  .regime_state() -> RegimeState        # latest folded regime
  .state() -> dict ; .compute_hash() -> str
```

`evaluate_quant(ctx, cert, key, *, prior_belief=None, ...)`: if `prior_belief` is not None,
use it as the base belief instead of `prior_belief(...)`; everything downstream (posterior,
credible interval, evidence binding) reflects learned history.

## 5. Verification

- `test_quant_d30.py`: settlement folds into prior (posterior mean moves toward outcome);
  calibration Brier decreases as model becomes accurate; reliability bins populate; prior
  hash is deterministic/replayable; learned prior injected into `evaluate_quant` changes the
  advisory `belief` field but **not** the decision/gov verdict or executed qty (M0); regime
  nudges on a surprise settlement; import-wall purity (only `fleet.crypto` + intra-package).
- Full regression: 365 (+D30) passing; locked layers byte-untouched; `test_boundary_quant`
  still green.
- API: `POST /quant/observe` then `GET /quant/calibration` returns a populated report;
  a subsequent `POST /order` with `model_p_yes` shows the *learned* posterior.

## 6. Status
IMPLEMENTED.
