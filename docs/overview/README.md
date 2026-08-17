# Overview — Sovereign Agent Fleet

> **A sovereign cognitive control plane for governing probabilistic agents and
> consequential actions.**
>
> Cognition is probabilistic. Authority is deterministic.

## What is this?

A local-first system that lets capable-but-untrustworthy agents **propose** consequential
actions, while a deterministic, cryptographically-verifiable control plane decides
whether those actions are **authorized**, **executed**, and **recorded**. The agents
reason; the protocol governs.

It is **not** another multi-agent framework. Frameworks orchestrate agents. This governs
them — and the governance is independent of which brain (local LLM, cloud model, or a
pure deterministic strategy) produced the proposal.

## Why does it exist?

Modern agentic systems combine powerful probabilistic reasoning with increasingly
consequential actions. The model can reason — but **reasoning is not authority**. A
confident model is not an authorized one. A correct model is not a permitted one. An
identity can be compromised and still be prevented from escalating authority. Evidence can
establish truth without granting permission.

We built a control plane that makes those distinctions *structural*: they fall out of the
code's import boundaries and its pure-function decision logic, not from docstrings.

## What makes it different?

- **Cognition and authority are separate layers.** The cognitive layer (brains, retrieval,
  persona, quantitative reasoning) produces proposals + evidence. It can never call the
  decision function. Enforced by import walls (`fleet/cognition` cannot import `gateway`
  / `policy`; `exchange/quant` cannot import `exchange/governance` / `fleet/fin`).
- **The meta-invariant M0.** No security invariant depends on model behavior. Remove all
  cognition from an already-formed proposal and the authorization verdict is unchanged
  (verified by a Run-A = Run-B verifier).
- **Deterministic authority.** Identity, capability, policy, approval, and signing live in
  the control plane — never in the model.
- **Independent verification.** Every decision is signed into a tamper-evident ledger; an
  out-of-band verifier reconstructs the inputs and recomputes the disposition, proving what
  happened without holding any authority.
- **Local-first sovereignty.** Authority/keys stay local; only signed artifacts replicate.

## How does it work? (one paragraph)

A cognitive agent observes the world and emits a **proposal** (plus optional evidence —
D28 enrichment). That proposal crosses into the **governance layer**, which authenticates
the identity, checks the capability (gateway, default-deny), evaluates risk/policy
(incident matrix or financial risk matrix), and — if needed — requires a cryptographically
bound human approval. The result is a signed **authorization** that the **execution
environment** validates against the *exact current state* before it transitions anything.
The whole exchange is recorded in a signed ledger and later independently **verified**.

The full flow: `Environment → Evidence → Cognitive agent → Proposal → Deterministic policy
→ Capability/authority → Approval/consensus → Execution gateway → Cryptographic record →
Audit/verification`.

## What is actually implemented?

See [`architecture/`](../architecture/) and [`demos/`](../demos/). In brief: a complete
governance substrate (`fleet/`, ~225 tests), two financial reference workloads
(`exchange/` venue+quant and `fleet/fin/` paper-trading), the D28 cognitive-architecture
scaffolding, adversarial demos, and a canonical Next.js control surface (`ui/`). **384
tests pass.**

## How is it secured?

See [`security/`](../security/) and [`governance/`](../governance/). Root-of-trust identity
hierarchy, Ed25519-signed hash-chain ledger, fail-closed gates, cryptographically-bound
human approval, live key rotation, default-deny property tests, and consensus that can only
*escalate*, never authorize.

## How can I run it?

See [`development/`](../development/). `pip install -r requirements.txt && pytest` runs the
full suite. The `ui/` surface: `uvicorn fleet.api.app:app` + `npm run dev` in `ui/`.

## What can I see?

See [`demos/`](../demos/): a 5-minute adversarial governability demo, the exchange
quant pipeline (propose → risk → quant-evidence → state-locked execution → verification),
and the D24 ZK attestation.

## What happens when an agent attempts something unauthorized?

It is **denied or held** by a deterministic gate — a forged identity is rejected, a missing
capability returns DENY, a HALLUCINATION is blocked at the evidence gate, a proposal needing
human sign-off is held pending an Ed25519-bound approval, and a PROTECTED target can be
VERIFIED-compromised yet still BLOCKED by policy. Every such outcome is a signed ledger
entry. This is the core "aha."

## Where is this going next?

See [`roadmap/`](../roadmap/) and the open research questions. The trajectory
(D27 → D28 → D29/D30) is an evolution from *governed action* → *governed cognition* →
*governed quantitative decision-making*.
