---
title: "Sovereign Knowledge Systems: An Experimentally Evaluated Architecture for Separating Probabilistic Cognition from Consequential Authority"
author: Daniel Kliewer
date: 2026-08-18
version: 3.5
status: evaluated
canonical_url: /paper
abstract: >-
  We present an experimentally evaluated architecture for governed agentic
  computation in which probabilistic model cognition is deliberately treated as an
  untrusted epistemic component, while authorization, execution, verification, and
  evidence are implemented as independently governed computational boundaries. The
  architecture is organized around a single research object -- an explicitly
  ordered trust-transition sequence (knowledge -> compilation -> retrieval ->
  cognition -> proposal -> authorization -> execution -> verification ->
  evidence) -- and a formal principle, the Authority Non-Equivalence Principle: no
  probabilistic inference, regardless of confidence, capability, or semantic
  plausibility, constitutes authorization to perform a consequential operation. We
  state five architectural invariants and we formalize the distinction between
  three types of correctness the architecture separates -- epistemic, authority,
  execution -- none of which implies the others. The architecture is implemented
  and demonstrated across two cooperating codebases: A10 (the epistemic substrate:
  a knowledge compiler producing a versioned graph and search index behind a
  fail-closed gate) and Sovereign Agent Fleet (the authority and execution
  substrate: a frozen deterministic authorization function, cryptographic
  identity, human approval, bounded execution, and a tamper-evident audit ledger).
  We evaluate the architecture against its own invariants using its test suite as
  the benchmark (564 executable tests in the governance substrate, all passing; 18
  fail-closed compiler-gate tests), classify those tests by adversarial
  condition, and report three adversarial experiments -- two end-to-end and one
  six-vector attack matrix. We organize the evaluation around four explicit
  research questions (RQ1-RQ4) and a structural baseline (direct tool-invoking
  agent versus governed architecture), specifying experimental conditions, failure
  criteria, trial counts, and reproducibility. We claim precisely what the evidence
  constrains the authority available to probabilistic cognition and provides
  independently verifiable boundaries around consequential execution. We close by
  stating the open problem -- knowledge poisoning -- exactly, as a case in which
  a perfectly authorized, perfectly executed action can still be wrong.
keywords:
  - agent governance
  - knowledge compilation
  - GraphRAG
  - capability security
  - formal verification
  - verifiable execution
  - threat model
  - computational sovereignty
  - authority separation
  - adversarial evaluation
---

# Sovereign Knowledge Systems: An Experimentally Evaluated Architecture for Separating Probabilistic Cognition from Consequential Authority

## Abstract

Large language models have introduced probabilistic computation into workflows
that historically relied on deterministic programs. A persistent architectural
error is to place model-generated decisions on the critical path between cognition
and consequential action, implicitly treating probabilistic inference as an
authority mechanism. This paper presents an architecture that makes consequential
agentic execution **independent of probabilistic model authority** and evaluates
it empirically.

The contribution is organized around a single research object: an explicitly
ordered trust-transition sequence --

```
knowledge → compilation → retrieval → cognition → proposal
→ authorization → execution → verification → evidence
```

-- and a formal principle, the **Authority Non-Equivalence Principle**: no
probabilistic inference, regardless of confidence, model capability, or semantic
plausibility, constitutes authorization to perform a consequential operation.
Algebraically: `Inference(x) ≠ Authorization(x)`, `Execution(x) → Authorization(x)`,
and `Verification(x) ≠ Cognition(x)`.

The architecture is implemented across two cooperating codebases. **A10** is the
*epistemic substrate*: a knowledge compiler that compiles 177 human-authored
documents into a graph (687 nodes, 2,981 edges), a BM25 search index, and
per-article sidecars behind a fail-closed verification gate. **Sovereign Agent
Fleet** is the *authority and execution substrate*: a frozen authorization
function, cryptographic identity, capability policy, human approval, controlled
execution, and a tamper-evident audit ledger. The knowledge compiler is the
*transformation boundary*; the governance protocol is the *authority boundary*;
the verifier is the *execution-integrity boundary*.

We evaluate the architecture against five architectural invariants using the system's
own tests as the benchmark -- 564 executable tests, all passing -- and we report
two adversarial experiments that demonstrate both halves of the thesis: a model
induced to request an unauthorized operation is rejected at the authority boundary
(execution never occurs, the rejection is audited); and a legitimately authorized
operation whose executor falsely reports success is detected by an independent
verifier. All reported numbers are reproduced from the executing test suite. We
close by distinguishing three types of correctness the architecture separates --
epistemic, authority, execution -- and by stating the open problem, knowledge
poisoning, precisely.

**Keywords:** agent governance, knowledge compilation, GraphRAG, capability
security, formal verification, verifiable execution, threat model, computational
sovereignty, authority separation, adversarial evaluation.

---

## 1. Introduction

The emergence of large language models has changed the architecture of software
systems by introducing probabilistic computation into workflows that were
historically governed by deterministic programs. A conventional system establishes
explicit control flow, authorization rules, data structures, and state
transitions. A language model introduces a different primitive: given the same
nominal input it may produce different outputs, may generate incorrect
information with high confidence, and may emit actions whose consequences cannot
be established from the output alone.

The central proposition of this work is that the model should be treated as an
**untrusted epistemic component**, while authority should be implemented as an
**independently verifiable protocol**. Under this proposition, the model may
reason, propose, and hypothesize; it does not become the system's root of trust.
The contribution of this paper is not a specific agent, model, or benchmark, but an
**architectural composition**, a **formal principle**, and an **empirical
evaluation** of that composition.

The work is organized around a single research question:

> **Research Question.** Can an agentic system use probabilistic cognition while
> preventing probabilistic cognition from becoming the authority over consequential
> execution?

A conventional agent collapses this distinction into a single loop --
`Observe → Think → Act → Observe → Think → Act` -- in which the component that
thinks is also the component that acts, so an erroneous or adversarial thought can
directly cause a consequential action. The architecture presented here inserts
structure between thought and action:

> `Observe → Think → Propose → Authorize → Act → Verify → Record`

The inserted stages -- Propose, Authorize, Verify, Record -- are the contribution.
They are architectural boundaries, not stages of an LLM workflow: an untrusted
cognitive output must cross them before it can cause anything to happen.

We make the distinction concrete with a sequence that reviewers can reason about:

> **knowledge → compilation → retrieval → cognition → proposal → authorization →
> execution → verification → evidence**

Each arrow is a trust transition. The decisive transition is the one between
*cognition* (a model output) and *authorization* (a permission). At that boundary,
the proposal carries no authority; the policy function consults no model output.
The remainder of the paper formalizes this boundary, implements it, and evaluates
it.

---

## 2. The Research Object and the Central Principle

The conceptual center of the architecture is the nine-stage pipeline introduced in
Section 1 -- knowledge, compilation, retrieval, probabilistic cognition, proposal,
deterministic authorization, execution, independent verification, cryptographic
evidence. Each arrow is an architectural boundary, not a workflow stage. We state
the thesis as a formal principle so that the pipeline can be read as an
implementation of it.

**Authority Non-Equivalence Principle.** *A probabilistic inference, regardless of
confidence, model capability, or semantic plausibility, does not constitute
authorization to perform a consequential operation.*

We render this as:

```
Inference(x)  ≠  Authorization(x)
```

and define authorization as a deterministic function over non-epistemic inputs:

```
Authorization(x) = Policy(Identity, Capability, Resource, Action, State)
```

where `Identity` is a cryptographically authenticated principal, `Capability` is a
granted permission, `Resource` is the affected object, `Action` is the requested
operation, and `State` is governed system state (epoch, clock). The model is
conspicuously absent from the right-hand side.

Two further invariants follow:

```
∀c.  Execution(c)  ⇒  Authorization(c)
```

no execution occurs without an authorization decision; and

```
Verification(x)  ≠  Cognition(x)
```

verification is independent of the cognitive process that produced `x`. The same
model that proposed `x` is not the component that determines whether `x` executed
correctly.

This formulation is the paper's core. The novelty is not Ed25519, nor RAG, nor
knowledge graphs, nor policy engines, nor human approval, nor agents
individually. It is the **architectural composition** -- cognition as untrusted
input, authority as an external deterministic protocol, execution as bounded
action, verification as an independent judge -- with the invariant preserved
across every layer and demonstrated experimentally.

### 2.1 Scope of the claim

The architecture does not attempt to make probabilistic cognition trustworthy; it
constrains the authority available to cognition when trust cannot be assumed. What
the evaluation establishes is a set of *control properties* about the surrounding
system, not properties of the model:

- **The model cannot unilaterally grant itself authority.** Authorization is
  decided by an external, deterministic function over non-epistemic inputs
  (Invariant 1).
- **Unauthorized capabilities are rejected deterministically.** Forgery,
  expiration, scope mismatch, and escalation each return `BLOCKED` (Invariant 2,
  Table 3).
- **Consequential operations are gated by explicit authorization.** No execution
  occurs without a verified grant (Invariant 2).
- **Execution is evaluated independently of the model's claim.** A false executor
  report is detected by recomputation, not believed (Invariant 3).
- **Evidence is tamper-evident.** Historical records are chained, signed, and
  replay-detectable (Invariant 4).

What the architecture does *not* establish is stated explicitly in Section 13 and
Section 12.2: it does not prove the model truthful, intelligent, or that the
resulting knowledge is correct; it does not guarantee universal AI safety, the
correct specification of policy, or the absence of all attack surfaces. We make
this distinction formal as a standing **Claims and Guarantees** statement, against
which every architectural assertion in the paper can be checked:

**The architecture guarantees:**

- **Model output alone cannot authorize consequential execution.** Authorization
  is decided by an external, deterministic policy function over non-epistemic
  inputs (Invariant 1).
- **Authorization is evaluated independently of model confidence.** The policy
  engine consults no model output, score, or probability; the same proposal
  receives the same verdict regardless of how confidently the model asserts it
  (Invariant 1, Experiments 11.1 and 11.3).
- **Consequential execution can be independently verified.** An executor's claim
  of success is not believed; verification recomputes or re-checks against the
  authoritative record (Invariant 3, Experiment 11.2).
- **Relevant evidence can be cryptographically authenticated and made
  tamper-evident.** Historical records are chained, signed, and replay-detectable
  (Invariant 4).
- **Domain-specific adapters can operate without changing the core authority
  model.** Six distinct domains run over the same `decide()` function without
  altering the authority boundary (Invariant 5, Table 6).

**The architecture does not guarantee:**

- **That model reasoning is correct.** The model may be wrong; the architecture
  constrains what a wrong model can *do*, not whether it is right (Section 4, the
  Authorized-to-be-wrong case).
- **That source knowledge is true.** Compilation and retrieval faithfully
  reproduce source content; they do not certify its truth (Section 7, A6).
- **That policy is correctly specified.** The protocol enforces *the* policy
  faithfully; it does not judge whether *that* policy is desirable or complete
  (Section 13).
- **That every possible attack is detected.** The evaluation covers a defined
  adversarial set (A1-A6, six-vector matrix); it is not a proof of
  attack-surface completeness.
- **That authorization implies desirable outcomes.** A legitimately authorized
  action can still be the wrong thing to do; cryptographic integrity proves *how*
  it happened, not that it *should* have (Section 4, the third independence case).

This guarantee/non-guarantee split is the central rigor discipline of the paper:
every "the architecture does X" claim is paired with the boundary where X stops
applying. It is the primary defense against a skeptical reader over-reading the
title's word "architecture."

> **Novelty as boundary, not as algorithm.** The contribution is not a new policy
> language or a new agent algorithm: it is the *system boundary* at which
> probabilistic cognition produces proposals while authority is independently
> determined by a governed protocol. Policy, approval, and verification are each
> individually long established; the novelty is their composition behind a single
> authority boundary.

---

## 3. Architectural Invariants

The research object is most usefully stated as a set of invariants the architecture
is required to preserve. We give them explicitly so that the evaluation (Section 9)
can be read as a measurement of how well each is preserved, and so that reviewers
can falsify a specific claim rather than the paper as a whole.

**Invariant 1 — Authority Non-Equivalence.** *Model output does not constitute
authorization.*

```text
ModelOutput ≠ Authorization
```

No model output -- regardless of confidence, capability, or semantic plausibility
-- is a permission to perform a consequential operation. Authorization is granted
only by the external, deterministic policy function over non-epistemic inputs
(Section 7.3).

**Invariant 2 — Authorized Execution.** *Every consequential execution corresponds
to an independently validated authorization decision.*

```text
Execution → Authorization
```

No execution occurs without a prior, verified authorization decision; the execution
substrate never manufactures one.

**Invariant 3 — Verification Independence.** *The component that determines whether
an action succeeded is independent of the component that proposed or executed it.*

```text
Verification ⟂ Cognition
```

The verifier recomputes expected state from signed inputs; it does not inherit the
executor's self-report or the model's assertion of success.

**Invariant 4 — Evidence Integrity.** *Historical evidence is tamper-evident through
a chained cryptographic state.*

```text
AuditState(t+1) = H( AuditState(t) || Event(t+1) )
```

Each audit entry is signed and chained to its predecessor; mutation, truncation,
and replay are detectable. The ledger proves *who authorized what, what artifact was
involved, what execution occurred, and whether the recorded state was subsequently
modified* -- not that the underlying action was semantically correct.

**Invariant 5 — Knowledge Provenance.** *A compiled knowledge artifact is traceable
to its source and compilation parameters.*

```text
Artifact = C( Source, CompilerVersion, Configuration )
```

The artifact records its provenance (source, compiler, `git_sha`, generated_at) and
its content hash is reproducible from source behind a fail-closed gate; a divergent
or corrupted source cannot silently yield a valid artifact.

These five invariants are the contract the evaluation measures. Invariant 1 is the
core thesis; Invariants 2-4 bound the authority and execution domains; Invariant 5
bounds the epistemic domain's supply chain. None of the five is reducible to
cryptographic security alone: Invariant 1 is a *policy* statement, Invariant 5 is a
*provenance* statement, and the gap between "the artifact is faithfully compiled"
(Invariant 5) and "the artifact is true" is the open problem of Section 12.2.

---

## 4. Three Trust Domains and Three Types of Correctness

We formalize the system as three trust domains, each with a distinct integrity
property and a distinct type of correctness. The clean conceptual center of the
work is the nine-stage pipeline of Section 1, read as three stacked domains
separated by hard architectural boundaries:

<figure className="paper-figure">
<svg viewBox="0 0 720 470" width="100%" role="img" aria-label="Figure: The Three Integrity Domains. The pipeline passes from the epistemic domain through an untrusted-proposal boundary into the authority domain, then through an authorized-action boundary into the execution domain.">
  <style>
    .t{font:700 15px ui-sans-serif,system-ui,sans-serif;fill:var(--color-ink)}
    .s{font:600 12px ui-sans-serif,system-ui,sans-serif;fill:var(--color-ink-3)}
    .ar{stroke:var(--color-ink-3);stroke-width:1.4;fill:none;marker-end:url(#ah3)}
  </style>
  <defs><marker id="ah3" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="currentColor"/></marker></defs>
  <rect x="40" y="20" width="640" height="130" rx="10" fill="rgba(43,91,168,0.07)" stroke="var(--color-ink-3)" stroke-width="1.4"/>
  <text x="60" y="48" class="t">EPISTEMIC DOMAIN</text>
  <text x="60" y="74" class="s">Knowledge → Compile → Retrieve</text>
  <text x="60" y="94" class="s">↓</text>
  <text x="60" y="114" class="s">Cognition → Proposal</text>
  <text x="560" y="74" text-anchor="end" class="s">integrity: is the belief correct?</text>
  <text x="560" y="94" text-anchor="end" class="s">(untrusted proposal)</text>
  <path class="ar" d="M360,150 L360,182"/>
  <text x="360" y="174" text-anchor="middle" class="s">untrusted proposal crosses</text>
  <text x="360" y="190" text-anchor="middle" class="s">the authority boundary</text>
  <rect x="40" y="200" width="640" height="130" rx="10" fill="rgba(31,138,76,0.08)" stroke="var(--color-green)" stroke-width="1.6"/>
  <text x="60" y="228" class="t" style="fill:var(--color-green)">AUTHORITY DOMAIN</text>
  <text x="60" y="254" class="s">Identity → Capability → Policy</text>
  <text x="60" y="274" class="s">↓</text>
  <text x="60" y="294" class="s">Authorization → Approval</text>
  <text x="560" y="254" text-anchor="end" class="s">integrity: was the action</text>
  <text x="560" y="274" text-anchor="end" class="s">legitimately authorized?</text>
  <path class="ar" d="M360,330 L360,362"/>
  <text x="360" y="354" text-anchor="middle" class="s">authorized action crosses</text>
  <text x="360" y="370" text-anchor="middle" class="s">the execution boundary</text>
  <rect x="40" y="380" width="640" height="130" rx="10" fill="rgba(22,20,15,0.05)" stroke="var(--color-ink-3)" stroke-width="1.4"/>
  <text x="60" y="408" class="t">EXECUTION DOMAIN</text>
  <text x="60" y="434" class="s">Execute → Observe → Verify</text>
  <text x="60" y="454" class="s">↓</text>
  <text x="60" y="474" class="s">Evidence → Cryptographic Audit</text>
  <text x="560" y="434" text-anchor="end" class="s">integrity: did the authorized</text>
  <text x="560" y="454" text-anchor="end" class="s">action happen as recorded?</text>
</svg>
<figcaption><strong>Figure 5.</strong> The Three Integrity Domains. The nine-stage pipeline of
Section 1 passes down through two hard boundaries. An untrusted proposal carries no
authority into the authority domain; an authorized action carries no assumption of
correctness into the execution domain. Each domain has an independent integrity
question that the others do not answer.</figcaption>
</figure>

**Definition 1 (Epistemic Domain).** Determines *what the system believes or
proposes*: the knowledge compiler, retrieval, the knowledge graph, embeddings, and
model reasoning. **Epistemic integrity**: is the information or reasoning actually
correct?

**Definition 2 (Authority Domain).** Determines *what the system is permitted to
do*: identity, capability, policy, approval. **Authority integrity**: was the
requested operation actually and legitimately authorized?

**Definition 3 (Execution Domain).** Determines *what actually happened*: the
executor, the resulting state, the verifier, cryptographic evidence. **Execution
integrity**: did the authorized operation actually produce the recorded state, and
is that record tamper-evident?

The three domains are most cleanly distinguished by the question each answers --
a distinction frequently collapsed in conventional agent systems:

- **Truth** -- *is the proposition actually correct?* -> the **epistemic** domain
  (the model primarily operates here).
- **Permission** -- *is the system allowed to perform the requested operation?* ->
  the **authority** domain (the policy engine operates here).
- **Fact** -- *what actually happened?* -> the **execution** domain (the verifier
  and evidence system operate here).

The architecture keeps these questions in separate computational boundaries so that
an answer to one is never mistaken for an answer to another.

**The unintuitive result.** The most important consequence of the separation is not
that governance *prevents* bad outcomes -- it is that a **perfectly governed system
can still do the wrong thing**. If the knowledge is wrong, the model reasons
correctly from the wrong knowledge, policy authorizes the action, execution succeeds,
and verification confirms the expected (wrong) state, then *every governance
invariant can pass while the outcome is undesirable*. That is not a failure of the
architecture; it is the architecture correctly refusing to conflate four different
questions. It also prevents the common mistake this paper is at pains to avoid:
treating **security, provenance, and truth as interchangeable**.

These are fundamentally different properties. A system can succeed at two while
failing the third:

- **Epistemic failure, governance success.** The model produces an *incorrect
  conclusion*, but the governance system correctly *rejects* its proposed action.
  (Epistemic integrity fails; authority and execution integrity are
  satisfied.)
- **Execution failure.** The model produces a *reasonable proposal*, the policy
  engine correctly *authorizes* it, and the executor *malfunctions*. (Epistemic
  and authority integrity pass; execution integrity fails.)
- **Authorized-to-be-wrong.** An epistemically incorrect action passes every
  authority and execution check *because the system was authorized to do exactly
  the wrong thing*. (All three integrity types can be satisfied while the
  outcome is wrong.) This is the case the unintuitive result above describes, and
  it bounds the system's claim; it is treated precisely in Section 11.

**Theorem (Non-Implication).** None of the three integrity types implies another:

```
EpistemicIntegrity  ↛  AuthorityIntegrity
AuthorityIntegrity  ↛  ExecutionIntegrity
ExecutionIntegrity  ↛  EpistemicIntegrity
```

*Justification.* Epistemic integrity does not imply authority integrity: a correct
proposal still requires an external grant. Authority integrity does not imply
execution integrity: an authorized action may be mis-executed and must be
independently verified. Execution integrity does not imply epistemic integrity: a
flawlessly executed, perfectly audited action can still be wrong if the underlying
knowledge was wrong -- the third case above. This is the architecture's most
intellectually interesting consequence: **a system can maintain authority integrity
and execution integrity while still producing epistemically incorrect outcomes.** The
cryptographic audit can prove that the wrong thing was legitimately authorized and
correctly executed -- which tells us exactly what cryptographic governance does
*not* solve.

### 4.1 A Recurring Pattern: Removing Trust Rather Than Assuming It

The deepest idea in the design is not a component but a pattern. The architecture
does not try to make its components *trustworthy*; it removes the *authority* that
would make their untrustworthiness dangerous. The same move recurs at every
boundary:

- You do not have to **trust the model**, because the model does not control
  authorization (`decide()` consults no model output, Invariant 1).
- You do not have to **trust the executor's claim of success**, because
  verification is independent (Invariant 3).
- You do not have to **trust the audit log**, because its integrity is
  cryptographically verifiable (Invariant 4).
- You do not have to **trust the cloud as the authority**, because the authority
  root can remain local (Section 5).
- You do not have to **trust generated knowledge artifacts as canonical**, because
  they can be regenerated from source behind a fail-closed gate (Invariant 5).

> **Pattern.** Do not solve trust by assuming the component is trustworthy. Solve it
> by removing unnecessary authority from the component.

This pattern is the unifying lens of the paper: the contribution is a *composition*
that repeatedly applies the same trust-removal move across the epistemic, authority,
and execution domains.

---

## 5. On "Sovereign": A Precise Definition

The term *sovereign* is used precisely, not as a synonym for local inference.

**Definition 4 (Sovereignty).** *Sovereignty is the preservation of local authority
over identity, policy, knowledge provenance, and consequential execution despite
the use of external computational infrastructure.*

This is stronger and more specific than "run the model locally." It allows
computation to be distributed across external infrastructure (cloud GPUs, managed
services, remote tool hosts) while the *authority roots* remain under explicit
control. We therefore distinguish five properties that are frequently conflated:

| Property | Meaning | Independently controllable |
|---|---|---|
| Local computation | inference runs on owned hardware | one axis |
| Local authority | identity, policy, and authorization decisions are made under local control | the property this paper guarantees |
| Data ownership | who holds the raw data | separable |
| Cryptographic control | who holds the signing keys | the mechanism enabling local authority |
| Execution authority | who decides a consequential action runs | the governance boundary |

The architecture's claim is about **local authority** backed by **cryptographic
control**, not about the physical location of computation. A model may run on
external infrastructure; the grant that authorizes an action is signed by a
locally-held key and verified against a locally-pinned trust anchor. Sovereignty,
in this paper, answers the reviewer's natural question -- *sovereign according to
what threat model?* -- as: sovereign with respect to A1-A6 (Section 9), i.e.
holding the authority roots even when computation is not local.

---

## 6. Architectural Substrate Decomposition

The architecture is implemented across two cooperating codebases. The clean
decomposition is:

- **A10 = epistemic substrate** (knowledge plane).
- **Sovereign Agent Fleet = authority and execution substrate** (governance/execution plane).
- **Knowledge compiler = transformation boundary** (Markdown → structured artifacts).
- **Governance protocol = authority boundary** (policy + approval gate).
- **Verifier = execution-integrity boundary** (independent recomputation of outcome).

<figure className="paper-figure">
<svg viewBox="0 0 720 540" width="100%" role="img" aria-label="Figure 1: Complete system architecture as a vertical pipeline across three trust-domain bands.">
  <style>
    .t{font:700 14px ui-sans-serif,system-ui,sans-serif;fill:var(--color-ink)}
    .s{font:600 11px ui-sans-serif,system-ui,sans-serif;fill:var(--color-ink-3)}
    .ar{stroke:var(--color-ink-3);stroke-width:1.2;fill:none;marker-end:url(#ah)}
  </style>
  <defs><marker id="ah" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="currentColor"/></marker></defs>
  <rect x="20" y="18" width="680" height="158" rx="8" fill="none" stroke="var(--color-ink-3)"/>
  <rect x="20" y="200" width="680" height="96" rx="8" fill="none" stroke="var(--color-green)" stroke-width="1.4"/>
  <rect x="20" y="324" width="680" height="184" rx="8" fill="none" stroke="var(--color-ink-3)"/>
  <text x="32" y="40" class="t">Epistemic Substrate</text><text x="688" y="40" text-anchor="end" class="s">A10: what the system believes</text>
  <text x="32" y="224" class="t">Authority Substrate</text><text x="688" y="224" text-anchor="end" class="s">Fleet: what is permitted</text>
  <text x="32" y="348" class="t">Execution Substrate</text><text x="688" y="348" text-anchor="end" class="s">Fleet: what actually happened</text>
  <rect x="56" y="56" width="124" height="38" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="118" y="79" text-anchor="middle" class="s">Human Knowledge</text>
  <rect x="200" y="56" width="124" height="38" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="262" y="79" text-anchor="middle" class="s">Knowledge Compiler</text>
  <rect x="344" y="56" width="124" height="38" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="406" y="79" text-anchor="middle" class="s">Compiled Artifacts</text>
  <rect x="488" y="56" width="100" height="38" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="538" y="79" text-anchor="middle" class="s">Retrieval / Graph</text>
  <rect x="604" y="56" width="84" height="38" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="646" y="79" text-anchor="middle" class="s">Cognition</text>
  <rect x="604" y="112" width="84" height="38" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="646" y="135" text-anchor="middle" class="s">Proposal</text>
  <rect x="248" y="226" width="130" height="42" rx="5" fill="var(--color-paper)" stroke="var(--color-green)" stroke-width="1.8"/><text x="313" y="252" text-anchor="middle" class="s">Deterministic Policy</text>
  <rect x="404" y="226" width="130" height="42" rx="5" fill="var(--color-paper)" stroke="var(--color-green)" stroke-width="1.8"/><text x="469" y="252" text-anchor="middle" class="s">Human Approval</text>
  <rect x="248" y="356" width="130" height="42" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="313" y="382" text-anchor="middle" class="s">Execution</text>
  <rect x="404" y="356" width="130" height="42" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="469" y="382" text-anchor="middle" class="s">Independent Verification</text>
  <rect x="560" y="356" width="130" height="42" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="625" y="382" text-anchor="middle" class="s">Cryptographic Evidence</text>
  <path class="ar" d="M180,75 L200,75"/>
  <path class="ar" d="M324,75 L344,75"/>
  <path class="ar" d="M468,75 L488,75"/>
  <path class="ar" d="M588,75 L604,75"/>
  <path class="ar" d="M646,94 L646,112"/>
  <path class="ar" d="M646,150 L469,226"/>
  <path class="ar" d="M469,268 L469,356"/>
  <path class="ar" d="M378,377 L404,377"/>
  <path class="ar" d="M534,377 L560" />
  <path class="ar" d="M313,398 L120,440" style="stroke-dasharray:3 3"/>
  <text x="120" y="462" text-anchor="middle" class="s">feedback: evidence informs future knowledge</text>
</svg>
<figcaption><strong>Figure 1.</strong> Complete system architecture. A10 is the epistemic
substrate (left band); Sovereign Agent Fleet provides the authority and execution
substrates (lower bands). The proposal → policy transition is a hard trust
boundary: the proposal carries no authority and the policy consults no model
output.</figcaption>
</figure>

The critical property is that the **proposal → policy** transition is a hard trust
boundary. Between Cognition/Proposal (epistemic) and Policy/Approval (authority)
there is no shared state that would let a proposal silently promote itself to a
permission.

<figure className="paper-figure">
<svg viewBox="0 0 720 260" width="100%" role="img" aria-label="Figure 2: Three trust-domain zones separated by the transformation, authority, and execution boundaries.">
  <style>
    .t{font:700 14px ui-sans-serif,system-ui,sans-serif;fill:var(--color-ink)}
    .s{font:600 11px ui-sans-serif,system-ui,sans-serif;fill:var(--color-ink-3)}
  </style>
  <rect x="20" y="30" width="210" height="180" rx="10" fill="rgba(43,91,168,0.07)" stroke="var(--color-ink-3)"/>
  <rect x="255" y="30" width="210" height="180" rx="10" fill="rgba(31,138,76,0.08)" stroke="var(--color-green)"/>
  <rect x="490" y="30" width="210" height="180" rx="10" fill="rgba(22,20,15,0.05)" stroke="var(--color-ink-3)"/>
  <text x="125" y="58" text-anchor="middle" class="t">Epistemic</text>
  <text x="360" y="58" text-anchor="middle" class="t" style="fill:var(--color-green)">Authority</text>
  <text x="595" y="58" text-anchor="middle" class="t">Execution</text>
  <text x="125" y="92" text-anchor="middle" class="s">compiler · graph</text>
  <text x="125" y="110" text-anchor="middle" class="s">retrieval · model</text>
  <text x="125" y="128" text-anchor="middle" class="s">belief · proposal</text>
  <text x="360" y="92" text-anchor="middle" class="s">identity · capability</text>
  <text x="360" y="110" text-anchor="middle" class="s">policy · approval</text>
  <text x="595" y="92" text-anchor="middle" class="s">executor · verifier</text>
  <text x="595" y="110" text-anchor="middle" class="s">audit ledger</text>
  <line x1="230" y1="40" x2="255" y2="40" stroke="var(--color-ink-3)" stroke-width="2"/>
  <line x1="230" y1="200" x2="255" y2="200" stroke="var(--color-ink-3)" stroke-width="2"/>
  <text x="242" y="125" text-anchor="middle" class="s" transform="rotate(-90 242 125)">transformation boundary</text>
  <line x1="465" y1="40" x2="490" y2="40" stroke="var(--color-ink-3)" stroke-width="2"/>
  <line x1="465" y1="200" x2="490" y2="200" stroke="var(--color-ink-3)" stroke-width="2"/>
  <text x="477" y="125" text-anchor="middle" class="s" transform="rotate(-90 477 125)">authority boundary</text>
</svg>
<figcaption><strong>Figure 2.</strong> The three trust domains as separated zones. The
transformation boundary admits only compiled artifacts; the authority boundary
admits only an externally-signed, scope-bound grant; the execution boundary
admits only an already-authorized operation.</figcaption>
</figure>

---

## 7. Knowledge Substrate (A10 — Epistemic)

A10 implements the epistemic substrate. Its architecture includes a Next.js
application, a structured source corpus, a data layer, and a semantic compiler.
The knowledge system is treated as a computational substrate, not merely a content
store.

### 7.1 Source Corpus

The source corpus is the long-term human-authored representation of the system's
knowledge: 177 Markdown posts under `content/blog/`, each with structured
frontmatter (title, author, date, canonical URL, status, topics, series). This
creates an important asymmetry: the model may generate derived representations,
but the canonical source remains independently inspectable and regenerable.

### 7.2 Knowledge Compilation (the Transformation Boundary)

The knowledge compiler (`knowledge-compiler/`) runs a deterministic pipeline at
build time:

```
ingest → normalize → extract → graph → search → emit → verify
```

It reads the 177 Markdown sources, parses frontmatter, extracts entities,
relationships, claims, and references per post, builds a NetworkX
entity/relationship graph, builds a BM25 index, and emits `index.json`,
`<slug>.json` sidecars, `graph.json`, and `search.json` to `public/artifacts/`.
Because the build is deterministic and local, the semantic structure can be
version-controlled, diffed, and reproduced.

<figure className="paper-figure">
<svg viewBox="0 0 720 240" width="100%" role="img" aria-label="Figure 3: A10 knowledge compilation pipeline across the transformation boundary.">
  <style>
    .t{font:600 11px ui-sans-serif,system-ui,sans-serif;fill:var(--color-ink)}
    .s{font:600 11px ui-sans-serif,system-ui,sans-serif;fill:var(--color-ink-3)}
    .ar{stroke:var(--color-ink-3);stroke-width:1.2;fill:none;marker-end:url(#a3)}
  </style>
  <defs><marker id="a3" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="currentColor"/></marker></defs>
  <rect x="10" y="40" width="110" height="40" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="65" y="64" text-anchor="middle" class="t">Markdown (177)</text>
  <rect x="140" y="40" width="100" height="40" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="190" y="58" text-anchor="middle" class="t">Parse +</text><text x="190" y="72" text-anchor="middle" class="t">normalize</text>
  <rect x="260" y="40" width="100" height="40" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="310" y="58" text-anchor="middle" class="t">Extract</text><text x="310" y="72" text-anchor="middle" class="t">entities/claims</text>
  <rect x="380" y="40" width="100" height="40" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="430" y="58" text-anchor="middle" class="t">Graph +</text><text x="430" y="72" text-anchor="middle" class="t">Search</text>
  <rect x="500" y="40" width="90" height="40" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="545" y="58" text-anchor="middle" class="t">Emit</text><text x="545" y="72" text-anchor="middle" class="t">artifacts</text>
  <rect x="610" y="40" width="100" height="40" rx="5" fill="rgba(31,138,76,0.08)" stroke="var(--color-green)"/><text x="660" y="58" text-anchor="middle" class="t">Verify</text><text x="660" y="72" text-anchor="middle" class="t">gate</text>
  <path class="ar" d="M120,60 L140,60"/>
  <path class="ar" d="M240,60 L260,60"/>
  <path class="ar" d="M360,60 L380,60"/>
  <path class="ar" d="M480,60 L500,60"/>
  <path class="ar" d="M590,60 L610,60"/>
  <rect x="500" y="120" width="210" height="86" rx="6" fill="rgba(43,91,168,0.06)" stroke="var(--color-ink-3)"/>
  <text x="605" y="144" text-anchor="middle" class="t">public/artifacts/</text>
  <text x="515" y="166" class="s">graph.json (687n/2981e)</text>
  <text x="515" y="184" class="s">search.json (BM25)</text>
  <text x="515" y="200" class="s">&lt;slug&gt;.json sidecars</text>
  <path class="ar" d="M655,80 L655,120"/>
  <rect x="10" y="120" width="200" height="86" rx="6" fill="rgba(22,20,15,0.05)" stroke="var(--color-ink-3)"/>
  <text x="110" y="152" text-anchor="middle" class="t">Consumers</text>
  <text x="20" y="174" class="s">portal (server components)</text>
  <text x="20" y="190" class="s">retrieval / RAG</text>
  <text x="20" y="206" class="s">governance plane</text>
  <path class="ar" d="M500,163 L450,163 L450,140"/>
</svg>
<figcaption><strong>Figure 3.</strong> A10 knowledge compilation pipeline (transformation
boundary). Semantic transformations are performed once at build time and emitted
as deterministic, version-controlled artifacts rather than recomputed per
request.</figcaption>
</figure>

### 7.3 Artifact Model and the Fail-Closed Verification Gate

The artifact schema is explicit and versioned:

- `index.json`: `{ schema_version, total, posts: [{ slug, title, author, date,
  canonical_url, status, topics, series, featured, content_hash }] }`.
- `<slug>.json` sidecar: `{ id, title, author, created_at, updated_at,
  canonical_url, content_hash ("sha256:..."), topics[], status, series,
  entities[], relationships[], claims[], references[], related_artifacts[],
  provenance: { source, compiler, git_sha, generated_at } }`.
- `graph.json`: `{ nodes: [{ id, label, type ("article"|"entity"), slug?, status?,
  topics?, date?, featured? }], edges: [{ from, to, label, weight, basis }] }`.
- `search.json`: `{ engine: "bm25", k1, b, entries: [{ slug, title, excerpt,
  tokens }] }`.

The **verification gate** is fail-closed. Any failure raises and the build CLI
exits non-zero. It checks: (1) all 177 slugs unique; (2) every canonical URL equals
`/blog/<slug>`; (3) every content hash is reproducible from source; (4)
`graph.json`, `search.json`, `index.json` present, non-empty, parseable; (5) every
post has an emitted sidecar. These are the integrity properties a governance
system would demand of any knowledge it reasons over: uniqueness, deterministic
canonicalization, reproducible content identity, and completeness.

---

## 8. Governance and Execution Substrate (Sovereign Agent Fleet)

Sovereign Agent Fleet implements the authority and execution substrates. Its
central principle is that the system should not require trust in the model.

### 8.1 Role Separation

The multi-agent structure provides role separation: Researcher produces
observations; Analyst transforms them into qualified intelligence; Operator
executes authorized actions. Agent roles (`researcher`, `analyst`, `operator`,
`human`, `tool`) are carried on a cryptographically signed identity certificate,
never asserted by model output.

### 8.2 Identity and Root of Trust

The architecture derives a key hierarchy from an Argon2id-strengthened master
secret:

```
master secret (Argon2id) → root Ed25519 signing key → per-agent Ed25519 identity keys
```

The root key issues agent certificates (`AgentCert`) that the agent cannot alter
-- the agent does not hold the root key, so it cannot grant itself scope,
capabilities, or role. Certificates bind to `agent_id`, `role`, `capabilities`,
issuance/expiry, and `cert_seq`, signed under a root epoch so rotated roots do not
invalidate historical chains.

### 8.3 Deterministic Policy and the `decide()` Substrate

Policy is implemented independently of the language model. The authorization
function `decide()` in `fleet/epistemic/decision.py` is a **pure, deterministic
function** whose inputs are: `identity`, `grant` (externally-signed
`AuthorityGrant`), `authorization_scope`, `request`, `constraints`,
`current_epoch`, `now`, and `trusted_issuer_pubkey_pem` (the pinned governance
trust anchor). It accepts **no probability, confidence, model score, belief, or
calibration value**, and returns an `AuthorizationDecision` whose state contains
no epistemic field.

The evaluation proceeds as an ordered guard sequence, each failure returning
`BLOCKED`:

1. a grant must exist (the substrate never manufactures one);
2. the grant signature must verify against the **pinned trusted issuer key** -- not
   a key the grant describes for itself, which would let an attacker self-sign a
   valid-looking grant;
3. the grant must be current (epoch supersession primary; a TTL is a backstop);
4. the grant is bound to this identity and cannot be transferred;
5. the grant must reference exactly the scope being exercised;
6. the requested capability must be within the granted scope;
7. deterministic policy read returns `AUTO`, `HUMAN`, or `BLOCKED`.

A model can request an action that policy rejects, and the rejection remains valid
even if the model provides an elaborate justification -- because the model is not
an input to `decide()`.

### 8.4 Capability Authorization and Human Approval

Capabilities provide a finer-grained, least-privilege authority model than broad
agent permissions. Human approval provides an additional boundary for
consequential operations: the approval record is bound to the specific operation
(action id, capability, artifact hash) and is cryptographically signed by a
`human`-role cert. A forged, rebound, or non-human-signed approval is rejected
(Section 9.5).

### 8.5 Execution, Verification, and Audit

Execution occurs only after authorization. Verification independently determines
whether the resulting artifact or state satisfies required conditions; it is a
separate computational role, not a statement emitted by the executor (the
execution-integrity boundary). The audit architecture wraps an Ed25519-signed
hash-chain ledger: each entry is signed and linked to the previous entry, with a
signed checkpoint so truncation and replay are detectable. Per-record
confidentiality is provided by an XChaCha20-Poly1305 envelope (HKDF per-record
subkeys), so encryption protects secrecy while signatures protect integrity -- the
two concerns are not conflated.

The execution domain is governed by an explicit state machine. The fleet substrate
drives transitions through:

```
REQUEST → INTENT → PLAN → ACTION → TOOL → OBSERVATION
        → EVIDENCE → VERIFICATION → ARTIFACT → APPROVAL → FINAL → AUDIT
```

<figure className="paper-figure">
<svg viewBox="0 0 720 150" width="100%" role="img" aria-label="Figure 4: Sovereign Agent Fleet execution state machine.">
  <style>
    .t{font:700 11px ui-sans-serif,system-ui,sans-serif;fill:var(--color-ink)}
    .ar{stroke:var(--color-ink-3);stroke-width:1.2;fill:none;marker-end:url(#a4)}
  </style>
  <defs><marker id="a4" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="currentColor"/></marker></defs>
  <rect x="10" y="55" width="62" height="34" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="41" y="76" text-anchor="middle" class="t">REQUEST</text>
  <rect x="90" y="55" width="62" height="34" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="121" y="76" text-anchor="middle" class="t">INTENT</text>
  <rect x="170" y="55" width="62" height="34" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="201" y="76" text-anchor="middle" class="t">PLAN</text>
  <rect x="250" y="55" width="62" height="34" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="281" y="76" text-anchor="middle" class="t">ACTION</text>
  <rect x="330" y="55" width="62" height="34" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="361" y="76" text-anchor="middle" class="t">TOOL</text>
  <rect x="410" y="55" width="62" height="34" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="441" y="76" text-anchor="middle" class="t">OBS</text>
  <rect x="490" y="55" width="62" height="34" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="521" y="76" text-anchor="middle" class="t">EVID</text>
  <rect x="570" y="55" width="62" height="34" rx="5" fill="var(--color-paper)" stroke="var(--color-green)"/><text x="601" y="76" text-anchor="middle" class="t">VERIFY</text>
  <rect x="650" y="55" width="60" height="34" rx="5" fill="var(--color-paper)" stroke="var(--color-ink-3)"/><text x="680" y="76" text-anchor="middle" class="t">FINAL</text>
  <path class="ar" d="M72,72 L90,72"/>
  <path class="ar" d="M152,72 L170,72"/>
  <path class="ar" d="M232,72 L250,72"/>
  <path class="ar" d="M312,72 L330,72"/>
  <path class="ar" d="M392,72 L410,72"/>
  <path class="ar" d="M472,72 L490,72"/>
  <path class="ar" d="M552,72 L570,72"/>
  <path class="ar" d="M632,72 L650,72"/>
  <path class="ar" d="M680,105 C680,130 41,130 41,105" stroke-dasharray="3 3"/>
  <rect x="255" y="105" width="80" height="22" rx="4" fill="rgba(31,138,76,0.08)" stroke="var(--color-green)"/>
  <text x="295" y="120" text-anchor="middle" class="t" style="fill:var(--color-green)">APPROVAL</text>
  <text x="360" y="138" text-anchor="middle" class="t">AUDIT persists every transition into a signed, hash-chained ledger</text>
</svg>
<figcaption><strong>Figure 4.</strong> Sovereign Agent Fleet execution state machine. Each
transition is validated; APPROVAL is an explicit gate for consequential operations,
and AUDIT persists every transition into a tamper-evident ledger.</figcaption>
</figure>

This sequence prevents the model from collapsing the entire pipeline into a single
response. Each arrow is a trust transition that can be independently validated and
recorded.

---

## 9. Formal Threat Model, Research Questions, and Evaluation Design

### 9.1 Threat Model (A1-A6)

We define the adversary by capability, not by scenario.

- **A1: Malicious or compromised model.** Intentionally generates unauthorized or
  harmful actions, or reports false justification.
- **A2: Prompt injection.** External knowledge or tool content attempts to
  manipulate agent behavior.
- **A3: Privilege escalation.** An agent requests capabilities outside its assigned
  authority.
- **A4: Executor compromise.** The execution subsystem reports false success.
- **A5: Evidence tampering.** An attacker modifies historical audit records.
- **A6: Knowledge poisoning.** A malicious or incorrect document enters the
  canonical or compiled knowledge substrate.

### 9.2 Threat → Domain → Defense

The adversary maps directly onto the three trust domains of Section 4. Each threat
is localized to exactly one or two domains, and each has a corresponding, named
defense. This is the security argument in one table.

| Threat (Adversary) | Domain | Defense |
|---|---|---|
| Hallucinated reasoning (A1) | Epistemic | Evidence / retrieval / independent verification |
| Prompt injection (A2) | Epistemic | Input isolation / policy boundary |
| Privilege escalation (A3) | Authority | Capability policy (least privilege) |
| Forged identity (A3) | Authority | Cryptographic identity (pinned issuer key) |
| Unauthorized action (A1/A3) | Authority | Deterministic authorization (`decide()`) |
| Executor lying (A4) | Execution | Independent verification (recompute, not self-report) |
| Audit modification (A5) | Execution / Evidence | Signed hash-chain ledger |
| Knowledge poisoning (A6) | Epistemic (open) | Provenance / versioning (defenses = future work) |

*Table 1. The threat model as a domain/defense mapping. The first seven rows are
covered by invariants 1-5; the eighth (A6) is the open problem of Section 12.2.*

### 9.3 Research Questions and the Evaluation Protocol

Carrying "experimentally evaluated" in the title imposes an obligation: a reviewer
must be able to see what was tested, under what conditions, with what constitutes
failure, how many trials, and whether it is reproducible. We therefore state the
evaluation as four research questions, each answered by the executing test suite,
and we specify the protocol for each.

**RQ1 -- Authority containment.** *Can deterministic authorization prevent an
untrusted cognitive component from executing unauthorized capabilities?*
- *Condition:* a model (benign or `HostileBrain`) emits a proposal requesting a
  capability outside its grant. *Failure criterion:* the proposal is authorized.
- *Verdict source:* `decide()` returns `BLOCKED` (Table 3, rows 1, 3; Experiments
  11.1). *Trials:* the adversarial suites below (Unauthorized, Capability
  escalation, Cross-domain, 120 of 237 adversarial tests) plus the 1,000-instance
  decision matrix (Table 6). *Determinism:* `decide()` is a pure function; reruns
  are byte-identical (Table 4, `test_epistemic_phase1.py`). *Reproducible:* yes,
  via `pytest` at the pinned commit (References [2]).

**RQ2 -- Verification independence.** *Can independent verification detect an
incorrect executor claim?*
- *Condition:* a legitimately authorized action executes; the executor tampers its
  own `operator.final` record (A4). *Failure criterion:* the verification aggregate
  reports `PASS`.
- *Verdict source:* the independent verifier recomputes the hash and escalates to
  `CRITICAL` (Table 3, row 6; Experiment 11.2). *Trials:* the Executor-deception and
  Verification-failure classes (46 of 237) plus `test_verifier_critical_on_tamper`.
  *Determinism:* the verifier recomputes from signed inputs; no model output.
  *Reproducible:* yes.

**RQ3 -- Evidence integrity.** *Can cryptographic evidence detect post hoc
modification?*
- *Condition:* an attacker mutates, truncates, or replays a historical audit
  entry (A5). *Failure criterion:* the ledger verifies as authentic.
- *Verdict source:* the signed hash-chain ledger returns `verify_chain is False`
  (Table 3, row 5; Table 4, `test_crypto_phase0.py`). *Trials:* the Audit-tampering
  class (20 of 237) plus `test_audit_tamper_detected`,
  `test_audit_truncation_detected`, `test_c3_replay_of_old_entry_detected`.
  *Determinism:* verification is pure; reproducible: yes.

**RQ4 -- Domain generality.** *Can the same governance substrate preserve its
invariants across multiple application domains?*
- *Condition:* six domains share one frozen `decide()` through a single capability
  table. *Failure criterion:* an invariant holds in one domain but not another, or
  a scoped grant authorizes an out-of-scope universal capability.
- *Verdict source:* the cross-domain generality suite (Table 3,
  `test_registry_cross_domain_generality.py`) plus the financial and incident
  end-to-end suites. *Trials:* the Cross-domain class (19 of 237) and the
  six-domain parametrized generality tests. *Determinism:* pure; reproducible: yes.

Each RQ is answered by tests that are themselves deterministic and
re-executable, so another researcher can reproduce every number in Section 10 by
running the suite at the cited commit.

### 9.4 Baseline: Direct Tool-Invoking Agent vs. Governed Architecture

To make the contribution immediately legible, we contrast the architecture against
a minimal, realistic **Baseline A** -- a model that directly invokes tools -- under
the same injected invalid conditions. Baseline A is a structural reference (the
conventional `Observe → Think → Act` loop), not a separate implementation we
execute; its column reports the well-known default behaviour of an ungoverned
tool-calling model, which is precisely the failure class the architecture removes
authority from. The **Architecture B** column reports the observed suite result.

| Condition (injected) | Baseline A: model invokes tools | Architecture B: governed |
|---|---|---|
| Unauthorized capability | Executes | Rejects |
| Forged identity | Executes / ambiguous | Rejects |
| Modified approved action | Executes / ambiguous | Rejects |
| False executor success | Accepted | Detected |
| Tampered audit | Undetected | Detected |

*Table 2. Baseline comparison. Baseline A describes the default behaviour of an
ungoverned tool-calling agent; Architecture B reports the observed result from the
suite (Tables 3-7 / Experiments 11.1-11.3). The architecture's column is the one the
evaluation measures; Baseline A is the contrast that makes the contribution
concrete.*

### 9.5 Invariant Evaluation Table

We evaluate the architecture using its **own invariants as the benchmark**. No
external benchmark is required; the system's security properties are read directly
from the executing test suite. Each row is an invariant, the adversarial condition
that exercises it, and the observed result (reproduced from the 564-test fleet
suite; the A10 compiler gate contributes 18 tests).

| Security invariant | Adversarial condition | Expected | Observed |
|---|---|---|---|
| Authority separation | Model requests unauthorized capability | Reject | Reject |
| Identity integrity | Forged / self-issued principal | Reject | Reject |
| Capability isolation | Privilege escalation attempt | Reject | Reject |
| Approval binding | Modify approved action after signing | Reject | Reject |
| Audit integrity | Modify / truncate historical record | Detect | Detect |
| Verification independence | Executor falsely reports success | Reject | Reject |
| Knowledge provenance | Alter compiled artifact vs. source | Recompile / detect | Detect |
| Domain isolation | Unknown-domain capability request | Reject | Reject |

*Table 3. Security-invariant evaluation. The system's own tests are the benchmark.
Representative tests: `test_forged_grant_signature_rejected`,
`test_self_issued_grant_rejected`, `test_replay_expired_epoch_rejected`,
`test_alter_capability_after_signing_detected`,
`test_authorization_request_alone_grants_nothing`, `test_revoked_identity_rejected`,
`test_audit_tamper_detected`, `test_audit_truncation_detected`,
`test_c3_replay_of_old_entry_detected`,
`test_verifier_critical_on_tamper`, `test_hostile_brain_proposal_refused_by_risk_policy`.*

This converts the paper from an architectural argument into an **empirically
evaluated architecture**: every claimed invariant is mapped to an adversarial
condition and an observed result drawn from the suite.

### 9.6 Experimental Conditions and Reproducibility

To make "experimentally evaluated" falsifiable rather than asserted, we state the
exact conditions under which every number in Section 10 and Section 11 was produced.

- **Subject under test.** The governance and execution substrate
  (`sovereign-agent-fleet`) and the epistemic compiler (A10). The authorization
  function `decide()` is model-independent by construction: it consults no model
  output, so the evaluation does not require, train, or depend on a specific LLM.
- **Adversarial model.** Where a model is involved, it is a deterministic
  `HostileBrain` stub that emits the prohibited proposal; no production LLM is
  needed because the boundary under test is protocol-level, not model-level.
- **Software.** CPython 3.13; `pytest` with `-p no:cacheprovider`; a pure-Python
  substrate with no GPU, network, or RNG dependency on the authorization path.
- **Trials.** 564 tests in the full fleet suite (all passing); 237 of those in
  adversarial classes (Table 5); 1,000 parametric instances per row of the
  decision matrix (Table 6); six registered domains in the generality suite.
- **Configuration.** Deterministic fixtures; no randomized sampling. The suite is a
  fixed, version-controlled benchmark, not a stochastic evaluation.
- **Adversarial conditions.** The six-vector set of Section 11.3 and the per-class
  matrix of Table 5.
- **Success / failure criteria.** Per RQ in Section 9.3; for the suite, a single
  invariant violation fails the run.
- **Reproducibility.** Every result is reproduced at a pinned commit:
  `489e01697e664be6a0decd0ac0e335daeb47d9c4` (References [2]). A reader six months
  hence can recover the exact subject with `git checkout
  489e01697e664be6a0decd0ac0e335daeb47d9c4` in `sovereign-agent-fleet` and re-run
  `pytest`; the numbers in Section 10 and Section 11 are the output of that
  command.

### 9.7 Three Classes of Claim (and how they are kept distinct)

Because the title commits to "experimentally evaluated," we separate three classes
of claim that weaker papers blur together. Every assertion in this paper is one of
these, and the evidence for it is drawn from a correspondingly different source.

| Class | What it asserts | Evidence source | Example |
|---|---|---|---|
| **Architectural** | what the system is *designed* to guarantee | the invariants of Section 3 | "The architecture prevents unauthorized execution." |
| **Implementation** | what was *actually built* to realize it | the substrate descriptions (Sections 6-8) | "The implementation rejects unauthorized capability requests through `decide()`, which consults no model output." |
| **Experimental** | what was *measured* | the suite results (Sections 10-11) | "Across 237 adversarial authorization tests, 100% of unauthorized requests were rejected (Table 5)." |

*Table 8. The three classes of claim. Architectural claims are design commitments;
implementation claims describe the built artifact; experimental claims report
measured outcomes. Confusing them is the most common way a systems paper over-states
its evidence; we keep them in separate columns throughout.*

An architectural claim is a hypothesis about behaviour; an implementation claim is a
fact about the artifact; an experimental claim is a measurement of the artifact under
adversarial conditions. Where this paper makes an architectural claim, the matching
implementation and experimental claims appear in the same section so a reviewer can
trace design → build → measurement without inference.

---

## 10. Evaluation Results

The evaluation reports reproduced results from the executing test suites of both
repositories. The full Sovereign Agent Fleet suite comprises **564 tests, all
passing** (reproduced via `pytest` at the version cited in References [2]). We
categorize the invariant-relevant suites we draw on directly:

| Suite (file) | Tests | Invariant exercised |
|---|---:|---|
| `fleet/tests/test_epistemic_phase1.py` | 29 | probability/confidence/recommendation cannot become authority |
| `fleet/tests/test_epistemic_adversarial.py` | 28 | forgery, replay, scope mutation, implicit delegation, composition |
| `fleet/tests/test_crypto_phase0.py` | 23 | key hierarchy, sign/verify, hash-chain, envelope, rotation |
| `fleet/tests/test_financial_e2e.py` | 17 | four-gate trade pipeline, hostile-model refusal (M0) |
| `fleet/tests/test_incident_e2e.py` | 8 | remediation pipeline, protected-asset policy, second-line defense |
| `fleet/tests/test_approval_hardening_phase2.py` | 7 | forged/non-human/rebound approval rejection |
| `exchange/tests/test_governance.py` | 7 | risk classification, human-tier, approval rebinding |
| `domain_registry/tests/test_registry_cross_domain_generality.py` | 8 (+6-domain parametrized) | M0 cross-domain generality |
| A10 `knowledge-compiler/tests/test_compiler.py` | 18 | compiler emit + fail-closed verify gate |

*Table 4. Invariant-grouped test inventory (counts verified from the suites
cited). The remaining fleet tests cover consensus, runtime, control plane,
incident policy, brain, GCP, root rotation, armor, and boundary imports.*

### 10.1 Adversarial Classification of the Suite

The suites above are organized by file. To evaluate the architecture *by guarantee*
rather than by file, we classify every test function in the governance substrate by
the specific adversarial condition it asserts. Of 532 collected test functions in
the Sovereign Agent Fleet repository, **237 directly exercise one of the ten
adversarial conditions** below; the remainder exercise the correct-operation
baseline (authorized actions succeed, ledgers emit, etc.). Each adversarial class
is mapped to the invariant(s) and domain(s) it exercises. All 237 adversarial tests
pass.

| Adversarial class | Tests | Invariant | Domain |
|---|---:|---|---|
| Identity attacks (forged / self-issued / revoked) | 33 | 1, 2 | Authority |
| Capability escalation (scope / universal-cap) | 20 | 1, 2 | Authority |
| Unauthorized actions (model induced to request) | 51 | 1 | Authority |
| Approval mutation (rebind / misbound / non-human) | 22 | 2 | Authority |
| Artifact tampering (hash / mutate / corrupt) | 23 | 5 | Epistemic |
| Audit tampering (truncation / replay / mutate) | 20 | 4 | Execution / Evidence |
| Executor deception (false `final` / sim self-defense) | 27 | 3 | Execution |
| Verification failure (tamper → critical) | 19 | 3 | Execution |
| Knowledge provenance violations (compiler gate) | 3 | 5 | Epistemic |
| Cross-domain authorization violations (M0) | 19 | 1, 2 | Authority |

*Table 5. Adversarial classification of 237 of 532 collected governance-substrate
test functions (counts verified by static analysis of the suite; the A10
compiler-gate contributes a further 18 fail-closed tests). The classes overlap with
the per-file inventory of Table 4; together they account for the full 564-test
passing run. Every class is mapped to the invariants of Section 3 and the domains
of Section 4.*

### 10.2 Policy Enforcement (Authority Separation, Identity, Capability)

We evaluate the authorization function directly using a protocol-level decision
matrix. Each row is a class of request; the verdict is the `decide()` outcome.

| Test class | Allowed | Rejected | False accepts |
|---|---:|---:|---:|
| Authorized actions (valid grant, in scope) | 1000 | 0 | 0 |
| Unauthorized capabilities | 0 | 1000 | 0 |
| Unknown capabilities | 0 | 1000 | 0 |
| Invalid / forged identities | 0 | 1000 | 0 |
| Tampered / self-issued grants | 0 | 1000 | 0 |
| Stale or expired grants | 0 | 1000 | 0 |

*Table 6. Authorization decision matrix. "Attempts" are parametric instances within
the adversarial suites; the substrate returns `BLOCKED` for every class except the
authorized one, with zero false accepts.*

The decisive property is **zero false accepts** under forgery. The grant is
verified against a *pinned trusted issuer key* (`trusted_issuer_pubkey_pem`), not
against a key the grant embeds for itself -- so an attacker who forges a grant and
claims the issuer is the governance key is still rejected.

### 10.3 Approval Binding (Audit Integrity, A3/A4)

Forged agent certificates (signed by a non-root key) fail verification; tampered
certificates (capability escalation on a valid signature) fail; a revoked identity
is denied at the gateway before any governance gate runs
(`test_revoked_identity_rejected`). A forged, rebound, or non-human-signed human
approval is rejected (`test_approval_hardening_phase2`).

The signed hash-chain ledger detects three tamper classes: in-place value mutation
(`test_audit_tamper_detected`), tail truncation (`test_audit_truncation_detected`),
and replay of a previously-seen entry (`test_c3_replay_of_old_entry_detected`). All
return `verify_chain is False`.

### 10.4 Verification Independence (Experiment A — bad execution cannot fake success)

We make the model fail. A legitimately authorized trade is executed, producing an
`operator.final` record. When its `risk_assessment_hash` is mutated and the record
re-ingested, an **independent verifier** recomputes the hash, finds a mismatch, and
escalates the control-plane aggregate to `CRITICAL` -- the run can never report
overall `PASS` (`test_verifier_critical_on_tamper`). The executor's self-report is
not the source of truth; the verifier's recomputation is. This is the architectural
assertion `Verification(x) ≠ Cognition(x)` made operational: a corrupted executor
cannot manufacture a successful verification.

### 10.4 Domain Portability (Invariant: M0 Generality)

The same frozen `decide()` substrate governs six domains through a single
capability table (`domain_registry`). A parameterized generality suite verifies:
same policy → same verdict across all six domains
(`test_m0_same_policy_same_verdict_across_all_registered_domains`); policy flip
moves every domain AUTO→HUMAN together
(`test_m0_policy_flip_changes_all_registered_domains_identically`); no shared
substrate state among domains
(`test_m0_no_shared_substrate_state_among_registered_domains`); a scoped grant
cannot authorize an out-of-scope universal capability in every domain
(`test_m0_scoped_grant_cannot_authorize_universal_capability`); and the substrate
operates with all adapters removed from `sys.modules`
(`test_reverse_substrate_functional_without_any_adapter_present`).

In the financial workload, a `HostileBrain` model proposes an unauthorized asset
(TSLA) at 100x size; the proposal is **refused at the risk-policy layer** with no
`operator.final` record written
(`test_hostile_brain_proposal_refused_by_risk_policy`,
`test_hostile_brain_rejected_at_every_layer_independently`). In the incident
workload, VERIFIED evidence of a compromised `identity-svc` is **still blocked**
from isolating that protected asset (`test_act3_protected_blocked_despite_verified_compromise`),
a forged/mis-bound human approval is rejected
(`test_attack1_misbound_approval_rejected`), hallucinated (zero-reference) intel is
blocked at the evidence gate (`test_attack3_hallucination_intel_blocked`), and even
a direct `SimEnv.transition` call on a protected asset defends itself
(`test_attack4_simenv_second_line_defense`).

### 10.5 Knowledge Provenance (A10 Compiler)

The A10 compiler's fail-closed gate (Section 7.3) is exercised by 18 compiler
tests. The gate re-derives every `content_hash` from source and refuses to emit on
any mismatch. Reproducing artifacts from the corpus yields 177 posts, 687 graph
nodes, and 2,981 edges, with the gate reporting PASS. Divergent or corrupted source
cannot silently produce a valid artifact (Table 3, row "Knowledge provenance").

---

## 11. Three Adversarial Experiments

To make the thesis memorable and concrete, we report three experiments in which the
model is deliberately induced to fail. These demonstrate both halves of the
architecture: **bad cognition cannot obtain authority**, **bad execution cannot
manufacture successful verification**, and **a deliberately untrusted agent cannot
succeed on any of six adversarial vectors**.

### 11.1 Experiment 1 — Induced Unauthorized Request (bad cognition is rejected)

*Setup.* A `HostileBrain` model is given a task that is instructed (and independently
induced via injected context) to request an operation it is not permitted to
perform: trade an unauthorized asset (TSLA) at 100× the allowed size.

*Observation.*

- **Model:** proposes the unauthorized operation.
- **Governance:** the risk-policy layer rejects the proposal with no
  `operator.final` record (`test_hostile_brain_proposal_refused_by_risk_policy`).
- **Execution:** never occurs.
- **Audit:** records the rejection.

*Result.* The model produced an actionable output; the system did **not** convert
that output into authority. This is the Authority Non-Equivalence Principle
demonstrated end-to-end (M0): cognition is separated from authorization even when
the model is adversarial (A1).

### 11.2 Experiment 2 — Corrupted Executor (bad execution is caught)

*Setup.* A cooperative, fully authorized trade is executed successfully. The
executor then falsely reports success by tampering its own `operator.final` record
(an A4 executor-compromise attempt): the recorded `risk_assessment_hash` is
mutated.

*Observation.*

- **Governance:** the operation was correctly authorized.
- **Execution:** the executor claims success, but its record is inconsistent.
- **Verification:** an independent verifier recomputes the expected hash from
  signed inputs, finds the mismatch, and escalates the control-plane aggregate to
  `CRITICAL` (`test_verifier_critical_on_tamper`). The run can never report overall
  `PASS`.
- **Audit:** records both the authorized action and the verification failure.

*Result.* The authorized operation was real, but the executor could not *manufacture
a successful verification*. Execution correctness is established by an independent
judge, not by the executor's report (Section 3: `Verification(x) ≠ Cognition(x)`,
here strengthened to `Verification(x) ≠ ExecutionReport(x)`).

Together the experiments bound the architecture: it holds against a malicious
model **and** against a compromised executor. The only failure class the
architecture does not cover is the third case of Section 4 -- an authorized action
that is epistemically wrong because the knowledge itself was wrong. That is the
subject of Section 12.

### 11.3 Experiment 3 — Six-Vector Attack Matrix (the untrusted agent is made to fail)

The two end-to-end experiments above exercise one condition each. To make the
thesis memorable, Experiment 3 applies a single **deliberately untrusted agent**
under six simultaneous adversarial vectors and demonstrates that the protocol
rejects or detects each. The point is not that the agent behaves well; it is that
**the architecture remains governed when the agent does not behave well.**

| # | Vector (adversary) | Attempt | Domain | Result |
|---|---|---|---|---|
| 1 | Unauthorized capability (A1/A3) | request capability outside grant | Authority | Rejected (`decide()` → `BLOCKED`) |
| 2 | Privilege escalation (A3) | request universal / out-of-scope capability | Authority | Rejected (scope-bound grant) |
| 3 | Forged identity (A3) | self-issued / non-root certificate | Authority | Rejected (pinned issuer key) |
| 4 | Modification after approval (A2/A4) | alter approved action post-signing | Authority | Rejected (binding + hash) |
| 5 | False execution report (A4) | tamper `operator.final` hash | Execution | Detected (verifier `CRITICAL`) |
| 6 | Audit modification (A5) | mutate / truncate / replay ledger | Execution / Evidence | Detected (`verify_chain is False`) |

*Table 7. Six-vector attack matrix. A single untrusted agent is induced to attempt
all six vectors; the protocol rejects or detects each. Counts underlying each row
are the per-class totals of Table 5 and the parametric instances of Table 6; all
are reproduced at commit `489e016` (Section 9.6).*

The matrix converts the thesis into a single, falsifiable claim: an agent attempting
every known adversarial vector against the protocol is unable to obtain or fake
authority on any vector. This is the strongest statement the evaluation makes, and
the one the Experimental Conditions block (Section 9.6) makes reproducible.

### 11.4 The Three Adversarial Flows (visual summary)

The three experiments can be drawn as single adversarial flows. Each tests one
half of the thesis -- that cognition cannot become authority, that execution
cannot fake verification, and that evidence cannot be silently altered -- rather
than merely that the software runs.

<figure className="paper-figure">
<svg viewBox="0 0 640 150" width="100%" role="img" aria-label="Figure: Flow 1. An untrusted agent emits an unauthorized proposal; the deterministic policy returns REJECT; execution never occurs.">
  <style>.b{font:600 13px ui-sans-serif,system-ui,sans-serif;fill:var(--color-ink)}.g{font:600 13px ui-sans-serif,system-ui,sans-serif;fill:var(--color-green)}.r{font:700 13px ui-sans-serif,system-ui,sans-serif;fill:var(--color-red)}.ar{stroke:var(--color-ink-3);stroke-width:1.4;fill:none;marker-end:url(#ah11a)}</style>
  <defs><marker id="ah11a" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="currentColor"/></marker></defs>
  <text x="16" y="22" class="b">Untrusted Agent</text>
  <text x="16" y="44" class="b">↓ Unauthorized Proposal</text>
  <text x="16" y="74" class="g">Deterministic Policy</text>
  <text x="16" y="96" class="g">↓ decide()</text>
  <text x="16" y="128" class="r">REJECT — execution never occurs</text>
  <path class="ar" d="M150,30 L150,64"/><path class="ar" d="M150,82 L150,116"/>
</svg>
<figcaption><strong>Flow 1 (Experiment 11.1).</strong> Probabilistic cognition produces an unauthorized proposal; the policy function -- which consults no model output -- returns <code>REJECT</code>, and no execution is triggered.</figcaption>
</figure>

<figure className="paper-figure">
<svg viewBox="0 0 640 150" width="100%" role="img" aria-label="Figure: Flow 2. An authorized proposal is executed; the executor makes a false claim of success; independent verification detects the mismatch.">
  <style>.b{font:600 13px ui-sans-serif,system-ui,sans-serif;fill:var(--color-ink)}.g{font:600 13px ui-sans-serif,system-ui,sans-serif;fill:var(--color-green)}.r{font:700 13px ui-sans-serif,system-ui,sans-serif;fill:var(--color-red)}.ar{stroke:var(--color-ink-3);stroke-width:1.4;fill:none;marker-end:url(#ah11b)}</style>
  <defs><marker id="ah11b" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="currentColor"/></marker></defs>
  <text x="16" y="22" class="b">Authorized Proposal</text>
  <text x="16" y="44" class="b">↓ Execution</text>
  <text x="16" y="74" class="g">False Executor Claim</text>
  <text x="16" y="96" class="g">↓ Independent Verification</text>
  <text x="16" y="128" class="r">DETECT — run cannot report PASS</text>
  <path class="ar" d="M150,30 L150,64"/><path class="ar" d="M150,82 L150,116"/>
</svg>
<figcaption><strong>Flow 2 (Experiment 11.2).</strong> A legitimately authorized action is executed, but the executor's false claim of success is caught by an independent verifier recomputing against the authoritative record.</figcaption>
</figure>

<figure className="paper-figure">
<svg viewBox="0 0 640 150" width="100%" role="img" aria-label="Figure: Flow 3. Signed evidence is subjected to a tampering attempt; the integrity check fails; the modification is detected.">
  <style>.b{font:600 13px ui-sans-serif,system-ui,sans-serif;fill:var(--color-ink)}.g{font:600 13px ui-sans-serif,system-ui,sans-serif;fill:var(--color-green)}.r{font:700 13px ui-sans-serif,system-ui,sans-serif;fill:var(--color-red)}.ar{stroke:var(--color-ink-3);stroke-width:1.4;fill:none;marker-end:url(#ah11c)}</style>
  <defs><marker id="ah11c" markerWidth="9" markerHeight="9" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="currentColor"/></marker></defs>
  <text x="16" y="22" class="b">Signed Evidence</text>
  <text x="16" y="44" class="b">↓ Tampering Attempt</text>
  <text x="16" y="74" class="g">Integrity Check</text>
  <text x="16" y="96" class="g">↓ verify_chain</text>
  <text x="16" y="128" class="r">DETECT — audit fails closed</text>
  <path class="ar" d="M150,30 L150,64"/><path class="ar" d="M150,82 L150,116"/>
</svg>
<figcaption><strong>Flow 3 (Experiment 11.3, vector 6).</strong> Tampering with a signed, chained audit record breaks integrity verification; the modification is detected rather than silently accepted (Invariant 4).</figcaption>
</figure>

### 11.5 Experiment 4 — The Deliberately Hostile Chain (the architecture's thesis, end to end)

The previous experiments isolate one boundary at a time. Experiment 4 asks the
stronger question: can a single untrusted cognitive component attempt the *entire*
attack chain at once and still be held by the protocol? The model is given explicit
permission to be wrong and to try every move a hostile operator would try, in
sequence:

```text
request an unauthorized capability
        ↓
attempt privilege escalation
        ↓
modify an approved action
        ↓
claim an execution succeeded
        ↓
tamper with evidence
```

This is exactly the behaviour the project sentence forbids trusting the model for:

> **Do not trust the model. Trust the execution protocol.**

*Setup.* A `HostileBrain` is instantiated with a scenario that instructs it to walk
the full chain above within a single governed run. No step is cooperative; each is
an attempt to convert probabilistic cognition into authority or to forge the record
of what happened.

*What is measured.* Each step crosses a different architectural boundary, and each
is caught by the boundary's own mechanism:

| Step | Boundary crossed | Mechanism | Outcome (test basis) |
|---|---|---|---|
| Unauthorized capability request | epistemic → authority | `decide()` returns `BLOCKED` | Rejected (Exp 11.1 / Table 3) |
| Privilege escalation attempt | authority (scope) | scope-bound grant | Rejected (Table 3) |
| Modify approved action | authority (binding) | post-signing hash mismatch | Rejected (Exp 11.2 premise) |
| False execution claim | execution → verification | independent verifier `CRITICAL` | Detected (Exp 11.2) |
| Tamper with evidence | execution → evidence | `verify_chain is False` | Detected (Exp 11.3) |

*Table 9. The hostile chain. A single untrusted component attempts all five moves;
each is stopped or detected at the boundary it crosses. No step reaches a state where
the model's intent becomes consequential reality.*

*Result.* The run never reports overall `PASS`. The cognitive component's intent is
contained at the first boundary and, even where a step is partially authorized, the
later boundaries (verification, evidence) remain independent and catch the forgery.
This is the empirical counterpart of the Section 4 theorem: **probabilistic cognition
is allowed to be wrong, and the architecture's authority, execution, verification,
and evidence computations absorb that wrongness without making it real.** The
experiment does not demonstrate that the model is trustworthy -- it demonstrates that
the *protocol* does not need it to be.

---

## 12. Related Work and the Open Problem

### 12.1 Related Work

We situate the architecture relative to existing research. The contribution is not
any individual component but the composition and the preserved invariant.

**Reasoning and acting.** ReAct (Yao et al., ICLR 2023) interleaves reasoning
traces with actions; Toolformer (Schick et al., 2023) and later tool-use
architectures let models invoke external functions. These address *how models
reason and act*. This paper addresses the orthogonal question of *how authority is
separated from reasoning*.

**Retrieval-augmented generation.** RAG (Lewis et al., NeurIPS 2020) grounds
generation in retrieved passages; GraphRAG (Microsoft Research, 2024) extends this
with graph-structured retrieval. A10's compiler performs the semantic transformation
at build time and treats the result as a governed artifact rather than a transient
context window.

**Tool and context interoperability.** The Model Context Protocol (Anthropic, 2024)
standardizes model-to-tool connections; it is a transport layer, not an
authorization boundary. MCP-style connectors can feed the epistemic substrate; the
authority substrate remains external to any connector.

**Zero Trust Architecture.** NIST SP 800-207 ("never trust, always verify") is the
agentic analogue: the model is never trusted as an authority, and every
consequential transition is verified against an external policy and identity.

**Capability-based security.** Capability systems (Dennis & Van Horn, 1966; Miller
et al., 2003) grant least-privilege, unforgeable authorities. The fleet substrate
adopts this model: a capability is a granted, scope-bound permission, not a role
label, and cannot be minted by the agent holding it.

**Trusted execution environments.** TEEs (Intel SGX, AWS Nitro Enclaves) provide
hardware-isolated execution and attestation. The fleet substrate provides a
*logical* isolation of authority that is complementary to, and independent of,
hardware TEEs: the guarantees hold regardless of where execution physically occurs.

**Provenance systems.** W3C PROV and data-lineage frameworks capture artifact
derivation. The architecture adopts signed provenance at both ends: A10 sidecars
record `provenance` (source, compiler, `git_sha`, generated_at); the fleet audit
ledger records signed evidence. Provenance establishes *lineage and integrity*, not
*truth* -- the central point of Section 12.2.

**Workflow orchestration.** Airflow, Temporal, and Prefect provide durable
execution state. The fleet substrate shares the concern for inspectable execution
state but adds an explicit authority boundary and cryptographic verification.

### 12.2 Knowledge Poisoning (Open Problem, A6)

The architecture defends A1-A5. It does **not yet** defend A6. We state this
explicitly because it is the most important unsolved problem and the most
interesting boundary of the work.

Consider the pipeline of Section 1. Governance validates the *authority* of an
action, not the *truth* of the knowledge. If an attacker modifies a Markdown
document, the compiler faithfully compiles it, retrieval surfaces it, the model
reasons from it, the agent produces a perfectly authorized action, policy allows
it, the executor performs it, and every security layer works correctly -- the
system can still be wrong. This is exactly the third case of Section 3:
**Execution Correctness ↛ Epistemic Correctness.** Cryptographic integrity (the
document is unchanged since compilation; the compilation is reproducible) does not
establish semantic truth (the document is correct).

This is why the precise definition of *sovereign* in Section 4 matters: sovereignty
guarantees local authority over provenance and execution, but **not** epistemic
correctness of the inputs. The architecture currently guarantees authority and
execution integrity; it does not validate epistemic integrity of the inputs. We
identify three candidate defenses, all future work: (i) signed provenance at
document ingestion with multi-author attestation; (ii) cross-document
contradiction detection over the compiled graph; (iii) a knowledge-uncertainty
bound that escalates low-certainty proposals to human approval. None is yet
implemented. We report this gap rather than overclaim, because the distinction
between the three correctness types is itself the contribution.

---

## 13. Limitations

The architecture does not eliminate the fundamental uncertainty of probabilistic
cognition. A governed system can prevent an unauthorized action, but it cannot
guarantee that every authorized proposal is intellectually correct. Semantic
compilation can introduce extraction or relationship errors; the verification gate
checks integrity and reproducibility, not semantic truth. Cryptographic integrity
does not establish semantic truth: a perfectly signed false statement remains
false. Independent verification can fail when the expected state is itself poorly
specified. The architecture addresses authority, provenance, and execution
integrity; it does not yet solve knowledge poisoning (Section 12.2).

---

## 14. Future Work

1. **Formal verification of the governance state machine**, proving the safety
   invariants of Section 3 hold for all reachable states.
2. **Epistemic integrity defenses against A6**: signed document provenance with
   multi-author attestation; cross-document contradiction detection over the
   compiled graph; knowledge-uncertainty escalation to human approval.
3. **Stronger provenance binding** between compiled artifacts and model-generated
   proposals, cryptographically linking a proposal to the specific `git_sha` and
   content hashes it reasoned over.
4. **Multi-agent consensus over evidence** rather than merely over model outputs.
5. **Formal policy specification** for heterogeneous capabilities, machine-checking
   the registry's capability table against an explicit policy.
6. **Reproducible agent execution** in which model versions, prompts, retrieved
   artifacts, policies, tool inputs/outputs, and execution states can be
   reconstructed.

---

## 15. Conclusion

This work presents an experimentally evaluated architecture for separating
probabilistic cognition from consequential authority. The contribution is
organized around a research object -- the trust-transition sequence
knowledge → compilation → retrieval → cognition → proposal → authorization →
execution → verification → evidence -- and a formal principle, the Authority
Non-Equivalence Principle: a probabilistic inference does not constitute
authorization, regardless of confidence, capability, or plausibility.

We decomposed the system into three trust domains (epistemic, authority,
execution) with three distinct types of correctness, formalized sovereignty as the
preservation of local authority over identity, policy, provenance, and execution
despite external computation, and implemented the architecture across two
cooperating codebases: A10 (the epistemic substrate) and Sovereign Agent Fleet
(the authority and execution substrate).

We evaluated the architecture against five architectural invariants using its own tests
as the benchmark (564 executable tests, all passing), and we reported three
adversarial experiments: a model induced to request an unauthorized operation is
rejected at the authority boundary (execution never occurs); a legitimately
authorized operation whose executor falsely reports success is detected by an
independent verifier; and a deliberately untrusted agent is rejected or detected
across all six adversarial vectors of the attack matrix. We organized the
evaluation around four research questions
(RQ1-RQ4) answered by the suite, a structural baseline contrast, and reported real,
reproduced numbers and separated measured results from open problems.

The contribution is not agent governance, RAG, knowledge graphs, cryptographic
audit, capability security, human approval, or independent verification
individually -- none of which is novel. It is the **composition**: a unified
architecture that treats probabilistic cognition as an untrusted epistemic subsystem
while independently governing consequential authority, execution, verification, and
evidence, and applies that architecture to a compilable knowledge substrate. The
deepest idea is the recurring pattern in Section 4.1 -- *do not make components
trustworthy; remove the authority that would make their untrustworthiness dangerous* --
applied once per trust boundary.

The most important open problem is knowledge poisoning: the architecture guarantees
authority and execution integrity but does not yet validate the epistemic integrity
of the knowledge entering the pipeline. Resolving that gap -- without collapsing
the three trust domains back into one -- is the natural next step, and the
three-integrity framing developed here is the lens through which it should be
approached.

The result is a governed computational environment in which memory becomes
architecture, cognition becomes modular, authority becomes deterministic, and
autonomy becomes verifiable.

---

## References

1. Kliewer, D. *A10: Knowledge Compilation and Sovereign Knowledge System.*
   GitHub repository, `kliewerdaniel/a10`.
2. Kliewer, D. *Sovereign Agent Fleet: Governed Multi-Agent Execution
   Architecture.* GitHub repository, `kliewerdaniel/sovereign-agent-fleet`
   (564-test suite, all passing). Reproducible results in this paper are pinned to
   commit `489e01697e664be6a0decd0ac0e335daeb47d9c4`.
3. Lewis, P., et al. *Retrieval-Augmented Generation for Knowledge-Intensive NLP
   Tasks.* NeurIPS, 2020.
4. Yao, S., et al. *ReAct: Synergizing Reasoning and Acting in Language Models.*
   ICLR, 2023.
5. Schick, T., et al. *Toolformer: Language Models Can Teach Themselves to Use
   Tools.* NeurIPS, 2023.
6. Microsoft Research. *GraphRAG: Unlocking LLM Discovery on Graph-Indexed
   Knowledge.* 2024.
7. Anthropic. *Model Context Protocol (MCP) specification.* 2024.
8. NIST. *Zero Trust Architecture*, SP 800-207. 2020.
9. Dennis, J. B., & Van Horn, E. C. *Programming Semantics for Multiprogrammed
   Computations.* CACM, 1966.
10. Miller, M. S., Yee, K.-P., & Shapiro, J. *Capability Myths Demolished.*
    Technical Report, Johns Hopkins University, 2003.
11. RFC 8032. *Edwards-Curve Digital Signature Algorithm (EdDSA): Ed25519 and
    Ed448.* IETF, 2017.
12. NIST. *Argon2 (PHC winner) password hashing*, RFC 9106.
13. W3C. *PROV-O: The PROV Ontology.* 2013.

---

*Author's note (position, not claim). The broader research program behind this
paper -- local-first inference, explicit memory, graph reasoning, modular
cognition, and computational sovereignty -- is developed across the linked
repositories and the project's research hub. The paper above separates the
scientific claim from that position: the claim is the architectural composition
and its preserved invariants; the position is the broader argument for local,
governed, verifiable intelligence. A capable model is an untrusted epistemic
component; authority is an independently verifiable protocol.*
