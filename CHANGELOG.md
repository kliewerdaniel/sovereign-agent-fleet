# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and the project
adheres to semantic versioning of the *research artifact* (the paper and the
code that reproduces it move together).

## [Unreleased]

### Added
- Competition-hardening pass: main `ci.yml` (full-suite gate across Python
  3.11–3.13), `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`,
  `CITATION.cff`, and this `CHANGELOG.md`.
- README upgrades: status badges, feature grid, a runnable `decide()` example,
  and scaffolding pointers.

### Changed
- README evaluation section now states the honest **563 passing offline / 567
  collected** count (4 live-venue `network`-marked tests are deselected by
  default) and separates the three registers (architectural / implementation /
  experimental) the paper is disciplined about.

## [v3.6] — paper freeze-ready rigor
- Referee-calibrated register: conformance tests vs. one genuinely *blind*
  adversary harness; Theorem→Proposition; disclosed single-author corpus scope;
  explicit "no part machine-checked" statement.
- Added `fleet/tests/test_decision_sweep.py` (6,000-point parametric sweep, 0
  false accepts) and `fleet/tests/test_adversarial_blind_harness.py` (5,000
  randomized attack vectors, 0 false authorizations).
- Suite: **563 passing offline** (567 collected; 4 live-venue `network`-marked
  integration tests are deselected by default and require Kalshi credentials +
  egress). 564 baseline + 3 from the two v3.6 generator files.

## [v3.5] — frozen architecture baseline
- Five architectural invariants, three trust domains, A1–A6 threat model, four
  research questions. Reproducibility pinned to commit
  `489e01697e664be6a0decd0ac0e335daeb47d9c4`.

## [Earlier]
See `docs/research/` (the D1–D30 decision log) for the full design history from
Phase 0 through the domain-general M0 consolidation.
