# D25 — Sandboxed Operator Tool Execution (Round-2 re-evaluation of D21 deferral)

## Scope (as narrowed by the Round-2 prompt)
The original D21 audit deferred **both** WASM/sandboxed tool execution **and**
attested-runtime (TPM/enclave) identity, reasoning that the local-first demo
lacks the infra and a half-built version would blur the trust-boundary story.
Round 2 asked to re-evaluate only the *narrower* of the two: sandbox whatever the
`Operator` actually executes for `crm_write` (currently a plain function call)
behind a capability-scoped subprocess or WASM boundary, so a compromised tool
implementation cannot exceed its granted capability even if it tries.

The attested-runtime half is **not** re-evaluated here — it still requires infra
this repo does not have (a TPM/enclave or a remote attestation service) and remains
correctly deferred.

## What the Operator actually executes (read before design)
Traced `Operator.act` (`fleet/layers/runtime.py:259`) and its only effecting path:

1. `registry.discover(agent_id)` — authenticate operator identity (root-signed cert).
2. `intel_handoff.consume(...)` — consume a signed cross-agent handoff envelope.
3. `redact_pii(artifact_text)` — PII guard (D12).
4. D16 boundary: HALLUCINATION → blocked; ASSERTED → require signed approval.
5. `request_authority(live, capability, idempotency_key)` — **Gateway is the
   capability authority**. Denied → blocked.
6. If `require_approval`: `verify_approval(...)` — A1/A2 fail-closed binding.
7. `Runtime.idempotent(idempotency_key, _commit)` where `_commit` does exactly one
   thing: `self.rt.log_audit("operator.final", ...)` and returns a record dict.

A repo-wide search for `subprocess` / `os.system` / `shell=True` / `Popen` /
`requests` / `httpx` / `socket` / `smtplib` across `fleet/layers/` returns **zero**
matches. There is **no external tool adapter, no CRM client, no network call, no
file write, no shell invocation** in the `Operator` path or anywhere in the
runtime. The only "external effect" of a consequential action is a deterministic,
signed append to the local audit ledger — which is itself a Control-Plane primitive,
not a tool.

This is consistent with the design thesis: the fleet is a **protocol**, not a
tool-running host. `crm_write` is *modeled* as a capability the Gateway grants and
the ledger records; the demo "writes" are simulated (D11).

## Decision: DEFER (again), with a sharper, code-grounded reason
Introducing a capability-scoped subprocess/WASM boundary around `Operator.act`
would be **theater, not a trust-boundary improvement**, for three concrete reasons:

1. **There is no tool to sandbox.** Wrapping `log_audit` (a pure, signed append)
   in a subprocess or WASM module adds a process/serialization boundary around a
   function that already cannot exceed its inputs. It would *increase* attack
   surface (IPC, a new serialization trust boundary) while protecting nothing.

2. **The real capability boundary is already enforced earlier and fail-closed.**
   Before any effect, `request_authority` (Gateway) and `verify_approval` (A1/A2)
   decide whether the action may occur at all. A *compromised tool
   implementation* cannot "exceed its granted capability" because the capability
   grant is checked by the deterministic Control Plane, not by the tool. The tool
   has no power to exceed — there is no tool.

3. **A real sandbox would require inventing the very surface that doesn't exist.**
   To make sandboxing *meaningful* we would first have to add an actual external
   effect (a real CRM adapter, a real network egress) — which is a product change
   (D11 says the CRM is simulated; D6 says authority/keys stay local), not a
   hardening pass. Shipping a sandbox around a simulated effect is the exact
   "half-implemented version that blurs the trust-boundary story" the original D21
   deferral correctly warned against.

### If this is ever reopened (future criteria)
A sandbox becomes the right control **only after** a concrete external effect
exists — e.g. a real `fleet/gcp/bridge.py` write path or an outbound `outreach_send`
adapter. At that point the correct shape is:

- The adapter runs as a **separate, least-privilege process** (or WASM module)
  that receives *only* the already-authorized, already-redacted artifact plus a
  **capability token** minted by the Gateway; it holds no signing key, no cert
  store, no broader network than the single destination.
- The Gateway-issued token is the *only* thing the sandboxed process can use to
  act; escaping the sandbox yields at most one pre-authorized, pre-redacted write.
- This is captured here as the design intent so the next owner does not re-litigate
  the empty case.

## Deliverables in this branch
- This design doc (`D25-operator-sandbox.md`) recording the re-evaluation and the
  deferred-with-reason decision.
- **No code change** — adding a sandbox around a non-existent tool would violate
  ground rule #5 (no silent degradation / no theater) and #2 (trust boundary
  unchanged, correctly). The 123-test suite remains green.

## Relationship to the rest of the trust model
The capability boundary that *does* exist — Gateway authority + A1/A2 approval
binding + A3 cache liveness + M1/M2 armor + R2 consensus visibility — is the
actual defense-in-depth around consequential actions. Sandboxing is a property of
*where code runs*; this system's security comes from *what is allowed to decide*,
and that decision lives in the deterministic Control Plane, not in a tool host.
