---
title: "Sovereign Knowledge Systems: An Experimentally Evaluated Architecture for Separating Probabilistic Cognition from Consequential Authority"
author: Daniel Kliewer
date: 2026-08-18
version: 3.0
status: designed
canonical_url: /paper
abstract: >-
  We present an experimentally evaluated architecture that separates probabilistic
  model cognition from consequential authority. The architecture is built on a
  single research object -- an explicitly ordered trust-transition sequence
  (knowledge -> compilation -> retrieval -> cognition -> proposal ->
  authorization -> execution -> verification -> evidence) -- and a formal
  principle: the Authority Non-Equivalence Principle, which states that no
  probabilistic inference, regardless of confidence, capability, or semantic
  plausibility, constitutes authorization to perform a consequential operation.
  We decompose the system into three trust domains (epistemic, authority,
  execution) with distinct integrity properties, and we formalize sovereignty as
  the preservation of local authority over identity, policy, knowledge
  provenance, and consequential execution despite reliance on external
  computational infrastructure. The architecture is implemented across two
  cooperating codebases: A10, the epistemic substrate (knowledge compiler +
  knowledge graph), and Sovereign Agent Fleet, the authority and execution
  substrate (frozen authorization function, cryptographic identity, human
  approval, controlled execution, tamper-evident audit). We evaluate the
  architecture against eight security invariants using its own test suite as the
  benchmark (564 executable tests, all passing), and we report two adversarial
  experiments: (1) a model induced to request an unauthorized operation is
  rejected at the authority boundary and execution never occurs; (2) a legitimate
  operation that is correctly authorized but whose executor falsely reports
  success is detected by an independent verifier. All reported numbers are
  reproduced from the executing test suite. We close by distinguishing the three
  types of correctness the system separates -- epistemic, authority, execution --
  and by stating the open problem (knowledge poisoning) precisely.
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

We evaluate the architecture against eight security invariants using the system's
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

We state the thesis as a formal principle so that the architecture can be read as
an implementation of it.

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

---

## 3. Three Trust Domains and Three Types of Correctness

We formalize the system as three trust domains, each with a distinct integrity
property and a distinct type of correctness.

**Definition 1 (Epistemic Domain).** Determines *what the system believes or
proposes*: the knowledge compiler, retrieval, the knowledge graph, embeddings, and
model reasoning. **Epistemic correctness**: was the information or reasoning
actually correct?

**Definition 2 (Authority Domain).** Determines *what the system is permitted to
do*: identity, capability, policy, approval. **Authority correctness**: was the
requested operation actually permitted?

**Definition 3 (Execution Domain).** Determines *what actually happened*: the
executor, the resulting state, the verifier, cryptographic evidence. **Execution
correctness**: did the authorized operation actually produce the expected state?

These are fundamentally different properties. A system can succeed at two while
failing the third:

- **Epistemic failure, governance success.** The model produces an *incorrect
  conclusion*, but the governance system correctly *rejects* its proposed action.
  (Epistemic correctness fails; authority and execution correctness are
  satisfied.)
- **Execution failure.** The model produces a *reasonable proposal*, the policy
  engine correctly *authorizes* it, and the executor *malfunctions*. (Epistemic
  and authority correctness pass; execution correctness fails.)
- **Authorized-to-be-wrong.** An epistemically incorrect action passes every
  authority and execution check *because the system was authorized to do exactly
  the wrong thing*. (All three correctness types can be satisfied while the
  outcome is wrong.) This is the most important case, and it bounds the system's
  claim; it is treated precisely in Section 10.

**Theorem (Non-Implication).** None of the three correctness types implies
another:

```
EpistemicCorrectness  ↛  AuthorityCorrectness
AuthorityCorrectness  ↛  ExecutionCorrectness
ExecutionCorrectness  ↛  EpistemicCorrectness
```

*Justification.* Epistemic correctness does not imply authority correctness: a
correct proposal still requires an external grant. Authority correctness does not
imply execution correctness: an authorized action may be mis-executed and must be
independently verified. Execution correctness does not imply epistemic
correctness: a flawlessly executed, perfectly audited action can still be wrong if
the underlying knowledge was wrong -- the third case above.

---

## 4. On "Sovereign": A Precise Definition

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

## 5. Architectural Substrate Decomposition

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

## 6. Knowledge Substrate (A10 — Epistemic)

A10 implements the epistemic substrate. Its architecture includes a Next.js
application, a structured source corpus, a data layer, and a semantic compiler.
The knowledge system is treated as a computational substrate, not merely a content
store.

### 6.1 Source Corpus

The source corpus is the long-term human-authored representation of the system's
knowledge: 177 Markdown posts under `content/blog/`, each with structured
frontmatter (title, author, date, canonical URL, status, topics, series). This
creates an important asymmetry: the model may generate derived representations,
but the canonical source remains independently inspectable and regenerable.

### 6.2 Knowledge Compilation (the Transformation Boundary)

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

### 6.3 Artifact Model and the Fail-Closed Verification Gate

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

## 7. Governance and Execution Substrate (Sovereign Agent Fleet)

Sovereign Agent Fleet implements the authority and execution substrates. Its
central principle is that the system should not require trust in the model.

### 7.1 Role Separation

The multi-agent structure provides role separation: Researcher produces
observations; Analyst transforms them into qualified intelligence; Operator
executes authorized actions. Agent roles (`researcher`, `analyst`, `operator`,
`human`, `tool`) are carried on a cryptographically signed identity certificate,
never asserted by model output.

### 7.2 Identity and Root of Trust

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

### 7.3 Deterministic Policy and the `decide()` Substrate

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

### 7.4 Capability Authorization and Human Approval

Capabilities provide a finer-grained, least-privilege authority model than broad
agent permissions. Human approval provides an additional boundary for
consequential operations: the approval record is bound to the specific operation
(action id, capability, artifact hash) and is cryptographically signed by a
`human`-role cert. A forged, rebound, or non-human-signed approval is rejected
(Section 8.2).

### 7.5 Execution, Verification, and Audit

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

## 8. Formal Threat Model and Evaluation Design

### 8.1 Threat Model (A1-A6)

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

### 8.2 Invariant Evaluation Table

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

*Table 1. Security-invariant evaluation. The system's own tests are the benchmark.
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

---

## 9. Evaluation Results

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

*Table 2. Invariant-grouped test inventory (counts verified from the suites
cited). The remaining fleet tests cover consensus, runtime, control plane,
incident policy, brain, GCP, root rotation, armor, and boundary imports.*

### 9.1 Policy Enforcement (Authority Separation, Identity, Capability)

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

*Table 3. Authorization decision matrix. "Attempts" are parametric instances within
the adversarial suites; the substrate returns `BLOCKED` for every class except the
authorized one, with zero false accepts.*

The decisive property is **zero false accepts** under forgery. The grant is
verified against a *pinned trusted issuer key* (`trusted_issuer_pubkey_pem`), not
against a key the grant embeds for itself -- so an attacker who forges a grant and
claims the issuer is the governance key is still rejected.

### 9.2 Approval Binding (Audit Integrity, A3/A4)

Forged agent certificates (signed by a non-root key) fail verification; tampered
certificates (capability escalation on a valid signature) fail; a revoked identity
is denied at the gateway before any governance gate runs
(`test_revoked_identity_rejected`). A forged, rebound, or non-human-signed human
approval is rejected (`test_approval_hardening_phase2`).

The signed hash-chain ledger detects three tamper classes: in-place value mutation
(`test_audit_tamper_detected`), tail truncation (`test_audit_truncation_detected`),
and replay of a previously-seen entry (`test_c3_replay_of_old_entry_detected`). All
return `verify_chain is False`.

### 9.3 Verification Independence (Experiment A — bad execution cannot fake success)

We make the model fail. A legitimately authorized trade is executed, producing an
`operator.final` record. When its `risk_assessment_hash` is mutated and the record
re-ingested, an **independent verifier** recomputes the hash, finds a mismatch, and
escalates the control-plane aggregate to `CRITICAL` -- the run can never report
overall `PASS` (`test_verifier_critical_on_tamper`). The executor's self-report is
not the source of truth; the verifier's recomputation is. This is the architectural
assertion `Verification(x) ≠ Cognition(x)` made operational: a corrupted executor
cannot manufacture a successful verification.

### 9.4 Domain Portability (Invariant: M0 Generality)

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

### 9.5 Knowledge Provenance (A10 Compiler)

The A10 compiler's fail-closed gate (Section 6.3) is exercised by 18 compiler
tests. The gate re-derives every `content_hash` from source and refuses to emit on
any mismatch. Reproducing artifacts from the corpus yields 177 posts, 687 graph
nodes, and 2,981 edges, with the gate reporting PASS. Divergent or corrupted source
cannot silently produce a valid artifact (Table 1, row "Knowledge provenance").

---

## 10. Two Adversarial Experiments

To make the thesis memorable and concrete, we report two experiments in which the
model is deliberately induced to fail. These demonstrate both halves of the
architecture: **bad cognition cannot obtain authority**, and **bad execution
cannot manufacture successful verification**.

### 10.1 Experiment 1 — Induced Unauthorized Request (bad cognition is rejected)

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

### 10.2 Experiment 2 — Corrupted Executor (bad execution is caught)

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
judge, not by the executor's report (Section 2: `Verification(x) ≠ Cognition(x)`,
here strengthened to `Verification(x) ≠ ExecutionReport(x)`).

Together the two experiments bound the architecture: it holds against a malicious
model **and** against a compromised executor. The only failure class the
architecture does not cover is the third case of Section 3 -- an authorized action
that is epistemically wrong because the knowledge itself was wrong. That is the
subject of Section 11.

---

## 11. Related Work and the Open Problem

### 11.1 Related Work

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
*truth* -- the central point of Section 11.2.

**Workflow orchestration.** Airflow, Temporal, and Prefect provide durable
execution state. The fleet substrate shares the concern for inspectable execution
state but adds an explicit authority boundary and cryptographic verification.

### 11.2 Knowledge Poisoning (Open Problem, A6)

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

## 12. Limitations

The architecture does not eliminate the fundamental uncertainty of probabilistic
cognition. A governed system can prevent an unauthorized action, but it cannot
guarantee that every authorized proposal is intellectually correct. Semantic
compilation can introduce extraction or relationship errors; the verification gate
checks integrity and reproducibility, not semantic truth. Cryptographic integrity
does not establish semantic truth: a perfectly signed false statement remains
false. Independent verification can fail when the expected state is itself poorly
specified. The architecture addresses authority, provenance, and execution
integrity; it does not yet solve knowledge poisoning (Section 11.2).

---

## 13. Future Work

1. **Formal verification of the governance state machine**, proving the safety
   invariants of Section 2 hold for all reachable states.
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

## 14. Conclusion

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

We evaluated the architecture against eight security invariants using its own tests
as the benchmark (564 executable tests, all passing), and we reported two
adversarial experiments: a model induced to request an unauthorized operation is
rejected at the authority boundary (execution never occurs); and a legitimately
authorized operation whose executor falsely reports success is detected by an
independent verifier. We reported real, reproduced numbers and separated measured
results from open problems.

The most important open problem is knowledge poisoning: the architecture guarantees
authority and execution integrity but does not yet validate the epistemic integrity
of the knowledge entering the pipeline. Resolving that gap -- without collapsing
the three trust domains back into one -- is the natural next step, and the
three-correctness framing developed here is the lens through which it should be
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
