"""Phase 2 — SEMANTIC architectural dependency-policy for ``fleet.epistemic``.

The existing ``test_boundary_epistemic.py`` enforces the import wall *syntactically*
(via AST import scanning). That is useful but fragile in one direction: the day
someone relocates a function-local ``from cryptography import ...`` up to module
top-level, the syntactic check has to be re-taught. The actual invariant the
architecture cares about is *semantic*, not textual:

    ``fleet.epistemic`` may depend on the APPROVED cryptographic foundation API
    (``fleet.crypto.foundation``: canonical_bytes / sha256 / AgentCert), but it
    MUST NOT become a cryptographic or governance RUNTIME itself.

"Must not become a runtime" decomposes into testable, import-location-independent
facts. The scan below walks the **AST identifier nodes** (``Name`` / ``Attribute``
chains / import targets / function-def names) of the real substrate — docstrings
and comments are not identifier nodes, so this scan is blind to prose and to where
an import sits. Relocating an import from inside a function to the top of a module
does not change the set of identifier nodes, so the policy holds either way.

The three runtime facts:

  1. NO KEY CUSTODY / NO MINTING. The layer never produces a signature or holds a
     private key. It only *_verifies_* externally-issued grants. (The trusted
     issuer key is passed IN by the caller, never created inside the layer.)

  2. NO GRANT-MINTING FUNCTION. There is no function in the package that *issues*
     an AuthorityGrant. Authority is always externally signed; the package only
     validates what it is handed.

  3. NO GOVERNANCE/FINANCIAL RUNTIME. The layer references no execution, trading,
     risk, mandate, or fleet-governance symbols. It READS deterministic
     ``GovernanceConstraints`` (policy data) but never executes governance.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EPISTEMIC_DIR = _REPO_ROOT / "fleet" / "epistemic"


# ---------------------------------------------------------------------------
# Semantic scan: collect the set of CODE identifiers (not prose) from the package
# ---------------------------------------------------------------------------
def _substrate_files():
    return [
        p for p in sorted(_EPISTEMIC_DIR.rglob("*.py"))
        if p.name != "_boundary_bad_fixture.py"
    ]


def _identifier_strings() -> set[str]:
    """Every code identifier in the substrate: dotted attribute chains, bare names,
    import-module targets, and function-def names. Docstrings/comments are excluded
    by construction (they are not identifier AST nodes)."""
    ids: set[str] = set()
    for p in _substrate_files():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    ids.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    ids.add(node.module)
                for alias in node.names:
                    ids.add(alias.name)
            elif isinstance(node, ast.Attribute):
                ids.add(_dotted(node))
            elif isinstance(node, ast.Name):
                ids.add(node.id)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                ids.add(node.name)
    return ids


def _dotted(node: ast.AST) -> str:
    parts: list[str] = []
    cur: ast.AST | None = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def _function_names() -> list[str]:
    names: list[str] = []
    for p in _substrate_files():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.append(node.name)
    return names


# Crypto *runtime* / key-custody identifier roots that must NEVER appear.
_FORBIDDEN_CRYPTO_RUNTIME = (
    "SecretVault", "IdentityRoot", "master_to_kek", "hash_password_safe",
    "verify_password_safe", "private_key", "Ed25519PrivateKey", "sign",
)

# Governance / financial *runtime* identifier roots the neutral layer must never use.
_FORBIDDEN_GOVERNANCE_RUNTIME = (
    "decide_trade", "Mandate", "RiskLayer", "TradeDecision", "RiskBudget",
    "CalibrationState",
)


def test_substrate_holds_no_private_key_and_cannot_sign():
    """RUNTIME fact 1: the layer verifies but never mints. No key-custody / signing
    identifier may appear anywhere in the substrate (code identifiers only)."""
    ids = _identifier_strings()
    offenders = sorted(s for s in _FORBIDDEN_CRYPTO_RUNTIME if s in ids)
    assert not offenders, (
        "fleet.epistemic must not contain crypto-runtime / key-custody identifiers; "
        f"found: {offenders}"
    )


def test_substrate_has_no_grant_minting_function():
    """RUNTIME fact 2: there is no function that ISSUES an AuthorityGrant. Authority
    is always externally signed; the layer only validates it."""
    minting_names = [
        n for n in _function_names()
        if re.search(r"(sign|issue|mint|create|forge|grant)_?(grant|authority)", n, re.I)
    ]
    assert not minting_names, (
        "fleet.epistemic must not define a grant-minting function; "
        f"found: {minting_names}"
    )
    import fleet.epistemic as fe
    assert hasattr(fe, "AuthorityGrant")
    # The package must not EXPORT a grant-signer either.
    exported = [n for n in dir(fe) if not n.startswith("_")]
    signers = [n for n in exported if re.search(r"(sign|issue|mint)_?(grant|authority)", n, re.I)]
    assert not signers, f"package must not export a grant-signer; found {signers}"


def test_substrate_references_no_governance_financial_runtime():
    """RUNTIME fact 3: the neutral layer never executes governance/financial logic.
    It reads deterministic GovernanceConstraints data but runs no mandate/risk/trade."""
    ids = _identifier_strings()
    offenders = sorted(s for s in _FORBIDDEN_GOVERNANCE_RUNTIME if s in ids)
    assert not offenders, (
        "fleet.epistemic must not reference governance/financial runtime identifiers; "
        f"found: {offenders}"
    )


def test_only_decide_produces_an_authorization_decision():
    """AuthorizationDecision must be constructed in exactly ONE place — decide().
    No other module may mint a permission object, which prevents authority from
    being produced outside the deterministic gate."""
    constructions: list[tuple[str, int]] = []
    for p in _substrate_files():
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\bAuthorizationDecision\s*\(", line):
                constructions.append((p.name, i))
    rogue = [(f, n) for (f, n) in constructions if f != "decision.py"]
    assert not rogue, (
        "AuthorizationDecision may only be constructed inside decision.py; "
        f"found elsewhere: {rogue}"
    )
    assert constructions, "expected at least the decide() construction site"


def test_crypto_dependency_is_confined_to_foundation_api():
    """SEMANTIC companion to the syntactic wall: every ``fleet.crypto`` import
    target must be exactly ``fleet.crypto.foundation``. The layer must not reach
    into other crypto submodules (vaults, identity roots, key derivation)."""
    ids = _identifier_strings()
    crypto_refs = {s for s in ids if s == "fleet.crypto" or s.startswith("fleet.crypto.")}
    bad = sorted(r for r in crypto_refs if r != "fleet.crypto.foundation")
    assert not bad, (
        "fleet.epistemic may only depend on fleet.crypto.foundation; "
        f"found reference to: {bad}"
    )


def test_crypto_usage_is_verification_not_custody():
    """Drill into the one place that touches crypto: AuthorityGrant.verify_grant.
    It must use load_pem_public_key + verify (read-only verification), never sign or
    generate. This pins the 'validate, do not mint' boundary at the call level."""
    auth_src = (_EPISTEMIC_DIR / "authority.py").read_text(encoding="utf-8")
    assert "verify(" in auth_src, "verify_grant must actually call verify()"
    assert "load_pem_public_key" in auth_src, "verify_grant must load the (public) key"
    for bad in ("sign(", "Ed25519PrivateKey", "private_key", "generate("):
        assert bad not in auth_src, (
            f"authority.py must not contain '{bad}' — it only verifies grants"
        )


def test_trusted_issuer_key_is_supplied_not_created():
    """The decisive structural claim: decide() requires a TRUSTED issuer public key
    to be PASSED IN, and the layer creates no such key. This is what makes the
    substrate a validation layer, not a governance runtime."""
    import inspect

    from fleet.epistemic import decide

    params = set(inspect.signature(decide).parameters)
    assert "trusted_issuer_pubkey_pem" in params, \
        "decide() must take the trust anchor as a caller-supplied argument"
    names = _function_names()
    key_factory = [n for n in names if re.search(r"(generate|create|load).*(key|keypair|pubkey)", n, re.I)]
    assert not key_factory, (
        f"fleet.epistemic must not create key material; found {key_factory}"
    )


def test_substrate_still_imports_cleanly_and_is_not_a_runtime():
    """Integration: importing the package must not transitively pull in any
    forbidden runtime module, confirming the semantic policy holds at load time."""
    import sys

    before = set(sys.modules)
    import fleet.epistemic  # noqa: F401

    after = set(sys.modules)
    newly = {m for m in (after - before) if not m.startswith("_")}
    forbidden = {
        "fleet.cognition", "exchange.quant", "exchange.governance", "fleet.fin",
        "fleet.simenv", "fleet.layers", "fleet.gcp", "fleet.api",
        "fleet.crypto.vault", "fleet.crypto.identity",
    }
    leaked = sorted(m for m in newly if any(m == f or m.startswith(f + ".") for f in forbidden))
    assert not leaked, f"fleet.epistemic transitively imported runtime modules: {leaked}"
