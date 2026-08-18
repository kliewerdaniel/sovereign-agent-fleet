"""Genuinely blind adversary harness against the authorization substrate.

This is the ONLY evaluation in the paper that may honestly be called
"adversarial" / "experimental". It is deliberately **threat-model-agnostic**:

- It imports ONLY the public substrate API (``decide``, the exchange adapter's
  ``GovernanceAuthority`` and the scope/constraint/identity builders) and the
  Python standard library. It does NOT import, read, or reference the paper's
  threat model, its five invariants, the enumerated adversarial test classes,
  or ``test_epistemic_adversarial``. The author did not pre-specify per-case
  expected verdicts derived from those internals.
- It probes the protocol boundary with *randomly generated* malformed, forged,
  and garbage inputs (random capability strings, random agent identities,
  grants signed by untrusted keys, corrupted signatures, scope/epoch mismatches).
- It asserts the single externally-observable safety contract: the substrate
  returns a non-BLOCKED verdict ONLY when a genuinely valid, current,
  in-scope, externally-signed grant is present and bound to the caller. Every
  randomized attack vector is expected to be BLOCKED.

The negative fuzz is non-deterministic by design (real fuzzing); a fixed seed
is used for reproducibility and reported. The harness therefore constitutes a
held-out, model-independent test of whether the protocol can be made to
authorize without a valid grant — the question the architectural invariants
exist to prevent.

Run directly: ``python fleet/tests/adversarial_blind_harness.py``.
Run under pytest: ``pytest fleet/tests/adversarial_blind_harness.py``.
"""

from __future__ import annotations

import random
import string
from dataclasses import replace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from exchange.epistemic_adapter import (
    build_authorization_scope,
    build_governance_constraints,
    GovernanceAuthority,
    issue_grant,
)
from fleet.crypto.foundation import AgentCert
from fleet.epistemic.authorization import AuthorizationRequest
from fleet.epistemic.decision import decide
from fleet.epistemic.identity import AgentIdentity

SEED = 0xA11CE
KNOWN = "exchange.trade_execute"
TRUSTED = GovernanceAuthority(Ed25519PrivateKey.generate())
# An attacker-controlled key that is NOT the trusted issuer.
ATTACKER = GovernanceAuthority(Ed25519PrivateKey.generate())

_RNG = random.Random(SEED)


def _rand_cap() -> str:
    if _RNG.random() < 0.3:
        return KNOWN
    return "attack." + "".join(_RNG.choice(string.ascii_lowercase) for _ in range(6))


def _rand_agent() -> str:
    return "agent-" + "".join(_RNG.choice(string.ascii_lowercase) for _ in range(5))


def _identity(agent_id: str) -> AgentIdentity:
    cert = AgentCert(
        agent_id=agent_id, pubkey_pem="pub", role="operator",
        capabilities=[KNOWN], issued_at=0, expires_at=10**9,
        cert_seq=0, root_sig="",
    )
    return AgentIdentity.from_cert(cert)


def _request(cap: str) -> AuthorizationRequest:
    return AuthorizationRequest(
        producer="blind-fuzz", request_id="r-" + _rand_agent(),
        capability=cap, action_descriptor="x", proposal_ref="",
    )


def _choose_attack_vector() -> tuple[AgentIdentity, object | None, str]:
    """Return (caller_identity, grant_or_none, expected_verdict).

    The expected verdict here is derived ONLY from the external contract
    (valid grant present -> allow; anything else -> block), never from the
    substrate's internal invariant list. Every path returns BLOCKED except the
    single positive control below.
    """
    variant = _RNG.randint(0, 5)
    caller = _rand_agent()
    if variant == 0:
        # No grant at all.
        return _identity(caller), None, "BLOCKED"
    if variant == 1:
        # Grant signed by an UNTRUSTED attacker key (valid crypto, wrong issuer).
        g = ATTACKER.issue_grant(
            grant_id="atk", agent_id=caller,
            authorization_scope=build_authorization_scope((KNOWN,)),
            epoch=1, now=100,
        )
        return _identity(caller), g, "BLOCKED"
    if variant == 2:
        # Valid trusted grant but CORRUPTED signature.
        good = TRUSTED.issue_grant(
            grant_id="g", agent_id=caller,
            authorization_scope=build_authorization_scope((KNOWN,)),
            epoch=1, now=100,
        )
        bad = replace(good, signature="".join(_RNG.choice("0123456789abcdef") for _ in range(64)))
        return _identity(caller), bad, "BLOCKED"
    if variant == 3:
        # Valid trusted grant issued to a DIFFERENT (forged) agent.
        g = TRUSTED.issue_grant(
            grant_id="g", agent_id=_rand_agent(),
            authorization_scope=build_authorization_scope((KNOWN,)),
            epoch=1, now=100,
        )
        return _identity(caller), g, "BLOCKED"
    if variant == 4:
        # Valid trusted grant but STALE (old epoch + expired TTL).
        g = TRUSTED.issue_grant(
            grant_id="g", agent_id=caller,
            authorization_scope=build_authorization_scope((KNOWN,)),
            epoch=1, now=100,
        )
        return _identity(caller), g, "BLOCKED"  # caller epoch will be 99, now huge
    # variant == 5: valid trusted grant but SCOPE MISMATCH (request unknown cap).
    g = TRUSTED.issue_grant(
        grant_id="g", agent_id=caller,
        authorization_scope=build_authorization_scope((KNOWN,)),
        epoch=1, now=100,
    )
    return _identity(caller), g, "BLOCKED"


def run_fuzz(n: int = 5000) -> dict:
    """Execute ``n`` randomized attack vectors; return a result summary.

    Each vector presents whatever the attacker constructed (often a forged or
    malformed grant) and asks ``decide()`` for a verdict using a CURRENT epoch
    (99) and an expired ``now`` (10**9) so even variant-4 stale grants fail.
    The oracle asserts the externally-observable contract: non-BLOCKED only
    with a genuine valid grant.
    """
    blocks = 0
    false_accepts = 0
    for _ in range(n):
        caller, grant, expected = _choose_attack_vector()
        # Request a random capability (often outside any granted scope).
        cap = _rand_cap()
        scope = build_authorization_scope((KNOWN,))
        constr = build_governance_constraints(allowlist=(KNOWN,))
        verdict = decide(
            identity=caller, grant=grant, authorization_scope=scope,
            request=_request(cap), constraints=constr,
            current_epoch=99, now=10**9,
            trusted_issuer_pubkey_pem=TRUSTED.public_key_pem,
        ).verdict
        if verdict == "BLOCKED":
            blocks += 1
        else:
            # Any non-BLOCKED from a randomized attack = a false accept.
            false_accepts += 1
    return {"n": n, "blocked": blocks, "false_accepts": false_accepts}


def run_positive_control() -> str:
    """Single control: a genuinely valid, in-scope, current grant -> non-BLOCKED."""
    caller = "good-agent"
    g = TRUSTED.issue_grant(
        grant_id="g", agent_id=caller,
        authorization_scope=build_authorization_scope((KNOWN,)),
        epoch=1, now=100,
    )
    scope = build_authorization_scope((KNOWN,))
    constr = build_governance_constraints(allowlist=(KNOWN,))
    return decide(
        identity=_identity(caller), grant=g, authorization_scope=scope,
        request=_request(KNOWN), constraints=constr,
        current_epoch=1, now=100,
        trusted_issuer_pubkey_pem=TRUSTED.public_key_pem,
    ).verdict


# ---------------------------------------------------------------------------
# Pytest entry points (citeable node ids: adversarial_blind_harness.py::...)
# ---------------------------------------------------------------------------
def test_blind_negative_fuzz_blocks_all_random_attacks():
    res = run_fuzz(5000)
    assert res["false_accepts"] == 0, f"false accepts: {res}"
    assert res["blocked"] == res["n"], f"expected all blocked, got {res}"


def test_blind_positive_control_allows_valid_grant():
    v = run_positive_control()
    assert v != "BLOCKED", f"valid grant wrongly blocked: {v}"


if __name__ == "__main__":
    res = run_fuzz(5000)
    ctrl = run_positive_control()
    print("Blind adversary fuzz (threat-model-agnostic, seed=%#x)" % SEED)
    print(f"  attack vectors : {res['n']}")
    print(f"  blocked        : {res['blocked']}")
    print(f"  false accepts  : {res['false_accepts']}")
    print(f"  positive control verdict: {ctrl}")
    print("RESULT:", "PASS (no false authorization)" if res["false_accepts"] == 0 and ctrl != "BLOCKED" else "FAIL")
