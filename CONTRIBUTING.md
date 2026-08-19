# Contributing to Sovereign Agent Fleet

First, thank you for considering a contribution. This project is a research
artifact as much as a codebase: the *architecture* is the contribution, and the
architecture's non-negotiable property is that **no security invariant depends on
model behavior** (meta-invariant **M0**).

## Before you open a PR

1. **Read the thesis, not just the code.** The one-line version:
   > *Do not trust the model. Trust the execution protocol.*
   > `MODEL OUTPUT ≠ AUTHORIZATION`
   The full treatment is the paper
   [`docs/research/30-sovereign-knowledge-systems.md`](../docs/research/30-sovereign-knowledge-systems.md)
   (rendered at [danielkliewer.com/paper](https://www.danielkliewer.com/paper)).
2. **Run the suite.** The default `pytest` run is **563 passing** offline (567
   collected; 4 live-venue `network`-marked tests are deselected unless you pass
   `-m network` with credentials + egress).
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   python -m pytest -q
   ```
3. **Keep the boundaries.** The import walls are load-bearing. The governance
   substrate (`fleet/`) must never import the cognition layer
   (`fleet/cognition`, `exchange/quant`). This is enforced by
   `fleet/tests/test_boundary_epistemic.py` and will fail CI if violated.

## What counts as a good contribution

- **New external consumers** of the *frozen* `fleet.epistemic.decide()` — the
  architecture is domain-general, and each new domain that reuses `decide()`
  with zero substrate edits strengthens the M0 claim. Add it to
  `domain_registry/REGISTERED_CAPABILITIES` and extend the generality suite.
- **Hardening of the authority/execution/verification boundaries** — with a
  test that demonstrates the adversary it defeats (mapped to A1–A6).
- **Clearer evidence / documentation** of an existing invariant.
- **Performance or clarity** that does not change verdicts (run the suite to
  prove verdict-equivalence).

## What a PR should contain

- A focused change. If it touches more than one trust domain, explain why in the
  description.
- Tests. A behavior change without a test is incomplete. New adversarial coverage
  should map to one of the ten classes in `docs/security/`.
- An update to `CHANGELOG.md` under *Unreleased* (or a note that it is
  doc-only).

## Commit / branch conventions

- Default branch is `main`.
- Keep commits legible; squash noise before requesting review.
- CI must be green (`ci.yml` full suite + `fleet-security.yml` supply-chain
  audit).

## Code of conduct

This project adheres to the [Contributor Covenant](CODE_OF_CONDUCT.md). By
participating you agree to uphold it.

## Security-sensitive changes

If your change affects the crypto, identity, approval, or verification path,
see [SECURITY.md](SECURITY.md) and prefer a private disclosure over a public
issue until triaged.
