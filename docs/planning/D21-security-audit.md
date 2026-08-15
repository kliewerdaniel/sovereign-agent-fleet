# D21 — Security Audit & Hardening Plan (Fortified Enterprise Fleet)

> Status: **AUDIT COMPLETE — findings below; hardening + extensions implemented in
> follow-up commits on branch `security-hardening-d21`.**
> Scope: `fleet/` (Phases 0–5), `requirements*.txt`, `docs/planning/*`.
> Method: read-everything-first, then probe each trust-boundary boundary with a
> constructive adversarial test before any fix (rule #3 of the build prompt).
> Baseline before changes: **78 tests green**.

The thesis we are defending is *"Do not trust the model. Trust the execution
protocol."* The audit asks the honest question: **does the protocol actually
enforce that, or does it only narrate it?** Several places were narration-only.
This document lists every gap, rates it, and the rest of the branch closes them.

---

## 1. Dependency & supply-chain review

**Finding S1 (MEDIUM).** `requirements.txt` and `requirements-gcp.txt` use
unbounded version ranges (`cryptography>=42.0`, `pynacl>=1.5`,
`argon2-cffi>=23.1`, `pytest>=8.0`, and the entire GCP set). A future
`pip install` can pull a breaking or vulnerable minor. There is no lockfile and
no SBOM, and no CI gate that fails the build on a newly-disclosed critical.

- **Action:** add a pinned `requirements.lock.txt` (hashes via `pip freeze` /
  `pip-tools`), add `pip-audit` to CI, and ship a `Makefile`/`ci` job that runs
  `pip-audit -r requirements.txt` and fails on any CRITICAL/HIGH. (Pinning is a
  hardening step, not a weakening — the public repo already declares a minimum
  that is satisfied by the pinned versions.)

**Finding S2 (LOW / accepted-with-note).** GCP deps are correctly *not* in the
test venv (lazy imports in `bridge.py`/`console.py`), so the 78-test suite runs
offline. Good. We keep that property; the SBOM/CI job runs against both files.

---

## 2. Cryptographic review (`fleet/crypto/`)

**Finding C1 — Argon2id parameters (LOW).** `envelope.derive_kek` uses
`time_cost=3, memory_cost=65536 (64 MiB), parallelism=1`. OWASP 2023 for
Argon2id recommends ≥ 19 MiB memory *and* ≥ 2 passes, OR higher memory at one
pass. 64 MiB / 3 passes is **conservative and fine** for a local KDF. No change
required; documented as compliant. (`kdf.py`'s PBKDF2 fallback at 600k rounds is
also acceptable but is correctly never selected when argon2 is present.)

**Finding C2 — XChaCha20-Poly1305 nonce reuse (LOW, verified safe).** Nonce is
`secrets.token_bytes(24)` per `seal()` call (envelope.py:134). 192-bit nonce
space ⇒ reuse probability is cryptographically negligible even under heavy
concurrent writers, and each record uses a *distinct HKDF subkey* (per
record-name), so a theoretical nonce repeat under different keys is still safe.
`JsonStore.put` is `threading.RLock`-guarded, so two threads cannot interleave a
write. **No fix needed; this is genuinely sound.** Noted because the prompt
asked to confirm it, and it confirms clean.

**Finding C3 — Ed25519 hash-chain detects tamper + reorder, NOT replay alone
(HIGH-ish, but *mitigated by design*).** `Ledger.verify_chain` checks
`seq` monotonicity and `prev` linkage, so **reordering is detected** and any
byte change to an entry breaks its own signature. Genuine *replay* (re-inserting
an already-seen valid entry) is not separately prevented by the chain — but the
system has **two independent replay defenses** that the audit confirms are
effective:
  1. Gateway idempotency key memoization (gateway.py:75) — replay of an
     authority request returns the *prior* verdict, never a fresh grant.
  2. Runtime `idempotent()` (runtime.py:114) — replay of a consequential write
     returns the recorded result, never double-executes.

So replay is closed at the *authorization* and *execution* layers even though
the chain itself is append-only. **Finding: document this explicitly** (it was
implicit) and add an adversarial test proving a forged-but-valid-looking
replayed entry doesn't re-grant (it can't, because nothing re-derives authority
from a ledger entry).

---

## 3. Key lifecycle & disaster recovery (CRITICAL GAP)

**Finding K1 — No root-key backup / recovery story (HIGH).** `IdentityRoot`
derives its Ed25519 root key solely from `master_secret` + `salt` (foundation.py:107).
There is **no documented or tested** path for:
  - backing up the root key material (the `salt` + an encrypted master export),
  - rotating the *root* itself (only agent certs rotate — D14 — not the root),
  - disaster recovery if the root is lost (every agent cert becomes unverifiable
    → total fleet outage) or *compromised* (every cert must be re-issued under a
    new root, and the **public verifier would reject the new root with no
    continuity proof**).

D14 (agent revoke/rotate) is real but is *not* a root-DR plan. This is the
single most important "what if the root is compromised" question a skeptical
reviewer asks.

- **Action:** add `RootBackup` + `RootRotation` support in `foundation.py`:
  - `IdentityRoot.export_seed(kek)` → encrypted, key-wrapped root seed blob
    (so backup never persists plaintext); `IdentityRoot.from_seed(...)` restore.
  - `IdentityRoot.rotate_root(new_root)` that re-signs all *currently-live* agent
    certs under the new root and bumps a `root_epoch`, emitting signed
    `registry.root_rotate` entries. The public verifier gains a
    `verify_with_root_history(root_pubs)` that accepts any epoch's root — so a
    verifier presented with the old+new root public keys still validates the
    historical chain. Fail-closed: rotation requires the *old* root key to sign
    the rotation record (no silent root swap).
  - Add adversarial tests: (a) restore-from-backup yields a root that verifies
    the same live certs; (b) an operator presenting a cert re-signed under the
    new root verifies; (c) a cert re-signed under an *unauthorized* new root is
    rejected.

---

## 4. Policy engine — default-deny coverage

**Finding P1 — Default-deny confirmed, BUT a structural gap (MEDIUM).**
`decide()` returns DENY for any `(role, capability)` not in `_ROLE_CAPS`
(policy.py:52). There is **no implicit-allow path** — good. However:

  - The policy table is a module global with no integrity binding. The Gateway
    trusts `decide()` returns honestly because it's local code — fine for local
    first. But nothing prevents a *future* code change from accidentally adding
    an implicit allow. We want a machine-checked property, not a code review.
  - `human` role has capability `approve_deny` but the **Operator execution path
    never cryptographically verifies the human's `ApprovalRecord` signature**
    (see finding A1 below). Policy says "consequential requires approval" but the
    enforcement is a Python `is None` check on a passed-in dict — an attacker who
    controls the Operator process could pass a forged approval dict.

- **Action:** (a) add a property test (`hypothesis`) asserting `decide()` denies
  every capability not enumerated in `_ROLE_CAPS`, for all five roles + arbitrary
  unknown roles. (b) Close A1 (below).

---

## 5. Model Armor (D12) — injection/PII recall

**Finding M1 — Injection patterns are a small denylist (MEDIUM).** `armor.py`
strips 7 regex patterns. That blocks the *demonstrated* attacks but is not a
recall guarantee. Missing classes:
  - Base64 / unicode-homoglyph / zero-width-obfuscated instructions that don't
    match the ASCII regexes.
  - "Instruction in a different field/language" (e.g. non-English imperatives).
  - Payloads that arrive as *structured* fields whose *values* are instructions
    (already caught per-field, but only for `allowed_fields` that are strings —
    a nested dict/list value bypasses `scan_injection`).

**Finding M2 — PII redaction can be bypassed (MEDIUM).** `_PII_PATTERNS` runs on
the final artifact text, but `redact_pii` is only called in `Operator.act`
(artifact) and `draft_with_brain` (outreach body). The *evidence extract*
produced by the Researcher is **never PII-scanned before it becomes a record**
and is later embedded into QualifiedIntel. A tool returning a raw SSN in
`extract` would be persisted verbatim. Also the card regex
(`\b(?:[\d -]*?){13,19}\b`) is greedy and can mis-redact; and there is **no test
measuring redaction recall**.

- **Action:** (a) broaden injection scanning to recurse into nested
  dict/list values; (b) add a PII scan at the Researcher evidence boundary
  (before `Handoff.make`), not just at the artifact; (c) ship an adversarial
  corpus (`tests/fixtures/armor_corpus.json`) of injection + PII samples and a
  test that asserts per-class recall ≥ a threshold (fail-closed: if a known-bad
  sample passes, the test fails). (d) Keep denylist approach (no probabilistic
  classifier, per D12) but make it exhaustive and measured.

---

## 6. GCP trust boundary — one-directional verification (CONFIRMED, with one fix)

**Finding G1 — Verification is one-directional (GOOD).** `GcpBridge.replicate`
sends only signed artifacts; `FirestoreVerifier` accepts only public keys; the
console (console.py) is a display+signature shell and never writes authority
back into the local runtime. There is **no code path** by which a GCP document
or console POST mutates local cert/ledger/policy state. Confirmed clean.

**Finding G2 — Console approval endpoint is a stub (MEDIUM, accepted-for-demo
but must be loud).** `console.wsgi_app` `/approve` only echoes the request
(`{"received": req}`) and does **not** actually verify a human signature or bind
to a pending action. In production this must verify the human's `ApprovalRecord`
cryptographically *server-side*. For the demo this is explicitly documented as a
shell; we harden it by (a) having `/approve` reject requests that don't carry a
cryptographically-verifiable `human_sig` over the pending action, and (b) logging
a loud `console.unverified_approval_rejected` audit event when it doesn't.

---

## 7. CRITICAL — execution-time authorization gaps (the "narration vs enforcement" gaps)

**Finding A1 — Human approval is NOT verified at execution (HIGH).** In
`Operator.act` (runtime.py:271, 282) the check is `approval is None`. The
`approval` dict is passed in by the caller. **Nothing verifies the
`human_sig`** against the human cert's public key, and nothing binds the
approval to the specific `artifact_hash` / `action_id` / `capability` being
executed. So a caller who controls the Operator process can supply a
*forged* approval dict with any content and the consequential action proceeds.
This directly contradicts D17 ("signed ApprovalRecord"). The beats pass only
because the *test* passes a genuinely-signed dict — the protocol doesn't check
it.

**Fix (Phase 2, top priority):** add `verify_approval(record, human_cert_pem,
action_id, capability, artifact_hash)` in a new `fleet/layers/approval.py`
(reusing `FirestoreVerifier.verify_cert`-style public-key check). `Operator.act`
calls it and **fails closed** (returns `blocked`) if the signature is missing,
invalid, or doesn't bind to this exact action. Add adversarial tests:
  - forged approval (wrong human key) → blocked;
  - approval for a *different* action_id/capability → blocked;
  - approval whose `human_id` is not a `human` role cert → blocked;
  - valid approval → proceeds.

**Finding A2 — `capability` string is never bound to the issued cert (MEDIUM).**
`Operator.act` requests authority for a `capability` arg, and the Gateway checks
`cert.role`→capability via policy. That part is fine. But the **artifact_hash in
the approval does not have to match the artifact being committed** (A1 covers
the sig; this covers the *binding*). Tighten A1's verification to require
`approval["artifact_hash"] == sha256(redacted_artifact)` and
`approval["action_id"] == idempotency_key` and
`approval["capability"] == capability`. Fail-closed on mismatch.

**Finding A3 — Gateway caches verdicts globally with no expiry (LOW).** The
idempotency cache (`gateway.py:61`) is an unbounded in-memory dict. For a demo
fine; for production it's a slow memory leak and a potential replay-window
concern if an agent's cert is revoked but a cached GRANT verdict still exists.
**Fix:** on `registry.revoke`, invalidate cached verdicts for that agent_id (the
Gateway already has `auth_ok` re-checking each call, so a revoked agent is denied
on the *next* fresh request — but a *cached* one could still return a stale
GRANT). Add `gateway.invalidate(agent_id)` called from `registry.revoke`, and a
test proving a revoked agent's cached grant is dropped.

---

## 8. Fail-closed audit (rule #4)

| Location | Current behavior | Verdict |
|---|---|---|
| `IdentityRoot.verify_cert` | returns `False` on any exception | ✅ fail-closed |
| `verify_tool_envelope` | returns `False` on bad sig | ✅ |
| `Ledger.verify_chain` | returns `False` on any break | ✅ |
| `FirestoreVerifier` | raises/returns `False` | ✅ |
| `Operator.act` approval | **passes if dict present** | ❌ **fixed in A1** |
| `envelope.derive_kek` | **raises if argon2 absent** | ✅ (explicitly fails closed) |
| `Envelope` AEAD selection | raises if no backend | ✅ |
| `decide()` unknown pair | DENY | ✅ |
| `Gateway` forged cert | DENY + signed event | ✅ |
| **root key loss** | **total outage, no recovery** | ❌ **fixed in K1** |

---

## 9. Phase 2 hardening priority (implementation order)

1. **A1 + A2** — cryptographic verification + strict binding of human approval.
   (Unsigned/unapproved action could execute.) TOP.
2. **K1** — root key backup + rotation with verifier continuity.
3. **A3** — revoke invalidates Gateway cache.
4. **M1 + M2** — Armor recursion + evidence-boundary PII + measured corpus.
5. **P1** — property test for default-deny.
6. **G2** — console rejects unverifiable approvals.
7. **S1 + S2** — pin deps, SBOM, `pip-audit` CI.
8. **C3** — document replay defense + add test.

---

## 10. Phase 3 — innovative extensions (proposed, D2x docs to follow)

Candidates ranked; the build picks the top 2–3 that extend the *verifiable
execution protocol* without granting the model new authority:

- **E1 — Zero-knowledge policy-compliance proof (D22).** Let the Operator prove
  "this action complied with policy X and had a valid human approval" to a third
  party *without* revealing CRM data. Natural extension of the "public
  verifiability without authority" claim. Implementable with a Schnorr/Ed25519
  signature over a commitment to (policy_id, artifact_hash, approval_sig,
  root_epoch) — the verifier checks the math, not the data. **No model authority
  added.** Strong fit.
- **E2 — Multi-brain consensus / cross-check (D23).** Require two independently
  configured Brain backends to agree on VERIFIED-tier claims before the gate
  accepts them; disagreement is itself a signed audit event. Extends D16's
  content-correctness check with *independent* probabilistic corroboration.
  **Model stays proposal-only; the gate still decides.** Strong fit.
- **E3 — Formal property test of the policy engine (D24).** `hypothesis` over
  all role/capability pairs proving no reachable state grants an undeclared
  capability, plus a TLA+/Alloy sketch of the Gateway state machine. Cheap,
  high-credibility, no authority change. Included.
- **Rejected:** WASM/sandboxed tool execution and attested runtime (TPM/enclave)
  — both valuable but require runtime/infra the local-first demo doesn't have and
  would blur the "authority stays local" story if done half-way. Deferred with
  reason; not implemented in this branch (would cross a trust-boundary
  completeness gap if stubbed).

---

## Changelog (updated as the branch lands)

- **audit written (this file).** Baseline 78 tests green.
- **Phase 2 hardening — ALL COMMITTED.** (A1/A2) `fleet/layers/approval.py`
  `verify_approval` + `Operator.act` fail-closed binding; (K1) root seed backup +
  rotation w/ verifier continuity + `rotate_root` clears gateway cache; (A3)
  gateway re-validates liveness on idempotency replay + binds cache to
  (agent_id, cert_seq); (M1) recursive injection scan; (M2) evidence-boundary PII
  deep-scan/redact + adversarial corpus; (P1) exhaustive default-deny property
  test; (G2) console verifies human sig server-side, fails closed; (S1) locked
  pins + `fleet-security` CI (pip-audit + SBOM); (C3) replay-defense test.
  Suite now 107 green (`b1a7423` A1/A2, `952e0b9` K1/A3, `ca414fb` M1/M2/A3,
  `4a531d4` P1/G2/S1/C3).
- **Phase 3 extensions — design docs + impl + adversarial tests in progress.**
  (E1) zero-knowledge policy-compliance proof; (E2) multi-brain consensus gate.
  (E3, the formal policy property test, is already delivered as P1.)
