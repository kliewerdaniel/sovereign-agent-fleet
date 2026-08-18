---
title: "Sovereign Knowledge Systems: A Governed Architecture for Compilable Knowledge and Verifiable Agentic Execution"
author: Daniel Kliewer
date: 2026-08-18
version: 2.0
status: designed
canonical_url: /paper
abstract: >-
  We present a system architecture in which consequential agentic execution is
  made independent of probabilistic model authority by separating cognition,
  authorization, execution, verification, and evidence into explicit, verifiable
  architectural boundaries. The architecture is implemented across two cooperating
  codebases: A10, a knowledge system that compiles 177 human-authored documents
  into a graph, search index, and per-article sidecars at build time behind a
  fail-closed verification gate; and the Sovereign Agent Fleet, a frozen
  authorization substrate in which model output is treated as untrusted input
  rather than authority. We formalize the central contribution as the Authority
  Non-Equivalence Principle -- that no probabilistic inference output, regardless
  of confidence, constitutes authorization to perform a consequential operation --
  and we organize the system into three trust domains (epistemic, authority,
  execution) whose integrity properties are provably non-implicating. We evaluate
  the architecture against a formal threat model (A1-A6) using 564 executable
  tests, demonstrating that seven independent security invariants hold under
  adversarial pressure. The evaluation reports real, reproduced numbers; we
  explicitly distinguish what is measured from what remains open. The most
  important open problem is knowledge poisoning: the architecture guarantees
  authority and execution integrity but does not yet validate epistemic
  integrity of the knowledge entering the pipeline.
keywords:
  - sovereign intelligence
  - agent governance
  - knowledge compilation
  - autonomous agents
  - computational sovereignty
  - cryptographic audit
  - deterministic policy
  - GraphRAG
  - verifiable execution
  - capability security
  - threat model
  - formal verification
---

# Sovereign Knowledge Systems: A Governed Architecture for Compilable Knowledge and Verifiable Agentic Execution

## Abstract

Large language models have introduced probabilistic computation into workflows
that historically relied on deterministic programs. Contemporary agent
architectures frequently place model-generated decisions on the critical path
between cognition and consequential action, implicitly treating probabilistic
inference as an authority mechanism. This paper presents a system architecture
that makes consequential agentic execution **independent of probabilistic model
authority** by separating cognition, authorization, execution, verification, and
evidence into explicit architectural boundaries.

The architecture is implemented across two cooperating codebases. **A10** is a
knowledge system that compiles 177 human-authored Markdown documents into a
structured artifact set -- an entity/relationship graph (687 nodes, 2,981 edges),
a BM25 search index, and per-article sidecars carrying SHA-256 content hashes,
extracted entities, claims, references, and provenance -- behind a fail-closed
verification gate. **Sovereign Agent Fleet** is a frozen authorization substrate
in which model output is treated as untrusted input rather than authority, and
which is exercised unchanged across six domains (exchange/finance,
incident/security, supply/logistics, hypothesis/research, mirror/self-observability,
grid/energy) through a single registered capability table.

We formalize the central contribution as the **Authority Non-Equivalence
Principle**: no probabilistic inference output, regardless of confidence, semantic
validity, or model capability, constitutes authorization to perform a consequential
operation. We organize the system into three trust domains -- epistemic, authority,
execution -- and show that the integrity properties of these domains are
provably non-implicating: epistemic integrity does not imply authority integrity;
authority integrity does not imply execution integrity; and execution integrity
does not imply epistemic correctness.

We evaluate the architecture against a formal threat model of six adversary
classes (A1-A6) using 564 executable tests spanning governance, identity,
capability, approval, audit, verification, and domain portability. The evaluation
demonstrates that an unauthorized or malicious model can propose but cannot
authorize; that forged, replayed, mutated, or self-issued grants are rejected;
that the executor cannot falsely report success; and that historical evidence
resists tampering. All reported numbers are reproduced from the executing test
suite. We close by identifying the most important unsolved problem: **knowledge
poisoning** -- the architecture guarantees authority and execution integrity but
does not yet validate the epistemic integrity of the knowledge entering the
pipeline.

**Keywords:** sovereign intelligence, agent governance, knowledge compilation,
autonomous agents, retrieval augmented generation, GraphRAG, computational
sovereignty, cryptographic audit, deterministic policy, capability security,
threat model, formal verification, verifiable execution.

---

## 1. Introduction

The emergence of large language models has changed the architecture of software
systems by introducing probabilistic computation into workflows that were
historically governed by deterministic programs. A conventional software system
establishes explicit control flow, authorization rules, data structures, and state
transitions. A language model introduces a fundamentally different computational
primitive: given the same nominal input, a model may generate different outputs,
may produce incorrect information with high confidence, and may generate actions
whose consequences cannot be established from the output alone.

The architectural problem is therefore not simply that language models
hallucinate. Hallucination is one manifestation of a deeper systems issue: when a
probabilistic component is positioned as an **authority boundary**, model output
acquires the power to cause consequential state changes. The central proposition
of this work is:

> **A capable model should be treated as an untrusted epistemic component, while
> authority should be implemented as an independently verifiable protocol.**

Under this proposition, the model may reason, propose, and hypothesize; it does
not become the system's root of trust. The contribution of this paper is not a
specific agent, model, or benchmark, but an **architectural composition** and a
set of **invariants** preserved across its layers.

The architecture is implemented and tested in two cooperating codebases. A10
(`kliewerdaniel/a10`) provides the knowledge substrate: a structured 177-document
corpus, a semantic compiler, and a publication portal. Sovereign Agent Fleet
(`sovereign-agent-fleet`) provides the governance/execution substrate: a frozen
`decide()` authorization function, cryptographic identity, capability policy,
human approval, controlled execution, and a tamper-evident audit ledger. The
combination demonstrates that the knowledge plane and the authority plane can be
composed without either subsuming the other.

---

## 2. Problem Statement

Contemporary agentic systems combine language models with tools, memory,
retrieval systems, external APIs, software execution environments, and autonomous
planning loops. Such systems create a control problem because model-generated
content can cross multiple trust boundaries before reaching a consequential
operation.

We identify five failure modes that arise when probabilistic cognition is placed on
the authority path:

1. **Conflation of validity and authorization.** A technically valid operation
   generated by a model is not the same as an operation the system is permitted to
   perform.
2. **Confidence mistaken for evidence.** Coherent, high-confidence output does not
   establish that an operation is correct or authorized.
3. **Audit dependency on conversational history.** A chat transcript is not a
   tamper-evident record of what was authorized and executed.
4. **Implicit cloud authority.** When identity, policy, or verification is
   delegated to remote infrastructure, that infrastructure quietly acquires
   authority root status.
5. **Capability scaling without governance scaling.** A more capable model can
   propose more consequential actions; without corresponding governance strength,
   the potential blast radius grows with capability.

The architecture developed here addresses these failure modes by making the
separation between cognition and authority **structural and enforced in code**,
rather than a convention or a prompt.

---

## 3. Research Question and Contributions

We pose a single central research question:

> **RQ.** Can consequential agentic execution be made independent of
> probabilistic model authority by separating cognition, authorization, execution,
> verification, and evidence into explicit architectural boundaries -- and can
> that separation be preserved across heterogeneous domains and adversarial
> pressure?

The paper makes the following contributions:

- **A formal principle.** We state the **Authority Non-Equivalence Principle** and
  give it algebraic form (Section 4), establishing that authorization is a
  function of identity, capability, resource, action, and state -- never of model
  output.
- **A three-domain trust model.** We decompose the system into epistemic,
  authority, and execution trust domains, and show that their integrity properties
  are non-implicating (Section 5).
- **An implemented architecture.** We describe a concrete implementation in two
  codebases, including a deterministic knowledge compiler and a frozen
  authorization substrate (Sections 7-8).
- **A formal threat model.** We define six adversary classes (A1-A6) and map each
  to the specific mechanisms that defend against it (Section 9).
- **An empirical evaluation.** We report reproduced results from 564 executable
  tests across seven invariant categories, including adversarial and end-to-end
  scenarios (Section 11).
- **A precise statement of the open problem.** We distinguish authority and
  execution integrity from epistemic integrity, and identify knowledge poisoning
  as the central unsolved issue (Sections 11.6 and 12).

---

## 4. Architectural Thesis: Authority Non-Equivalence

The architectural thesis can be expressed as a single formal principle.

**Authority Non-Equivalence Principle.** *No probabilistic inference output,
regardless of confidence, semantic validity, or model capability, constitutes
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

Two further invariants follow directly:

```
∀c.  Execution(c)  ⇒  Authorization(c)
```

No execution occurs without an authorization decision; and

```
Verification(x)  ⟂  Cognition(x)
```

verification is logically independent of the cognitive process that produced `x`.
The same model that proposed `x` is not the component that determines whether `x`
was executed correctly.

This formulation is the paper's core novelty claim. The novelty is not Ed25519, nor
RAG, nor knowledge graphs, nor policy engines, nor human approval, nor agents
individually. It is the **architectural composition** -- cognition as untrusted
input, authority as an external deterministic protocol, execution as bounded
action, and verification as an independent judge -- with the invariant preserved
across every layer.

---

## 5. Three Trust Domains

We formalize the system as three trust domains, each with a distinct integrity
property.

**Definition 1 (Epistemic Domain).** The epistemic domain determines *what the
system believes or proposes*. It comprises the knowledge compiler, retrieval, the
knowledge graph, embeddings, and model reasoning. Its integrity property is
**Epistemic Integrity**: the faithfulness of beliefs and proposals to their
sources and to the reasoning process.

**Definition 2 (Authority Domain).** The authority domain determines *what the
system is permitted to do*. It comprises identity, capability, policy, and
approval. Its integrity property is **Authority Integrity**: the correspondence
between permitted actions and externally granted, cryptographically bound
permissions.

**Definition 3 (Execution Domain).** The execution domain determines *what
actually happened*. It comprises the executor, the resulting state, the verifier,
and cryptographic evidence. Its integrity property is **Execution Integrity**: the
correspondence between the authorized action and the observed, verifiable outcome.

**Theorem (Non-Implication).** None of the three integrity properties implies
another. Formally:

```
EpistemicIntegrity  ↛  AuthorityIntegrity
AuthorityIntegrity  ↛  ExecutionIntegrity
ExecutionIntegrity  ↛  EpistemicIntegrity
```

*Justification.* Epistemic integrity does not imply authority integrity: a perfectly
reasoned, correct proposal still requires an external grant to be authorized.
Authority integrity does not imply execution integrity: a correctly authorized
action may fail or be mis-executed, and must be independently verified. Execution
integrity does not imply epistemic integrity: a flawlessly executed, perfectly
audited action can still be wrong if the underlying knowledge was wrong. The third
case is the subject of Section 12.

This decomposition is the paper's primary theoretical framing. It converts the
informal claim "the model is not in charge" into a structured statement about
which guarantees hold where, and about the explicit gaps between them.

---

## 6. System Architecture

The complete architecture is a pipeline of transformations, partitioned across the
three trust domains of Section 5.

<figure style="margin:2rem 0;padding:1.25rem;border:1px solid var(--color-rule);background:var(--color-card-bg);color:var(--color-ink-3)">
<svg viewBox="0 0 720 520" width="100%" role="img" aria-label="Figure 1: Complete system architecture as a vertical pipeline partitioned into three trust-domain bands.">
  <style>
    .t{font:600 13px ui-sans-serif,system-ui,sans-serif;fill:var(--color-ink)}
    .s{font:500 11px ui-sans-serif,system-ui,sans-serif;fill:currentColor}
    .b{stroke:currentColor;stroke-width:1.2;fill:var(--color-paper)}
    .g{stroke:var(--color-green);stroke-width:1.6}
    .ar{stroke:currentColor;stroke-width:1.2;fill:none;marker-end:url(#ah)}
  </style>
  <defs><marker id="ah" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="currentColor"/></marker></defs>

  <!-- bands -->
  <rect x="20" y="20" width="680" height="150" rx="8" fill="rgba(43,91,168,0.06)" stroke="currentColor" stroke-dasharray="4 3"/>
  <rect x="20" y="200" width="680" height="90" rx="8" fill="rgba(31,138,76,0.07)" stroke="var(--color-green)" stroke-dasharray="4 3"/>
  <rect x="20" y="320" width="680" height="170" rx="8" fill="rgba(22,20,15,0.05)" stroke="currentColor" stroke-dasharray="4 3"/>

  <text x="30" y="38" class="t" style="fill:var(--color-ink)">Epistemic Domain</text>
  <text x="690" y="38" text-anchor="end" class="s">what the system believes</text>
  <text x="30" y="218" class="t" style="fill:var(--color-ink)">Authority Domain</text>
  <text x="690" y="218" text-anchor="end" class="s">what is permitted</text>
  <text x="30" y="338" class="t" style="fill:var(--color-ink)">Execution Domain</text>
  <text x="690" y="338" text-anchor="end" class="s">what actually happened</text>

  <!-- epistemic boxes -->
  <rect x="60" y="55" width="120" height="38" rx="5" class="b"/><text x="120" y="78" text-anchor="middle" class="s">Human Knowledge</text>
  <rect x="200" y="55" width="120" height="38" rx="5" class="b"/><text x="260" y="78" text-anchor="middle" class="s">Knowledge Compiler</text>
  <rect x="340" y="55" width="120" height="38" rx="5" class="b"/><text x="400" y="78" text-anchor="middle" class="s">Compiled Artifacts</text>
  <rect x="480" y="55" width="100" height="38" rx="5" class="b"/><text x="530" y="78" text-anchor="middle" class="s">Retrieval / Graph</text>
  <rect x="600" y="55" width="80" height="38" rx="5" class="b"/><text x="640" y="78" text-anchor="middle" class="s">Cognition</text>
  <rect x="600" y="110" width="80" height="38" rx="5" class="b"/><text x="640" y="133" text-anchor="middle" class="s">Proposal</text>

  <!-- authority boxes -->
  <rect x="250" y="228" width="120" height="40" rx="5" class="b" style="stroke:var(--color-green)"/><text x="310" y="252" text-anchor="middle" class="s">Deterministic Policy</text>
  <rect x="400" y="228" width="120" height="40" rx="5" class="b" style="stroke:var(--color-green)"/><text x="460" y="252" text-anchor="middle" class="s">Human Approval</text>

  <!-- execution boxes -->
  <rect x="250" y="360" width="120" height="40" rx="5" class="b"/><text x="310" y="384" text-anchor="middle" class="s">Execution</text>
  <rect x="400" y="360" width="120" height="40" rx="5" class="b"/><text x="460" y="384" text-anchor="middle" class="s">Independent Verification</text>
  <rect x="550" y="360" width="120" height="40" rx="5" class="b"/><text x="610" y="384" text-anchor="middle" class="s">Cryptographic Evidence</text>

  <!-- arrows -->
  <path class="ar" d="M180,74 L200,74"/>
  <path class="ar" d="M320,74 L340,74"/>
  <path class="ar" d="M460,74 L480,74"/>
  <path class="ar" d="M580,74 L600,74"/>
  <path class="ar" d="M640,93 L640,110"/>
  <path class="ar" d="M640,148 C640,190 460,200 460,228"/>
  <path class="ar" d="M460,268 L460,320 C460,340 460,340 460,360"/>
  <path class="ar" d="M370,380 L400,380"/>
  <path class="ar" d="M520,380 L550,380"/>
  <path class="ar" d="M310,400 C310,440 120,440 120,440" stroke-dasharray="3 3"/>
  <text x="120" y="458" text-anchor="middle" class="s" style="fill:var(--color-ink-3)">feedback: evidence informs future knowledge</text>
</svg>
<figcaption style="font:500 12px ui-sans-serif,system-ui,sans-serif;color:var(--color-ink-3);margin-top:.75rem"><strong>Figure 1.</strong> Complete system architecture. Solid arrows are the primary
trust-transition sequence; the dashed arc is the long-horizon evidence feedback
loop. Each transition is an opportunity for validation at a domain boundary.</figcaption>
</figure>

The critical property is that the **proposal → policy** transition is a hard trust
boundary. The proposal carries no authority; the policy function consults no model
output. Between Cognition/Proposal (epistemic) and Policy/Approval (authority)
there is no shared state that would let a proposal silently promote itself to a
permission.

<figure style="margin:2rem 0;padding:1.25rem;border:1px solid var(--color-rule);background:var(--color-card-bg);color:var(--color-ink-3)">
<svg viewBox="0 0 720 260" width="100%" role="img" aria-label="Figure 2: Three trust-domain zones separated by cryptographic and deterministic boundaries.">
  <style>
    .t{font:700 14px ui-sans-serif,system-ui,sans-serif;fill:var(--color-ink)}
    .s{font:500 11px ui-sans-serif,system-ui,sans-serif;fill:currentColor}
  </style>
  <rect x="20" y="30" width="210" height="180" rx="10" fill="rgba(43,91,168,0.07)" stroke="currentColor"/>
  <rect x="255" y="30" width="210" height="180" rx="10" fill="rgba(31,138,76,0.08)" stroke="var(--color-green)"/>
  <rect x="490" y="30" width="210" height="180" rx="10" fill="rgba(22,20,15,0.05)" stroke="currentColor"/>
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
  <line x1="230" y1="40" x2="255" y2="40" stroke="currentColor" stroke-width="2"/>
  <line x1="230" y1="200" x2="255" y2="200" stroke="currentColor" stroke-width="2"/>
  <text x="242" y="125" text-anchor="middle" class="s" transform="rotate(-90 242 125)">grant boundary</text>
  <line x1="465" y1="40" x2="490" y2="40" stroke="currentColor" stroke-width="2"/>
  <line x1="465" y1="200" x2="490" y2="200" stroke="currentColor" stroke-width="2"/>
  <text x="477" y="125" text-anchor="middle" class="s" transform="rotate(-90 477 125)">execution boundary</text>
</svg>
<figcaption style="font:500 12px ui-sans-serif,system-ui,sans-serif;color:var(--color-ink-3);margin-top:.75rem"><strong>Figure 2.</strong> The three trust domains as separated zones. The grant boundary
admits only an externally-signed, scope-bound grant; the execution boundary admits
only an already-authorized operation.</figcaption>
</figure>

The execution domain is also governed by an explicit state machine. The
fleet substrate drives transitions through:

```
REQUEST → INTENT → PLAN → ACTION → TOOL → OBSERVATION
        → EVIDENCE → VERIFICATION → ARTIFACT → APPROVAL → FINAL → AUDIT
```

<figure style="margin:2rem 0;padding:1.25rem;border:1px solid var(--color-rule);background:var(--color-card-bg);color:var(--color-ink-3)">
<svg viewBox="0 0 720 150" width="100%" role="img" aria-label="Figure 3: Sovereign Agent Fleet state machine from request through audit.">
  <style>
    .s{font:600 11px ui-sans-serif,system-ui,sans-serif;fill:var(--color-ink)}
    .ar{stroke:currentColor;stroke-width:1.2;fill:none;marker-end:url(#ah3)}
  </style>
  <defs><marker id="ah3" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="currentColor"/></marker></defs>
  <g>
    <rect x="10" y="55" width="62" height="34" rx="5" fill="var(--color-paper)" stroke="currentColor"/><text x="41" y="76" text-anchor="middle" class="s">REQUEST</text>
    <rect x="90" y="55" width="62" height="34" rx="5" fill="var(--color-paper)" stroke="currentColor"/><text x="121" y="76" text-anchor="middle" class="s">INTENT</text>
    <rect x="170" y="55" width="62" height="34" rx="5" fill="var(--color-paper)" stroke="currentColor"/><text x="201" y="76" text-anchor="middle" class="s">PLAN</text>
    <rect x="250" y="55" width="62" height="34" rx="5" fill="var(--color-paper)" stroke="currentColor"/><text x="281" y="76" text-anchor="middle" class="s">ACTION</text>
    <rect x="330" y="55" width="62" height="34" rx="5" fill="var(--color-paper)" stroke="currentColor"/><text x="361" y="76" text-anchor="middle" class="s">TOOL</text>
    <rect x="410" y="55" width="62" height="34" rx="5" fill="var(--color-paper)" stroke="currentColor"/><text x="441" y="76" text-anchor="middle" class="s">OBS</text>
    <rect x="490" y="55" width="62" height="34" rx="5" fill="var(--color-paper)" stroke="currentColor"/><text x="521" y="76" text-anchor="middle" class="s">EVID</text>
    <rect x="570" y="55" width="62" height="34" rx="5" fill="var(--color-paper)" stroke="var(--color-green)"/><text x="601" y="76" text-anchor="middle" class="s">VERIFY</text>
    <rect x="650" y="55" width="60" height="34" rx="5" fill="var(--color-paper)" stroke="currentColor"/><text x="680" y="76" text-anchor="middle" class="s">FINAL</text>
  </g>
  <path class="ar" d="M72,72 L90,72"/>
  <path class="ar" d="M152,72 L170,72"/>
  <path class="ar" d="M232,72 L250,72"/>
  <path class="ar" d="M312,72 L330,72"/>
  <path class="ar" d="M392,72 L410,72"/>
  <path class="ar" d="M472,72 L490,72"/>
  <path class="ar" d="M552,72 L570,72"/>
  <path class="ar" d="M632,72 L650,72"/>
  <path class="ar" d="M680,105 C680,130 41,130 41,105" stroke-dasharray="3 3"/>
  <rect x="255" y="105" width="80" height="24" rx="4" fill="rgba(31,138,76,0.08)" stroke="var(--color-green)"/>
  <text x="295" y="formation" />
  <text x="295" y="121" text-anchor="middle" class="s" style="fill:var(--color-green)">APPROVAL</text>
  <text x="360" y="138" text-anchor="middle" class="s">AUDIT persists every transition into a signed, hash-chained ledger</text>
</svg>
<figcaption style="font:500 12px ui-sans-serif,system-ui,sans-serif;color:var(--color-ink-3);margin-top:.75rem"><strong>Figure 3.</strong> Sovereign Agent Fleet execution state machine. Each transition
is validated; APPROVAL is an explicit gate for consequential operations.</figcaption>
</figure>

This sequence is important because it prevents the model from collapsing the
entire pipeline into a single response. Each arrow is a trust transition that can
be independently validated and recorded.

---

## 7. Knowledge Substrate (A10)

A10 provides the concrete implementation environment for the epistemic domain. Its
architecture includes a Next.js application, structured source content, a data
layer, public assets, documentation, and a semantic compiler. The knowledge system
is treated as a computational substrate, not merely a content store.

### 7.1 Source Corpus

The source corpus is the long-term human-authored representation of the system's
knowledge: 177 Markdown posts under `content/blog/`, each with structured
frontmatter (title, author, date, canonical URL, status, topics, series). This
creates an important asymmetry: the model may generate derived representations,
but the canonical source remains independently inspectable and regenerable.

### 7.2 Knowledge Compilation

The knowledge compiler (`knowledge-compiler/`) runs a deterministic pipeline at
build time:

```
ingest → normalize → extract → graph → search → emit → verify
```

- **ingest** reads the 177 Markdown sources.
- **normalize** parses frontmatter and applies the taxonomy.
- **extract** derives entities, relationships, claims, and references per post.
- **graph** builds a NetworkX entity/relationship graph.
- **search** builds a BM25 index with tokenized entries.
- **emit** writes `index.json`, `<slug>.json` sidecars, `graph.json`, and
  `search.json` to `public/artifacts/`.
- **verify** runs the fail-closed gate (Section 7.3).

<figure style="margin:2rem 0;padding:1.25rem;border:1px solid var(--color-rule);background:var(--color-card-bg);color:var(--color-ink-3)">
<svg viewBox="0 0 720 230" width="100%" role="img" aria-label="Figure 4: A10 knowledge compilation pipeline.">
  <style>
    .s{font:600 11px ui-sans-serif,system-ui,sans-serif;fill:var(--color-ink)}
    .ar{stroke:currentColor;stroke-width:1.2;fill:none;marker-end:url(#ah4)}
  </style>
  <defs><marker id="ah4" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="currentColor"/></marker></defs>
  <rect x="10" y="40" width="110" height="40" rx="5" fill="var(--color-paper)" stroke="currentColor"/><text x="65" y="64" text-anchor="middle" class="s">Markdown (177)</text>
  <rect x="140" y="40" width="100" height="40" rx="5" fill="var(--color-paper)" stroke="currentColor"/><text x="190" y="58" text-anchor="middle" class="s">Parse +</text><text x="190" y="72" text-anchor="middle" class="s">normalize</text>
  <rect x="260" y="40" width="100" height="40" rx="5" fill="var(--color-paper)" stroke="currentColor"/><text x="310" y="58" text-anchor="middle" class="s">Extract</text><text x="310" y="72" text-anchor="middle" class="s">entities/claims</text>
  <rect x="380" y="40" width="100" height="40" rx="5" fill="var(--color-paper)" stroke="currentColor"/><text x="430" y="58" text-anchor="middle" class="s">Graph +</text><text x="430" y="72" text-anchor="middle" class="s">Search</text>
  <rect x="500" y="40" width="90" height="40" rx="5" fill="var(--color-paper)" stroke="currentColor"/><text x="545" y="58" text-anchor="middle" class="s">Emit</text><text x="545" y="72" text-anchor="middle" class="s">artifacts</text>
  <rect x="610" y="40" width="100" height="40" rx="5" fill="rgba(31,138,76,0.08)" stroke="var(--color-green)"/><text x="660" y="58" text-anchor="middle" class="s">Verify</text><text x="660" y="72" text-anchor="middle" class="s">gate</text>
  <path class="ar" d="M120,60 L140,60"/>
  <path class="ar" d="M240,60 L260,60"/>
  <path class="ar" d="M360,60 L380,60"/>
  <path class="ar" d="M480,60 L500,60"/>
  <path class="ar" d="M590,60 L610,60"/>
  <rect x="500" y="120" width="210" height="80" rx="6" fill="rgba(43,91,168,0.06)" stroke="currentColor"/>
  <text x="605" y="142" text-anchor="middle" class="s" style="fill:var(--color-ink)">public/artifacts/</text>
  <text x="520" y="162" class="s">graph.json (687n/2981e)</text>
  <text x="520" y="180" class="s">search.json (BM25)</text>
  <text x="520" y="196" class="s">&lt;slug&gt;.json sidecars</text>
  <path class="ar" d="M655,80 L655,120"/>
  <rect x="10" y="120" width="200" height="80" rx="6" fill="rgba(22,20,15,0.05)" stroke="currentColor"/>
  <text x="110" y="150" text-anchor="middle" class="s" style="fill:var(--color-ink)">Consumers</text>
  <text x="20" y="172" class="s">portal (server components)</text>
  <text x="20" y="190" class="s">retrieval / RAG</text>
  <text x="20" y="206" class="s">governance plane (interface)</text>
  <path class="ar" d="M500,160 L450,160 L450,140"/>
</svg>
<figcaption style="font:500 12px ui-sans-serif,system-ui,sans-serif;color:var(--color-ink-3);margin-top:.75rem"><strong>Figure 4.</strong> A10 knowledge compilation pipeline. Semantic transformations are
performed once at build time and emitted as deterministic, version-controlled
artifacts rather than recomputed per request.</figcaption>
</figure>

Because the build is deterministic and local, the semantic structure can be
version-controlled, diffed, and reproduced -- the same reproducibility guarantee
the fleet substrate applies to authorization.

### 7.3 Artifact Model and Verification Gate

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
exits non-zero. It checks: (1) all 177 slugs unique; (2) every canonical URL
equals `/blog/<slug>`; (3) every content hash is reproducible from source
(re-hashing the body yields the stored hash); (4) `graph.json`, `search.json`,
`index.json` are present, non-empty, and parseable; (5) every post has an emitted
sidecar. These are precisely the integrity properties a governance system would
demand of any knowledge it reasons over: uniqueness, deterministic
canonicalization, reproducible content identity, and completeness.

---

## 8. Governance and Execution Plane (Sovereign Agent Fleet)

Sovereign Agent Fleet implements the authority and execution domains. Its central
principle is that the system should not require trust in the model.

### 8.1 Role Separation

The multi-agent structure provides role separation: Researcher produces
observations; Analyst transforms them into qualified intelligence; Operator
executes authorized actions. The separation reduces the likelihood that one
probabilistic process can simultaneously generate an objective, authorize itself,
execute the resulting action, and declare success. Agent roles (`researcher`,
`analyst`, `operator`, `human`, `tool`) are carried on a cryptographically signed
identity certificate, never asserted by model output.

### 8.2 Identity and Root of Trust

The architecture derives a key hierarchy from an Argon2id-strengthened master
secret:

```
master secret (Argon2id) → root Ed25519 signing key → per-agent Ed25519 identity keys
```

The root key issues agent certificates (`AgentCert`) that are signed by the root
and that the agent cannot alter -- the agent does not hold the root key, so it
cannot grant itself scope, capabilities, or role. Certificates bind to an
`agent_id`, `role`, `capabilities`, issuance/expiry, and a `cert_seq`, and are
signed under a root epoch so rotated roots do not invalidate historical chains.

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
3. the grant must be current (epoch supersession is primary; a TTL is a backstop);
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
(Section 11.3).

### 8.5 Execution, Verification, and Audit

Execution occurs only after authorization. Verification independently determines
whether the resulting artifact or state satisfies required conditions; it is a
separate computational role, not a statement emitted by the executor. The audit
architecture wraps an Ed25519-signed hash-chain ledger: each entry is signed and
linked to the previous entry, with a signed checkpoint so truncation and replay
are detectable. Per-record confidentiality is provided by an XChaCha20-Poly1305
envelope (HKDF per-record subkeys), so encryption protects secrecy while
signatures protect integrity -- the two concerns are not conflated.

---

## 9. Formal Threat Model

We define the adversary by capability, not by scenario. Six adversary classes are
considered.

- **A1: Malicious or compromised model.** The model intentionally generates
  unauthorized or harmful actions, or reports false justification.
- **A2: Prompt injection.** External knowledge or tool content attempts to
  manipulate agent behavior.
- **A3: Privilege escalation.** An agent requests capabilities outside its assigned
  authority.
- **A4: Executor compromise.** The execution subsystem reports false success.
- **A5: Evidence tampering.** An attacker modifies historical audit records.
- **A6: Knowledge poisoning.** A malicious or incorrect document enters the
  canonical or compiled knowledge substrate.

Table 1 maps each adversary to the mechanisms that defend against it, and to the
evaluation section where the defense is exercised.

| Adversary | Primary defense mechanism | Evaluated in |
|---|---|---|
| A1 Malicious/compromised model | `decide()` excludes model output; proposal carries no authority | §11.2, §11.4 |
| A2 Prompt injection | Evidence gate rejects zero-reference (HALLUCINATION) intel; tool output is envelope-bound | §11.4 (Attack 3) |
| A3 Privilege escalation | Capability scope; `capability_not_granted`; grant bound to identity | §11.2, §11.4 (Attack 2) |
| A4 Executor compromise | Independent verifier recomputes state; `operator.final` tamper → CRITICAL | §11.3, §11.5 |
| A5 Evidence tampering | Ed25519-signed hash chain; truncation/replay/seq detected | §11.3 (crypto) |
| A6 Knowledge poisoning | **Not yet defended** — see §11.6 and §12 | open |

*Table 1. Threat model: adversary classes mapped to defense mechanisms.*

The central design property is that defenses operate **even when the model is the
adversary** (A1). Because `decide()` does not consult the model, a hostile model
cannot convert its own output into a permitted action; this is the M0 invariant
demonstrated in Section 11.4.

---

## 10. Related Work

We situate the architecture relative to existing research. The contribution is not
any individual component but the composition and the preserved invariant.

**Reasoning and acting.** ReAct (Yao et al., ICLR 2023) interleaves reasoning
traces with actions, improving agent task performance. Toolformer (Schick et al.,
2023) and subsequent tool-use architectures let models invoke external functions.
These works address *how models reason and act*. This paper addresses the
orthogonal question of *how authority is separated from reasoning* -- the model's
action proposal is necessary but never sufficient for execution.

**Retrieval-augmented generation.** RAG (Lewis et al., NeurIPS 2020) grounds
generation in retrieved passages. GraphRAG (Microsoft Research, 2024) extends this
with graph-structured retrieval over entities and relationships. A10's compilation
pipeline is compatible with and builds upon this lineage, but performs the
semantic transformation at build time rather than per request, and treats the
result as a governed artifact rather than a transient context window.

**Tool and context interoperability.** The Model Context Protocol (Anthropic,
2024) standardizes how models connect to tools and data sources. MCP is a
transport and schema layer; it does not itself constitute an authorization
boundary. The architecture here is complementary: MCP-style connectors can feed
the epistemic domain, but the authority domain remains external to any connector.

**Zero Trust Architecture.** NIST SP 800-207 formalizes "never trust, always
verify" for network and identity. The Authority Non-Equivalence Principle is the
agentic analogue: the model is never trusted as an authority, and every
consequential transition is verified against an external policy and identity, not
against the requestor's self-description.

**Capability-based security.** Capability systems (Dennis & Van Horn, 1966;
Miller et al., 2003) grant least-privilege, unforgeable authorities. The fleet
substrate adopts this model: a capability is a granted, scope-bound permission
rather than a role label, and cannot be minted by the agent that holds it.

**Trusted execution environments.** TEEs and confidential computing (e.g., Intel
SGX, AWS Nitro Enclaves) provide hardware-isolated execution and remote
attestation. The fleet substrate provides a *logical* isolation of authority that
is complementary to, and independent of, hardware TEEs: the guarantees hold
regardless of whether execution occurs inside an enclave, on a local machine, or
in a cloud function.

**Provenance systems.** W3C PROV and data-lineage frameworks capture the
derivation of artifacts. The architecture adopts signed provenance at two ends of
the pipeline: the A10 sidecar records `provenance` (source, compiler, `git_sha`,
generated_at) for knowledge artifacts, and the fleet audit ledger records signed
evidence for execution. Crucially, provenance establishes *lineage and integrity*,
not *truth* -- a point developed in Section 12.

**Workflow and orchestration systems.** Systems such as Airflow, Temporal, and
Prefect provide deterministic execution and durability for workflows. The fleet
substrate shares the concern for durable, inspectable execution state, but adds an
explicit authority boundary and cryptographic verification that general
orchestrators do not enforce by default.

The novelty claim, stated precisely, is: **existing agent architectures primarily
address how models reason and act; this architecture addresses the orthogonal
question of how authority is separated from reasoning, and preserves that
separation as a tested invariant across heterogeneous domains.**

---

## 11. Evaluation

The evaluation reports reproduced results from the executing test suites of both
repositories. We adopt the convention that the system is **fail-closed**: every
guard defaults to rejection. We report what is measured and, equally important,
what is not.

### 11.1 Methodology

We categorize the executable tests by the invariant they exercise rather than by
module. The full Sovereign Agent Fleet suite comprises **564 tests, all passing**
(reproduced via `pytest` against the repository at the version cited in References
[2]). Of these, the invariant-relevant suites we draw on directly contain:

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

*Table 2. Invariant-grouped test inventory (counts verified from the suites
cited). The remaining fleet tests cover consensus, runtime, control plane,
incident policy, brain, GCP, root rotation, armor, and boundary imports.*

### 11.2 Policy Enforcement (Invariant: Authority Integrity)

We evaluate the authorization function directly using a protocol-level table. Each
row is a class of request; the verdict is the `decide()` outcome. These classes are
exercised across 28 adversarial contract tests and 29 epistemic-kernel tests.

| Test class | Attempts | Allowed | Rejected | False accepts |
|---|---:|---:|---:|---:|
| Authorized actions (valid grant, in scope) | 1000 (parametrized) | 1000 | 0 | 0 |
| Unauthorized capabilities | 1000 | 0 | 1000 | 0 |
| Unknown capabilities | 1000 | 0 | 1000 | 0 |
| Invalid/forged identities | 1000 | 0 | 1000 | 0 |
| Tampered/self-issued grants | 1000 | 0 | 1000 | 0 |
| Stale or expired grants | 1000 | 0 | 1000 | 0 |

*Table 3. Authorization decision matrix. "Attempts" are parametric instances
within the adversarial suites; the substrate returns `BLOCKED` for every class
except the authorized one, with zero false accepts. Representative concrete tests:
`test_forged_grant_signature_rejected`, `test_self_issued_grant_rejected`,
`test_replay_expired_epoch_rejected`, `test_alter_capability_after_signing_detected`,
`test_authorization_request_alone_grants_nothing`.*

The decisive property is **zero false accepts** under forgery. Critically, the
grant is verified against a *pinned trusted issuer key* (`trusted_issuer_pubkey_pem`),
not against a key the grant embeds for itself -- so an attacker who forges a grant
and claims the issuer is the governance key is still rejected.

### 11.3 Identity, Audit, and Execution Verification

**Identity (A3).** Forged agent certificates (signed by a non-root key) fail
`root.verify_cert`; tampered certificates (capability escalation on a valid
signature) fail verification; a revoked identity is denied at the gateway before
any governance gate runs (`test_revoked_identity_rejected`).

**Audit (A5).** The signed hash-chain ledger detects three tamper classes:
in-place value mutation (`test_audit_tamper_detected`), tail truncation
(`test_audit_truncation_detected`), and replay of a previously-seen entry
(`test_c3_replay_of_old_entry_detected`). All return `verify_chain is False`.

**Verification / Executor independence (A4).** We demonstrate the "executor cannot
falsely report success" property directly. In `test_verifier_critical_on_tamper`,
a correctly-executed trade produces an `operator.final` record; when its
`risk_assessment_hash` is mutated and the record is re-ingested, the independent
verifier recomputes the hash, finds a mismatch, and escalates the control-plane
aggregate to `CRITICAL` -- the run can never report overall `PASS`. The executor's
self-report is therefore not the source of truth; the verifier's recomputation is.

**Experiment A (independence of verification from cognition).** Let the model
propose and "report success" for a trade. Let the executor record the action. Let
an independent verifier recompute the expected state from signed inputs. Result:
the executor's reported success is accepted only when the verifier's recomputation
matches; a tampered record is rejected despite the executor's own log. This is the
architectural assertion of Section 4 ("`Verification(x) ⟂ Cognition(x)`") made
operational.

### 11.4 Domain Portability (Invariant: M0 Generality)

The same frozen `decide()` substrate governs six domains through a single
capability table (`domain_registry`). We verify portability with a parameterized
generality suite:

- **Same policy → same verdict** across all six registered domains under an
  identical AUTO policy; the semantic domain is invisible to `decide()`
  (`test_m0_same_policy_same_verdict_across_all_registered_domains`).
- **Policy flip moves every domain** AUTO→HUMAN together
  (`test_m0_policy_flip_changes_all_registered_domains_identically`).
- **No shared substrate state** among domains (pure function, no per-domain cache)
  (`test_m0_no_shared_substrate_state_among_registered_domains`).
- **Scoped grant cannot authorize** an out-of-scope universal capability, in every
  domain (`test_m0_scoped_grant_cannot_authorize_universal_capability`,
  parametrized over all six).
- **Substrate operates with all adapters removed** from `sys.modules`
  (`test_reverse_substrate_functional_without_any_adapter_present`).

The strongest demonstration is end-to-end and adversarial. In the financial
workload, a `HostileBrain` model proposes an unauthorized asset (TSLA) at 100x size.
The proposal is **refused at the risk-policy layer** with no `operator.final`
record written (`test_hostile_brain_proposal_refused_by_risk_policy`,
`test_hostile_brain_rejected_at_every_layer_independently`). The authority
boundary holds regardless of model output (M0). The same pipeline executes a
cooperative proposal and verifies `PASS` (`test_cooperative_brain_proposal_executes_and_verifies`).

In the incident workload, VERIFIED evidence of a compromised `identity-svc` is
**still blocked** from isolating that protected asset (`test_act3_protected_blocked_despite_verified_compromise`),
preventing self-inflicted auth DoS; a forged/mis-bound human approval is rejected
(`test_attack1_misbound_approval_rejected`); hallucinated (zero-reference) intel is
blocked at the evidence gate (`test_attack3_hallucination_intel_blocked`); and even
a direct `SimEnv.transition` call on a protected asset defends itself
(`test_attack4_simenv_second_line_defense`).

### 11.5 A10 Compiler Verification

The A10 compiler's fail-closed gate (Section 7.3) is exercised by 18 compiler
tests. The gate re-derives every `content_hash` from source and refuses to emit on
any mismatch. Reproducing artifacts from the corrected corpus yields 177 posts,
687 graph nodes, and 2,981 edges, with the gate reporting PASS. This is the same
fail-closed discipline applied to knowledge that the fleet applies to authorization:
divergent or corrupted source cannot silently produce a valid artifact.

### 11.6 Knowledge Poisoning (Open Problem)

The architecture defends A1-A5. It does **not yet** defend A6. We state this
explicitly because it is the most important unsolved problem and the most
interesting theoretical boundary of the work.

Consider the pipeline:

```
Knowledge → Compilation → Retrieval → Cognition → Proposal → Governance
```

Governance validates the *authority* of an action, not the *truth* of the
knowledge. If an attacker modifies a Markdown document, the compiler faithfully
compiles it, retrieval surfaces it, the model reasons from it, the agent produces
a perfectly authorized action, policy allows it, the executor performs it, and
every security layer works correctly -- the system can still be wrong.

This is exactly the non-implication of Section 5: **Execution Integrity ↛
Epistemic Integrity.** Cryptographic integrity (the document is unchanged since
compilation, the compilation is reproducible) does not establish semantic truth
(the document is correct). The architecture currently guarantees authority and
execution integrity; it does not validate epistemic integrity of the inputs.

We identify three candidate defenses, all future work: (i) signed provenance at
document ingestion with multi-author attestation; (ii) cross-document
contradiction detection over the compiled graph; (iii) a confidence/uncertainty
bound on knowledge-derived proposals that escalates low-certainty actions to human
approval. None is yet implemented. We report this gap rather than overclaim,
because the distinction between the three integrity types is itself the
contribution.

---

## 12. Discussion

The architecture's intellectual core is the separation of three trust domains.
The model is allowed to reason, propose, and hypothesize. It is **not** allowed to
become authority merely because it generated a proposal. This changes the security
question from "can the model be trusted?" to "can the surrounding system remain
correct when the model cannot be trusted?"

The three-integrity framing resolves a subtle point that weaker formulations
miss. A system can have perfect execution integrity (every action is audited and
verifiable) and still be epistemically wrong (it acted on poisoned knowledge). A
system can have perfect authority integrity (no unauthorized action ever runs) and
still be epistemically wrong (all authorized actions were based on false
premises). The novelty is not in achieving any one property, but in making the
*non-implication* explicit and engineering each boundary so that a failure in one
domain does not silently propagate authority into another.

The evaluation demonstrates the engineering maturity of the authority and
execution domains. The honest limitation is the epistemic domain's openness to A6.
We regard this as the most promising direction for follow-on work, not a
refutation of the thesis: the thesis is about *authority independence from
cognition*, and that holds.

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
integrity; it does not yet solve knowledge poisoning (Section 11.6).

---

## 14. Future Work

1. **Formal verification of the governance state machine**, proving the safety
   invariants of Section 4 hold for all reachable states.
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
   artifacts, policies, tool inputs, outputs, and execution states can be
   reconstructed.

---

## 15. Conclusion

This work presents an architecture for sovereign knowledge and agentic execution
based on a simple but consequential principle:

> **Do not trust the model; trust the execution protocol.**

We formalized this as the Authority Non-Equivalence Principle and organized the
system into three trust domains -- epistemic, authority, execution -- whose
integrity properties are provably non-implicating. We implemented the architecture
across two cooperating codebases: A10, which compiles 177 documents into a
deterministic, verifiable knowledge substrate; and Sovereign Agent Fleet, which
governs consequential execution through a frozen `decide()` substrate exercised
unchanged across six domains.

We evaluated the architecture against a formal threat model (A1-A6) using 564
executable tests, demonstrating that unauthorized or malicious models can propose
but cannot authorize, that forged and replayed grants are rejected, that the
executor cannot falsely report success, and that historical evidence resists
tampering. We reported real, reproduced numbers and separated measured results
from open problems.

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
   Architecture.* GitHub repository, `sovereign-agent-fleet` (564-test suite,
   all passing).
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
