---
title: "Sovereign Knowledge Systems: A Governed Architecture for Compilable Knowledge and Verifiable Agentic Execution"
author: Daniel Kliewer
date: 2026-08-18
version: 1.0
status: designed
canonical_url: /paper
abstract: >-
  Large language model systems increasingly place model-generated decisions
  directly on the critical path between cognition and consequential action.
  This paper presents a sovereign knowledge architecture that separates
  probabilistic cognition from deterministic governance, applies that separation
  to a compilable, version-controlled knowledge substrate, and binds every
  consequential transition to cryptographically verifiable evidence. The
  architecture is implemented across two cooperating codebases: the A10 knowledge
  system (a structured 177-post technical corpus compiled at build time into a
  graph, search index, and per-article sidecars) and the Sovereign Agent Fleet
  (a frozen authorization substrate in which model output is treated as untrusted
  input rather than authority). The central research contribution is not another
  autonomous agent but an architecture in which the knowledge substrate,
  cognition layer, authority layer, execution layer, and verification layer are
  deliberately separated -- allowing the model to become more capable without
  becoming the system's root of trust.
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
  - agent architecture
---

# Sovereign Knowledge Systems: A Governed Architecture for Compilable Knowledge and Verifiable Agentic Execution

## Abstract

Large language model systems have demonstrated increasingly capable reasoning,
retrieval, planning, and autonomous execution. Yet contemporary agent
architectures frequently place model-generated decisions directly on the critical
path between cognition and consequential action. This creates a fundamental
systems problem: **probabilistic inference is being implicitly treated as an
authority mechanism.**

This paper presents a sovereign knowledge architecture that separates
probabilistic cognition from deterministic governance and applies that
separation to a compilable, version-controlled knowledge substrate. The
architecture combines the knowledge and publication system implemented in the
**A10** project with the governance, identity, authorization, execution,
verification, and audit primitives developed in the **Sovereign Agent Fleet**
project. A10 provides a structured corpus, a semantic compilation layer, an
application architecture, and persistent knowledge artifacts. Sovereign Agent
Fleet provides a governed execution protocol in which model output is treated as
untrusted input rather than authority.

The resulting architecture establishes explicit boundaries between source
knowledge, semantic compilation, retrieval, reasoning, proposed actions,
authorization, execution, verification, and evidence. Rather than attempting to
make an individual model trustworthy, the system is designed to *remain safe when
the model is incorrect, compromised, hallucinating, replaced, or adversarial.*

This is not a theoretical sketch. Both halves are implemented and tested:

- The A10 knowledge compiler transforms 177 human-authored Markdown posts into a
  deterministic artifact set -- an entity/relationship graph (687 nodes, 2,981
  edges), a BM25 search index, and per-article sidecars carrying SHA-256 content
  hashes, extracted entities, claims, references, and provenance -- behind a
  **fail-closed verification gate** that re-derives every hash from source and
  refuses to emit on any inconsistency.
- The Sovereign Agent Fleet substrate provides a **pure, deterministic
  `decide()`** function that authorizes or rejects actions without ever reading a
  probability, confidence score, or model output. It is exercised unchanged
  across six domains (exchange/finance, incident/security, supply/logistics,
  hypothesis/research, mirror/self-observability, grid/energy) through a single
  registered capability table -- the M0 domain-generality result.

The paper argues that this architecture provides a general foundation for
sovereign intelligence in which memory is treated as architecture, semantic
processing is shifted toward compilation, authority is externalized into
deterministic policy, and consequential execution produces independently
verifiable evidence. The work demonstrates how a personal technical knowledge
system can evolve from a conventional content application into a governed
computational knowledge substrate, and establishes a general architecture
applicable to autonomous software, financial simulation, incident remediation,
scientific reasoning, and other domains requiring accountable agentic execution.

**Keywords:** sovereign intelligence, agent governance, knowledge compilation,
autonomous agents, retrieval augmented generation, GraphRAG, computational
sovereignty, cryptographic audit, deterministic policy, human-in-the-loop,
verifiable execution, agent architecture.

---

## Table of Contents

1. Introduction
2. Problem Definition
3. Research Objectives
4. Architectural Thesis
5. System Architecture
   5.1 Knowledge Substrate
   5.2 Semantic Compilation
   5.3 Probabilistic Cognition
   5.4 Governance and Authority
   5.5 Execution
   5.6 Independent Verification
   5.7 Cryptographic Evidence
6. The A10 Knowledge System
   6.1 Source Corpus
   6.2 Application Architecture
   6.3 Knowledge Compiler
   6.4 Artifact Model and Verification Gate
   6.5 Architectural Documentation
7. Sovereign Agent Fleet
   7.1 Governed Multi-Agent Architecture
   7.2 Identity and Root of Trust
   7.3 Deterministic Policy and the `decide()` Substrate
   7.4 Capability Authorization
   7.5 Approval Protocol
   7.6 Execution Boundary
   7.7 Independent Verification
   7.8 Tamper-Evident Audit
8. Integrating Knowledge and Governance
   8.1 Epistemic Boundary
   8.2 Authority Boundary
   8.3 Knowledge-to-Action Pipeline
   8.4 Provenance and Evidence
9. Formal System Model
   9.1 Trust Model
   9.2 Threat Model
   9.3 State Transitions
   9.4 Safety Invariants
10. Security Properties
11. Computational Sovereignty
12. Engineering Validation
13. Applications and Extensions
   13.1 Autonomous Software Engineering
   13.2 Financial Simulation
   13.3 Incident Response
   13.4 Scientific Knowledge Systems
   13.5 Personal Institutional Memory
14. Limitations
15. Future Research
16. Discussion
17. Conclusion
18. References

---

## 1. Introduction

The emergence of large language models has changed the architecture of software
systems by introducing probabilistic computation into workflows that were
historically governed by deterministic programs. A conventional software system
generally establishes explicit control flow, authorization rules, data
structures, and state transitions. A language model introduces a fundamentally
different computational primitive. Given the same nominal input, a model may
generate different outputs, may produce incorrect information with high
confidence, and may generate actions whose consequences cannot be established
from the output alone.

The architectural problem is therefore not simply that language models
hallucinate. Hallucination is one manifestation of a deeper systems problem. The
problem occurs when a **probabilistic component is positioned as an authority
boundary.**

The central proposition of this work is:

> **Model output should never constitute authority by itself.**

The systems developed across A10 and Sovereign Agent Fleet explore an alternative
architecture. Cognition is treated as an *untrusted* probabilistic subsystem
capable of generating observations, hypotheses, plans, recommendations, evidence
candidates, and action proposals. Governance exists *outside* the model and is
implemented through deterministic policy, capability boundaries, cryptographic
identity, explicit approval mechanisms, controlled execution, independent
verification, and durable evidence.

This architecture changes the fundamental security question from *"can the model
be trusted?"* to *"can the surrounding system remain correct when the model
cannot be trusted?"*

---

## 2. Problem Definition

Contemporary agentic systems increasingly combine language models with tools,
memory, retrieval systems, external APIs, software execution environments, and
autonomous planning loops. Such architectures create a control problem because
model-generated content can cross multiple trust boundaries before reaching a
consequential operation.

A model may generate a tool invocation. The invocation may access a filesystem,
database, financial interface, cloud resource, or external communication channel.
If the runtime treats the model-generated invocation as an *instruction* rather
than an *untrusted proposal*, the model effectively becomes an
authority-bearing principal.

This architecture creates several classes of failure.

**First, semantic correctness and authorization become conflated.** A model can
generate a technically valid operation that it should not be permitted to
execute. Validity of the request is not the same as permission to perform it.

**Second, model confidence can be mistaken for evidence.** A coherent explanation
does not establish that an operation is correct, and a high-confidence statement
does not establish that it is authorized.

**Third, auditability becomes dependent on conversational history** rather than
cryptographically bound execution records. A chat transcript is not a tamper-evident
audit log.

**Fourth, cloud infrastructure may become an implicit authority root** even when
the user or organization intends to retain local control. When verification,
identity, or policy resolution is delegated to a remote service, that service
quietly acquires authority.

**Fifth, increasing model capability can increase the potential blast radius of
failures** without producing corresponding increases in governance strength. A
more capable model can both propose better actions and propose more consequential
mistakes.

The architecture developed in this project addresses these problems by
establishing an explicit separation between cognition and authority. The
separation is not a style preference; it is enforced in code. In the Sovereign
Agent Fleet substrate, the authorization function `decide()` is documented as
accepting *no* probability, confidence, model score, belief, or calibration
value -- the verdict is determined entirely by capability, grant scope, epoch
currency, and policy (see Section 7.3).

---

## 3. Research Objectives

The project has five primary objectives.

**First**, to establish a knowledge substrate in which human-authored information
remains canonical while machine-readable semantic representations are generated
through compilation rather than runtime inference. The A10 compiler achieves this
by emitting deterministic artifacts (Section 6.3).

**Second**, to establish a governed agent architecture in which model-generated
cognition cannot directly authorize consequential actions. The Sovereign Agent
Fleet `decide()` substrate enforces this (Section 7.3).

**Third**, to provide cryptographically verifiable evidence for important state
transitions and actions, using Ed25519 signatures and hash chaining rather than
opaque logs (Section 7.8).

**Fourth**, to maintain local authority while permitting cloud infrastructure to
function as a computational or verification substrate rather than as the ultimate
source of trust (Section 11).

**Fifth**, to demonstrate that the same governance architecture can operate across
substantially different domains without modifying the fundamental authority
model -- the six-domain registry (Section 7.1, 12).

---

## 4. Architectural Thesis

The architectural thesis can be expressed as:

> **Cognition may propose. Policy authorizes. Execution acts. Verification
> independently determines whether the resulting state satisfies the required
> conditions. Evidence records what occurred.**

This distinction is fundamental.

- The language model is **not** the root of trust.
- The user interface is **not** the root of trust.
- The cloud deployment is **not** the root of trust.
- The agent role name is **not** the root of trust.
- The root of trust is established through explicit identity, policy,
  authorization, cryptographic evidence, and independently verifiable state.

This results in a system where **intelligence and authority are intentionally
decoupled.** A model that is wrong, compromised, or adversarial cannot convert its
own output into a permitted action, because the only function that can issue a
permission -- `decide()` -- does not consult the model at all.

---

## 5. System Architecture

The complete architecture can be understood as a sequence of transformations:

```
Source Knowledge
   -> Semantic Compilation
   -> Structured Artifacts
   -> Retrieval
   -> Cognition
   -> Proposal
   -> Policy
   -> Approval
   -> Execution
   -> Verification
   -> Evidence
```

Each stage has a distinct responsibility.

- The **source knowledge** represents human-authored or otherwise canonical
  information.
- The **compiler** transforms that knowledge into machine-usable artifacts at
  build time, not at request time.
- **Retrieval** provides relevant context.
- **Cognition** operates over that context and produces probabilistic outputs.
- The **proposal** boundary converts cognition into an explicitly typed request
  for action -- an artifact that *grants no authority*.
- **Policy** evaluates whether that request is permitted.
- **Approval** provides an additional authorization boundary for consequential
  operations.
- **Execution** performs only authorized operations.
- **Verification** independently evaluates the resulting state.
- **Evidence** records the resulting execution and verification information.

This architecture prevents any individual subsystem from silently assuming
responsibilities belonging to another subsystem.

### 5.1 Knowledge Substrate

A10 represents the knowledge side of this architecture. The project contains a
structured blog corpus (177 posts), an application source tree, a data layer,
public assets, documentation, a semantic compiler, a taxonomy, and compiler
tests. The architecture therefore treats content as structured computational
input rather than merely presentation data.

The Markdown corpus remains important because it provides a human-readable
canonical representation. The system does not require the model to become the
authoritative representation of the knowledge. This creates a durable separation
between the epistemic source and its machine-generated derivatives (Section 8.1).

### 5.2 Semantic Compilation

The knowledge compiler represents one of the most important architectural
properties of the system. Traditional retrieval-augmented generation systems
often perform substantial semantic processing during runtime -- documents are
loaded, parsed, embedded, retrieved, clustered, or otherwise transformed while
the user is waiting for an inference result.

The compiler model moves a portion of this computation into a build phase.
Conceptually:

```
Knowledge Source -> Parse -> Extract -> Normalize -> Relate -> Index -> Compile -> Artifact
```

The resulting artifacts can then be consumed by the runtime without repeatedly
reconstructing the same semantic structure. This is significant for both
performance and sovereignty: expensive semantic transformations are performed
locally, inspected, versioned, tested, reproduced, and deployed as deterministic
build artifacts (Section 6.3).

### 5.3 Probabilistic Cognition

The agent remains responsible for tasks where probabilistic computation provides
significant value: interpretation, synthesis, hypothesis generation, planning,
classification, natural-language reasoning, and proposal generation. The critical
architectural property is that these outputs are treated as **data**.

- A model saying that an action *should* occur does not cause that action to
  occur.
- A model saying that evidence *supports* a conclusion does not establish that
  the evidence is valid.
- A model *identifying* a capability does not grant that capability.

This is the fundamental epistemic boundary (Section 8.1).

### 5.4 Governance and Authority

Sovereign Agent Fleet externalizes authority into deterministic infrastructure.
The policy engine determines whether a particular identity, role, capability,
resource, and requested action are compatible.

This produces a strict distinction:

```
Model Proposal  !=  Authorized Action
```

A proposal must pass through the governance boundary before execution. The result
is a **fail-closed** architecture: unknown combinations are rejected rather than
interpreted optimistically. The substrate returns `BLOCKED` when *any* guard
fails -- no grant, invalid grant signature, stale grant, agent/scope mismatch,
capability not granted, or policy denial (Section 7.3).

### 5.5 Execution

Execution is intentionally downstream of authorization. The executor does not
determine whether an operation should be allowed; it receives an already
authorized operation and performs it within the defined execution environment.

This separation prevents the execution layer from becoming an accidental policy
engine. It also creates a useful testing boundary because execution can be tested
independently from cognition.

### 5.6 Independent Verification

Verification is intentionally separated from execution. The verifier does not
simply trust that the executor performed the operation correctly; instead, it
reconstructs relevant state from observable evidence and evaluates whether the
required conditions hold.

This creates a three-part distinction:

```
Proposal -> Execution -> Verification
```

rather than:

```
Model -> Action -> Trust
```

The distinction becomes particularly important for financial simulation and
incident remediation, where an incorrect execution can produce consequences even
when the original model reasoning appeared valid (Section 13.2, 13.3).

### 5.7 Cryptographic Evidence

The fleet architecture incorporates cryptographic identity and tamper-evident
evidence structures. Ed25519 signatures provide cryptographic authenticity for
identities and signed artifacts. Hash chaining provides structural integrity for
sequential evidence. The combination establishes an auditable execution history
in which modification of historical records becomes detectable.

The purpose is not merely to encrypt information. Encryption protects
confidentiality. Signatures and hash chains instead establish **integrity,
authenticity, and provenance** -- properties that hold even if the underlying
storage is untrusted (Section 7.8).

---

## 6. The A10 Knowledge System

A10 provides the concrete implementation environment for applying these
principles to a persistent technical knowledge corpus. Its architecture includes
a Next.js application, structured source content, a knowledge compiler, data
structures, typed application boundaries, documentation, and tests. The
knowledge system is not being treated as an external database attached to an
agent; the knowledge system itself is becoming a computational substrate.

### 6.1 Source Corpus

The source corpus provides the long-term human-authored representation of the
system's knowledge: 177 Markdown posts under `content/blog/`, each with
structured frontmatter (title, author, date, canonical URL, status, topics,
series). This creates an important asymmetry: the model may generate derived
representations, but the canonical source remains independently inspectable.
Generated semantic artifacts can be regenerated from source rather than becoming
irreversible model state.

### 6.2 Application Architecture

The application provides the human-facing interface to the knowledge substrate.
The separation between routes, components, data, libraries, and types creates
explicit software boundaries that can subsequently be consumed by automated
systems. The architecture therefore provides a natural interface between human
interaction and machine reasoning. The portal consumes the compiled artifacts at
build time (server components read them from `public/artifacts/`), so no model,
database, or runtime fetch sits between the reader and the compiled knowledge --
a direct instantiation of the "compile, then serve" principle.

### 6.3 Knowledge Compiler

The compiler establishes a semantic build boundary. Rather than treating the
corpus as a collection of isolated documents, the compiler (`knowledge-compiler/`)
runs a deterministic pipeline:

```
ingest -> normalize -> extract -> graph -> search -> emit -> verify
```

- **ingest** reads the 177 Markdown sources.
- **normalize** parses frontmatter and applies the taxonomy.
- **extract** derives entities, relationships, claims, and references per post.
- **graph** builds a NetworkX entity/relationship graph.
- **search** builds a BM25 index with tokenized entries.
- **emit** writes `index.json`, `<slug>.json` sidecars, `graph.json`, and
  `search.json` to `public/artifacts/`.
- **verify** runs the fail-closed gate (Section 6.4).

Because the build is deterministic and runs locally, the semantic structure can be
version-controlled, diffed, and reproduced -- the same reproducibility guarantee
the fleet substrate applies to authorization.

### 6.4 Artifact Model and Verification Gate

Compiled artifacts provide stable intermediate representations between source
content and runtime inference -- analogous to a compiler producing an
intermediate representation before machine execution. The analogy is useful
because it establishes a principled distinction between authoring, semantic
transformation, and execution.

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

### 6.5 Architectural Documentation

A10 also contains explicit architectural documentation and architectural decision
records (`docs/ADR-*.md`). This is significant for agentic systems because
architectural decisions themselves become persistent knowledge. An autonomous
system can reason over not only the source content but also the constraints and
decisions that govern how the software is constructed -- turning the ADRs into a
governable specification layer.

---

## 7. Sovereign Agent Fleet

Sovereign Agent Fleet implements the governance side of the architecture. Its
central principle is that the system should not require trust in the model. The
fleet architecture separates researcher, analyst, and operator responsibilities
and places deterministic controls between cognition and consequential execution.

### 7.1 Governed Multi-Agent Architecture

The multi-agent structure provides role separation:

- **Research** produces observations.
- **Analysis** transforms observations into conclusions or recommendations.
- **Operations** executes authorized actions.

The separation reduces the likelihood that one probabilistic process can
simultaneously generate an objective, authorize itself, execute the resulting
action, and declare success. The agent roles (`researcher`, `analyst`,
`operator`, `human`, `tool`) are enumerated in the crypto foundation and are
carried on the identity certificate, never on the output of a model.

The architecture is domain-general. A single registry
(`domain_registry/__init__.py`) holds one uniform capability table spanning six
external consumers:

| Domain | Capability constant |
|--------|---------------------|
| exchange / finance | `CAP_TRADE_EXECUTE` |
| incident / security | `CAP_INCIDENT_REMEDIATE` |
| supply / logistics | `CAP_SUPPLY_REORDER` |
| hypothesis / research | `CAP_HYPOTHESIS_RUN` |
| mirror / self-observability | `CAP_MIRROR_SELF_TUNE` |
| grid / energy | `CAP_GRID_BALANCE` |

Adding a domain is a one-line table edit plus a thin adapter; the frozen
`decide()` substrate is unchanged. This is the M0 domain-generality result: the
same authorization function governs six categorically distinct workloads without
any modification to the substrate itself.

### 7.2 Identity and Root of Trust

Cryptographic identity establishes a machine-verifiable representation of
principals. The architecture derives a key hierarchy from an Argon2id-strengthened
master secret:

```
master secret (Argon2id) -> root Ed25519 signing key -> per-agent Ed25519 identity keys
```

The root key issues **agent certificates** (`AgentCert`) that are signed by the
root and that the agent cannot alter -- the agent does not hold the root key, so
it cannot grant itself scope, capabilities, or role. Certificates bind to an
`agent_id`, `role`, `capabilities`, issuance/expiry, and a `cert_seq`, and are
signed under a root epoch so rotated roots do not invalidate historical chains.

This provides a stronger trust primitive than textual role names: *an agent
claiming to be an operator is not necessarily an operator; a cryptographically
recognized principal possessing the appropriate authorization is.*

### 7.3 Deterministic Policy and the `decide()` Substrate

Policy is implemented independently of the language model. The authorization
function `decide()` in `fleet/epistemic/decision.py` is a **pure, deterministic
function** whose inputs are:

- `identity` -- who is asking (`AgentIdentity`),
- `grant` -- an externally-signed `AuthorityGrant`,
- `authorization_scope` -- what the grant references,
- `request` -- what is requested (`AuthorizationRequest`),
- `constraints` -- deterministic `GovernanceConstraints`,
- `current_epoch`, `now` -- governed state,
- `trusted_issuer_pubkey_pem` -- the pinned governance trust anchor.

Crucially, `decide()` accepts **no probability, confidence, model score,
belief, or calibration value.** The verdict is determined entirely by capability
plus grant scope plus epoch currency plus policy. The function returns an
`AuthorizationDecision` whose state deliberately contains *no epistemic field*.

The evaluation proceeds as an ordered guard sequence, each failure returning
`BLOCKED`:

1. A grant must exist (the substrate never manufactures one from a request or
   thin air).
2. The grant signature must verify against the **pinned trusted issuer key** --
   not a key the grant describes for itself, which would let an attacker
   self-sign a valid-looking grant.
3. The grant must be current (epoch supersession is primary; a TTL is a
   backstop).
4. The grant is bound to this identity and cannot be transferred.
5. The grant must reference exactly the scope being exercised.
6. The requested capability must be within the granted scope.
7. Deterministic policy read returns `AUTO`, `HUMAN`, or `BLOCKED`.

The verdict `AUTO` permits execution without further human involvement; `HUMAN`
routes the request to an explicit approval boundary; `BLOCKED` terminates it. A
model can request an action that policy rejects, and the rejection remains valid
even if the model provides an elaborate justification -- because the model is not
an input to `decide()`.

### 7.4 Capability Authorization

Capabilities provide a finer-grained authority model than simply assigning broad
permissions to an agent. A capability is evaluated in conjunction with role,
identity, requested operation, and relevant constraints, producing a
least-privilege architecture. The registry's one-line capability table is the
single source of truth for which literal capability strings the substrate will
ever see; the substrate itself is agnostic to domain semantics.

### 7.5 Approval Protocol

Human approval provides an additional boundary for consequential operations. The
approval record can be bound to the specific operation being authorized rather
than becoming an indefinite permission grant. This transforms human involvement
from an informal conversational interaction into a structured authorization
event -- a signed approval that the verifier can check independently of any model
narration.

### 7.6 Execution Boundary

Execution occurs only after authorization. This is the point at which the system
crosses from epistemic computation into consequential computation, and therefore
one of the most important security surfaces in the entire architecture. The
executor receives an already-authorized operation and performs it within the
defined execution environment; it does not re-decide permission.

### 7.7 Independent Verification

The verification layer independently determines whether the resulting artifact or
state satisfies the required conditions. This makes verification a separate
computational role rather than a statement emitted by the same model that
generated the action. In the quantitative domain, for example, evidence objects
are signed by a producer key and verified against that key; a forged or tampered
signature fails verification rather than being trusted (Section 12).

### 7.8 Tamper-Evident Audit

The audit architecture provides a durable, append-only record of important system
events. The `AuditTrail` wraps an Ed25519-signed hash-chain ledger
(`ChrisCryptSN.Ledger`): each entry is signed and linked to the previous entry,
with a signed checkpoint so tail truncation is detectable. Signed records and
hash chaining allow later verification that historical evidence has not been
silently rewritten. This converts the execution history into a verifiable artifact
rather than an ordinary mutable log. Per-record confidentiality is provided
separately by an envelope (XChaCha20-Poly1305 with HKDF per-record subkeys), so
encryption protects secrecy while signatures protect integrity -- the two
concerns are not conflated.

---

## 8. Integrating Knowledge and Governance

The integration between A10 and Sovereign Agent Fleet is best understood as a
**protocol alignment** rather than a conventional application dependency.

- A10 supplies the **knowledge plane**.
- Sovereign Agent Fleet supplies the **authority plane**.
- The compiler supplies the **semantic transformation boundary**.
- The governance system supplies the **authorization boundary**.

```
Human Knowledge
   -> Compiled Knowledge Artifacts
   -> Retrieval
   -> Probabilistic Cognition
   -> Typed Proposal
   -> Deterministic Policy
   -> Human Approval (if required)
   -> Execution
   -> Independent Verification
   -> Signed Evidence
```

This architecture permits autonomous reasoning without granting autonomous
authority.

### 8.1 Epistemic Boundary

The epistemic boundary determines what the system believes or proposes. The model
operates here. Because the model is probabilistic, its outputs must be considered
hypotheses, recommendations, or proposals rather than facts with inherent
authority. The A10 corpus reinforces this: the canonical Markdown is the source of
truth; the compiled graph and sidecars are *derivatives* that can be regenerated
when the source changes.

### 8.2 Authority Boundary

The authority boundary determines what the system is permitted to do. The model
does **not** operate here. Policy, identity, capability, approval, and
verification operate here. This distinction is arguably the central contribution
of the architecture.

### 8.3 Knowledge-to-Action Pipeline

The architecture creates a controlled transition from knowledge to action:

1. Knowledge informs cognition.
2. Cognition produces a proposal.
3. The proposal requests an action.
4. Policy authorizes or rejects the action.
5. Execution performs the authorized action.
6. Verification determines whether the resulting state is valid.

This makes the transition from information to consequence explicit and
inspectable.

### 8.4 Provenance and Evidence

The final stage establishes provenance. A future auditor can ask not merely what
the system produced, but which knowledge artifacts informed the reasoning, which
proposal was generated, which policy applied, who or what authorized it, what
execution occurred, and whether independent verification succeeded. This creates
a pathway toward reproducible agentic computation. The A10 sidecar's
`provenance` block (`source`, `compiler`, `git_sha`, `generated_at`) and the
fleet's signed audit trail are complementary provenance mechanisms at the two
ends of the pipeline.

---

## 9. Formal System Model

Let the knowledge corpus be represented by:

```
K = { d_1, d_2, ..., d_n }
```

where each `d_i` is a canonical knowledge document.

The compiler transforms the corpus into:

```
A = C(K)
```

where `C` is the deterministic compilation function and `A` is the resulting
artifact set.

A retrieval function produces:

```
R(q, A)
```

for query `q`.

The probabilistic cognition function produces a proposal:

```
P = M(R(q, A), S)
```

where `M` is the model and `S` is system context.

Critically:

```
P ∉ Authority
```

Instead, a policy function evaluates the proposal:

```
D = G(I, P, Caps, Policy, State)
```

where `I` is the authenticated principal identity, `Caps` are capabilities, and
`State` represents relevant system state (epoch, clock). Only when:

```
D = ALLOW
```

may execution occur. Execution produces:

```
E = X(P, State)
```

Verification independently evaluates:

```
V = Verify(E, Expected, Evidence)
```

The security model depends on preventing the model from bypassing `G`.

### 9.1 Trust Model

The architecture assumes that the model may be unreliable. It also assumes that
external inputs may be malicious, tools may return malformed information, agents
may produce invalid proposals, network infrastructure may fail, and logs may be
attacked. The architecture therefore places trust in **deterministic
boundaries** rather than in individual cognitive components.

### 9.2 Threat Model

The system considers model hallucination, malicious prompts, unauthorized
capability requests, corrupted artifacts, altered audit records, compromised
execution environments, and invalid tool results as classes of adversarial or
failure conditions. The intended response is not to make each subsystem perfect;
the intended response is to **constrain the consequences of subsystem failure.**

### 9.3 State Transitions

The architecture can be represented as a governed state machine:

```
REQUEST -> INTENT -> PLAN -> ACTION -> TOOL -> OBSERVATION
        -> EVIDENCE -> VERIFICATION -> ARTIFACT -> APPROVAL -> FINAL -> AUDIT
```

The importance of this sequence is that each transition creates an opportunity for
validation. A model cannot simply collapse the entire state machine into one
response.

### 9.4 Safety Invariants

The architecture establishes several core invariants:

- Model output **cannot** directly authorize an action.
- Unknown capabilities **fail closed**.
- Execution occurs **only** after authorization.
- Consequential operations **may** require explicit human approval.
- Verification is **independent** from the original proposal.
- Evidence is **cryptographically bound** to relevant events.
- Cloud infrastructure does **not** inherently possess local authority.

These invariants remain meaningful even if the underlying model is replaced.

---

## 10. Security Properties

The resulting architecture provides several important security properties.

- **Authority separation** prevents cognition from directly becoming execution
  authority.
- **Least privilege** constrains what an individual agent can request or perform.
- **Cryptographic identity** establishes machine-verifiable principals.
- **Tamper evidence** makes historical modification detectable.
- **Independent verification** prevents the executor from becoming the sole source
  of truth regarding its own success.
- **Human approval** provides an explicit authorization boundary for
  high-consequence operations.
- **Local authority** reduces dependence on external infrastructure as a root of
  trust.

These properties are complementary rather than interchangeable.

---

## 11. Computational Sovereignty

Computational sovereignty in this architecture does not simply mean running
software locally. It means retaining control over the **fundamental authority
relationships** of the system.

- Local computation allows the knowledge corpus and semantic compiler to remain
  under direct control.
- Version-controlled source provides reproducibility.
- Compiled artifacts can be regenerated deterministically.
- Models can be swapped without disturbing the authority substrate.
- Cloud systems can be used as mirrors or execution substrates **without
  becoming authoritative.**

This produces a more robust relationship between local computation and cloud
infrastructure. The cloud becomes infrastructure. It does not become sovereignty.
In the fleet's own knowledge-architecture decision (D19), the graph stays local;
a cloud Firestore audit-ledger mirror carries only the compiled artifact
manifest -- hashes and evidence references, not the graph -- preserving
local-first authority. Cross-session continuity uses the manifest; the working
graph is rebuilt locally per task.

---

## 12. Engineering Validation

The strongest validation of the architecture is not a single benchmark; it is the
**preservation of invariants across multiple domains.** The Sovereign Agent Fleet
substrate has been exercised through governed scenarios -- incident remediation
and simulated financial operations among them -- while maintaining the same
underlying governance substrate.

The financial adapter is particularly significant because it demonstrates that a
consequential domain can be represented without embedding financial assumptions
into the core governance architecture. The same `decide()` function governs trade
execution, incident remediation, supply reordering, hypothesis runs, mirror
self-tuning, and grid balancing. Each domain supplies only a capability constant
and a thin adapter; none modify the substrate.

A10 provides another validation domain because its problem is fundamentally
different -- a knowledge and publication system rather than a trading or incident
system -- yet the same authority model remains applicable when the two are
composed. This suggests the architecture is not intrinsically tied to one
application category.

Two concrete engineering facts anchor the claim:

1. **Reproducible verification.** The A10 compiler's gate re-derives every
   `content_hash` from source and refuses to emit on any mismatch, so a corrupted
   or divergent source cannot silently produce an artifact. This is the same
   fail-closed discipline the fleet applies to authorization.
2. **Forgery resistance.** In the quantitative evidence layer, a forged signature
   or a tampered prior hash fails `verify()`; the verifier checks against the
   producer's public key, not the artifact's self-description. This mirrors the
   fleet's `decide()` requirement that a grant verify against a *pinned* trusted
   issuer key rather than a self-asserted one.

---

## 13. Applications and Extensions

### 13.1 Autonomous Software Engineering

An agent could inspect a repository, compile its architecture into structured
artifacts, propose a modification, execute tests, and produce a signed
verification artifact. The model would determine what it believes should change;
the governance system would determine whether the proposed modification is
authorized; the test system would independently determine whether the change is
valid.

### 13.2 Financial Simulation

The same architecture can govern simulated financial decisions. Market
observations become evidence; a strategy produces a proposal; risk policy
evaluates the proposal; a simulated exchange executes the action; independent
accounting verifies resulting positions and balances. The model therefore never
becomes the financial authority.

### 13.3 Incident Response

The system can observe an incident, produce a diagnosis, propose remediation,
request authorization, execute the remediation, and independently verify that the
incident state has changed as expected. This allows autonomous response without
giving the diagnostic model unrestricted operational authority.

### 13.4 Scientific Knowledge Systems

The A10 knowledge compiler provides a foundation for scientific knowledge
compilation. Documents become structured entities and relationships; agents can
generate hypotheses; evidence can be associated with claims; experiments can be
represented as proposed actions; verification can evaluate experimental outcomes.
The resulting architecture creates a potential bridge between knowledge graphs,
retrieval systems, scientific reasoning, and governed experimentation -- exactly
the compose-knowledge-plane-with-authority-plane pattern of Section 8.

### 13.5 Personal Institutional Memory

The architecture is also applicable to personal knowledge systems. A person's
written corpus can become persistent machine-readable institutional memory. The
important distinction is that the system does not replace the person's original
knowledge with model-generated memory; the source remains canonical, and the
model becomes an interpreter and reasoner over the source. This is the operating
model of A10 itself.

---

## 14. Limitations

The current architecture does not eliminate the fundamental uncertainty of
probabilistic cognition. A governed system can prevent an unauthorized action,
but it cannot guarantee that every authorized proposal is intellectually correct.

Semantic compilation can also introduce errors if extraction, normalization,
classification, or relationship construction is incorrect; the verification gate
checks integrity and reproducibility, not semantic truth.

Cryptographic integrity does not establish semantic truth: a perfectly signed
false statement remains false. Independent verification can also fail when the
expected state is itself poorly specified.

The architecture therefore addresses **authority, provenance, and execution
integrity** rather than solving general artificial-intelligence alignment. It is a
systems answer to a systems problem, not a claim about model correctness.

---

## 15. Future Research

Several research directions follow naturally.

1. **Formal verification of the governance state machine**, proving the safety
   invariants of Section 9.4 hold for all reachable states.
2. **Stronger provenance binding** between compiled knowledge artifacts and
   model-generated proposals, so a proposal is cryptographically linked to the
   specific `git_sha` and content hashes it reasoned over.
3. **Graph-based semantic compilation** in which relationships between documents
   become first-class, queryable artifacts (the A10 `graph.json` is a first step).
4. **Cryptographically signed retrieval provenance**, extending the sidecar
   `provenance` block into the runtime retrieval path.
5. **Multi-agent consensus over evidence** rather than merely consensus over model
   outputs.
6. **Formal policy specification** for heterogeneous agent capabilities, so the
   registry's capability table is machine-checked against an explicit policy.
7. **Reproducible agent execution** in which model versions, prompts, retrieved
   artifacts, policies, tool inputs, outputs, and execution states can be
   reconstructed.
8. **A generalized sovereign knowledge protocol** that allows independent
   applications to consume the same governance primitives.

---

## 16. Discussion

The architectural implication of this work is that agentic intelligence should not
be conceptualized solely as a model plus tools. A more useful abstraction is:

> **Intelligence = Memory + Retrieval + Cognition + Governance + Execution +
> Verification + Evidence**

Under this model, the language model is only one component. This distinction is
important because increasing model capability does not inherently solve the
authority problem. A more capable model can produce better proposals; it can also
produce more consequential mistakes. Therefore capability and governance should
scale independently.

The architecture developed in A10 and Sovereign Agent Fleet attempts to establish
exactly this separation:

- The knowledge system determines what information exists and how it can be
  compiled.
- The model determines what it believes should happen.
- The governance system determines what is permitted.
- The executor performs authorized actions.
- The verifier determines whether execution produced the expected result.
- The evidence system records what happened.

This produces a system in which no single probabilistic component is responsible
for the entire chain from perception to consequence.

---

## 17. Conclusion

This work presents an architecture for sovereign knowledge and agentic execution
based on a simple but consequential principle:

> **Do not trust the model; trust the execution protocol.**

The A10 system demonstrates how a technical publication environment can evolve
into a compilable knowledge substrate in which human-authored information remains
canonical while semantic representations become structured computational
artifacts -- compiled deterministically, verified by a fail-closed gate, and
served without a model on the request path.

Sovereign Agent Fleet demonstrates how autonomous cognition can be placed behind
deterministic governance, cryptographic identity, capability authorization, human
approval, controlled execution, independent verification, and tamper-evident
evidence -- with a single frozen `decide()` substrate governing six distinct
domains without modification.

Their combination establishes a broader architecture for sovereign intelligence.
The model is allowed to reason. The model is allowed to propose. The model is
allowed to generate hypotheses. The model is **not** allowed to become authority
merely because it generated the proposal.

This distinction provides a foundation for building autonomous systems whose
safety properties do not depend entirely upon the behavior of the underlying
model. The resulting system is therefore not simply an AI application; it is a
**governed computational environment** in which knowledge can be compiled,
cognition can operate over that knowledge, actions can be proposed, authority can
be evaluated independently, execution can be constrained, outcomes can be verified,
and evidence can be retained.

That architecture provides a practical path from conventional retrieval-augmented
applications toward sovereign intelligence systems in which memory becomes
architecture, cognition becomes modular, authority becomes deterministic, and
autonomy becomes verifiable.

---

## 18. References

1. Kliewer, D. *A10: Knowledge Compilation and Sovereign Knowledge System.*
   GitHub repository, `kliewerdaniel/a10`.
2. Kliewer, D. *Sovereign Agent Fleet: Governed Multi-Agent Execution
   Architecture.* GitHub repository, `sovereign-agent-fleet`.
3. Kliewer, D. *Sovereign Agent Fleet — Epistemic Architecture Synthesis* and
   *Agent Boundary and Decision Semantics* (internal architecture docs,
   `docs/architecture/`).
4. Microsoft. *Agent Governance Toolkit.* Architecture and security
   documentation.
5. NIST. *Artificial Intelligence Risk Management Framework* (AI RMF 1.0).
   National Institute of Standards and Technology, 2023.
6. NIST. *Zero Trust Architecture*, SP 800-207. National Institute of Standards
   and Technology, 2020.
7. RFC 8032. *Edwards-Curve Digital Signature Algorithm (EdDSA): Ed25519 and
   Ed448.* Internet Engineering Task Force, 2017.
8. Bernstein, D. J., et al. *The Ed25519 Signature Scheme.* (EdDSA specification,
   RFC 8032).
9. Lewis, P., et al. *Retrieval-Augmented Generation for Knowledge-Intensive NLP
   Tasks.* NeurIPS, 2020.
10. Yao, S., et al. *ReAct: Synergizing Reasoning and Acting in Language Models.*
    ICLR, 2023.
11. Argon2. *The memory-hard password hashing function* (PHC winner). RFC 9106.
12. Bernstein, D. J. *ChaCha20-Poly1305 and the XChaCha construction.* (AEAD
    cipher used by the fleet envelope layer.)

---

*Author's note: This paper is the research articulation of two implemented,
tested systems. Every architectural claim above is backed by code in the A10
knowledge compiler (`knowledge-compiler/`) and the Sovereign Agent Fleet
substrate (`fleet/`), and by the cross-domain registry
(`domain_registry/`). Where the prose says "the system does X," the cited module
does X.*
