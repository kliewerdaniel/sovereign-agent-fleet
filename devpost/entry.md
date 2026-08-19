# Devpost Entry — Sovereign Agent Fleet: Trust the Protocol, Not the Model

## Inspiration

Every popular agent framework treats the model as the agent: it reasons *and* it acts.
But cognition is **probabilistic** — it can be wrong, it can be compromised, and it can be
adversarially steered. When the same component that thinks also holds the keys, a single
failure (a hallucination, a prompt injection, a bribed endpoint) becomes a consequential
action in the real world.

The insight that started this project: a *confident* model is not an *authorized* one, a
*correct* model is not a *permitted* one, and an identity can be compromised yet still be
prevented from escalating authority. The fix is not "make the model safer" — it is to stop
letting the model be the authority. That became the thesis behind everything here:

> **Do not trust the model. Trust the execution protocol.**

## What it does

Sovereign Agent Fleet is a local-first governance substrate that keeps **cognition** and
**authority** in separate trust domains that never share a process boundary.

- **A frozen, deterministic authorization function** — `fleet.epistemic.decide()`. A pure
  function with no model output, no RNG, no wall clock, and no network. It returns exactly one
  verdict:

  $$
  \text{decide}(\text{identity},\ \text{grant},\ \text{scope},\ \text{request},\ \text{constraints},\ \text{epoch},\ \text{now},\ \text{trusted\_issuer})
  \;\in\; \{\text{AUTO},\ \text{HUMAN},\ \text{BLOCKED}\}
  $$

- **An import wall.** The cognition layer is *physically* blocked from importing authority
  modules. A structural test parses `evaluation.py` and fails the build if it imports any
  gateway, policy, runtime, finance, or incident module — so the model's reasoning code
  cannot reach the decision code.

- **A real crypto chain.** Argon2id KDF → Ed25519 identity → XChaCha20-Poly1305 sealed
  envelopes. Capability grants are bound to a pinned issuer key and verified by an independent
  verifier.

- **Six independent domains** — exchange/finance, incident, supply, hypothesis, mirror, and
  grid — each reuse the *same* `decide()` with **zero substrate edits**. The brain behind a
  proposal is irrelevant.

- **Independent verification.** An executor that falsely reports success is detected, not
  trusted. Execution only occurs if `decide()` authorized it.

The governing invariant is written in one line:

$$
\boxed{\text{MODEL OUTPUT} \;\neq\; \text{AUTHORIZATION}}
$$

## How we built it

- **Language & runtime:** Python 3.11–3.13, intentionally dependency-light — stdlib crypto
  plus `cryptography`, `pynacl`, and `argon2-cffi`.
- **Control plane:** a canonical FastAPI surface (`fleet/api`) with a `websockets` live ticker
  client and `httpx`-backed test client.
- **Authorization core:** a single frozen, deterministic `decide()` function — the only thing
  that can grant authority — with no model path in or out.
- **Verification gate:** Pytest drives 563 offline tests against an explicit **A1–A6 threat
  model** (identity forgery, capability escalation, approval mutation, artifact tampering,
  audit tampering, cross-domain authorization). 4 live-venue integration tests are
  network-marked and deselected by default.
- **CI:** GitHub Actions runs the full suite across the Python matrix; a separate supply-chain
  audit (`fleet-security`) runs `pip-audit` fail-closed with a CycloneDX SBOM.
- **Demo:** a scripted Playwright capture narrated over the paper, assembled with `ffmpeg`.
- **Optional cloud:** Cloud Run / Firestore / Pub-Sub and OpenTelemetry are an *add-on layer*
  (`requirements-gcp.txt`) — never required to run the suite.

## Challenges we ran into

1. **The portability trap.** The import-wall test originally opened its source file through a
   hardcoded absolute path to a developer laptop (`/Users/.../evaluation.py`). It passed
   locally for *weeks* while every CI run failed with `FileNotFoundError`. Tests are code — they
   must be portable, or your green badge is a lie. Fixing it flipped both workflows from red to
   green.
2. **Holding the wall as the system grew.** Adding six domains, an API, and a demo create
   constant temptation to "just import `decide` from cognition." The import-wall test is the only
   thing that held the boundary; without it the architecture would have silently collapsed back
   into an ordinary framework.
3. **Walking back our own language.** Once "experimentally evaluated" lands in an abstract, it is
   painful to retract. Calibrating claims to what was actually measured was the hardest part of
   the writeup — and the most worthwhile.
4. **The demo pipeline.** The narration TTS is deterministic per input text, so a garbled beat
   could only be fixed by *rephrasing* the script — which changed the clip duration and forced
   re-capturing every visual, re-syncing timings, and re-assembling the video.

## Accomplishments that we're proud of

- The **frozen authorization function** genuinely never reads or trusts model output — verified
  by a structural import-wall test, not by convention.
- **Six real domains** reusing one `decide()` with zero substrate edits, proving the architecture
  is domain-general rather than finance-specific.
- **563 tests passing offline** against a named A1–A6 threat model, including a genuinely blind
  fuzz harness of 5,000 randomized attack vectors with zero false authorizations.
- **Two green CI workflows** (CI + supply-chain audit) after a real, reproducible portability
  bug that had been masking failures for weeks.
- An honest paper that **says what it is** — conformance testing, not science — and names
  knowledge poisoning as an unsolved problem instead of hiding it.

## What we learned

- **Confirmatory tests are not "adversarial experiments."** A referee review forced us to stop
  over-claiming. The suite verifies the system against *its own* author-specified threat model —
  that is conformance testing. Only a genuinely blind fuzz of `decide()` earns the word
  *adversarial*. Calibrating the evidentiary register honestly matters as much as the
  architecture does.
- **Authority integrity is not truth.** The protocol can *guarantee* that no unauthorized action
  occurs. It cannot guarantee the *knowledge* the model reasoned from was untampered. Knowledge
  poisoning — feeding the cognition layer false premises — is an open problem we now state
  explicitly.
- **Green locally means nothing; green in CI means something.** The portability bug taught us to
  trust the reproducible environment over our own machines.

## What's next for Sovereign Agent Fleet: Trust the Protocol, Not the Model

- **Close the knowledge-poisoning gap.** Add provenance and integrity attestation for the
  cognition layer's inputs, so a tampered premise is detected before it becomes a (correctly
  authorized, wrongly reasoned) proposal.
- **Formal verification.** Lift the five invariants from English into a machine-checked spec
  (e.g., TLA+ or a dependent type) so "the boundary holds" is a proof, not a test.
- **A governed executor runtime.** Ship the reference execution environment that enforces decided
  scopes end-to-end, not just the decision function.
- **Broader domain adapters.** Demonstrate the same frozen `decide()` governing code-execution,
  email-sending, and infrastructure-change domains.
- **Production deploy.** Publish the demo to `danielkliewer.com` and a public Cloud Run instance
  behind the supply-chain-audited pipeline.
