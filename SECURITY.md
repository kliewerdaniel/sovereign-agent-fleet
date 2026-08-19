# Security Policy

Sovereign Agent Fleet is a research system whose entire thesis is *authority
integrity independent of model behavior*. Security issues here are taken
seriously because they are the subject matter.

## Supported versions

Only the latest `main` is supported. The paper-pinned reproducibility commit
(`489e01697e664be6a0decd0ac0e335daeb47d9c4`) is preserved for result
derivation, not for security fixes.

## Reporting a vulnerability

**Do not open a public issue for a suspected vulnerability.**

Email the maintainer (see the paper / repo owner) or open a draft security
advisory on GitHub. Include:

- A minimal reproduction (or a precise description of the adversary: A1–A6).
- The expected invariant and the observed violation.
- The commit/version it reproduces against.

You will get a response within a few days. Fixes are developed on a private
branch and disclosed once a patched version is available.

## Scope of the threat model

The formal adversaries are documented in the paper (§9 / Table 1) and
`docs/security/`:

- **A1** Rogue model (induce an unauthorized action)
- **A2** Forged identity
- **A3** Approval forgery / rebind
- **A4** Audit tampering
- **A5** Executor deception (false success report)
- **A6** Capability escalation

Out of scope (explicitly open research problems, not vulnerabilities):

- **Knowledge poisoning** — the architecture guarantees authority and execution
  integrity but does not yet validate *epistemic* integrity of ingested
  knowledge. Flagged as the paper's central open problem.
- Denial-of-service, side channels, and physical compromise of the root key
  holder.

## Supply-chain guarantees

- Base runtime deps are pinned (`requirements.lock.txt`); GCP bridge deps are
  pinned separately (`requirements-gcp.lock.txt`).
- `fleet-security.yml` runs `pip-audit` (fail-closed on known CVEs) and uploads a
  CycloneDX SBOM on every push/PR.
- The governance substrate uses only the Python standard library plus
  `cryptography` / `pynacl` / `argon2-cffi`; it imports **no** model or network
  libraries on the authorization path.
