"""Phase 0 — enforce the ``fleet/epistemic`` neutral-layer import boundary.

Mirrors ``fleet/tests/test_boundary.py`` and ``exchange/tests/test_boundary_quant.py``:
the neutral epistemic substrate must remain the *least-privileged* layer. It may
only import ``fleet.crypto.foundation`` (canonical hashing + ``AgentCert``) and
the standard library. If it imported financial/domain/authority/execution modules
it could become authority or leak domain logic, violating the Round 4 contract
(R1/R5/R11).

The checker is AST-based so it catches ``import fleet.fin``, ``from
exchange.governance import decide_trade``, and fully-qualified ``fleet.layers...``
usage, independent of runtime reachability.

ALLOWED targets (the only modules fleet/epistemic may touch):
    fleet.crypto                 (sign / verify / hashing primitives)
    fleet.crypto.foundation      (canonical_bytes, sha256, AgentCert)

FORBIDDEN targets (importing any FAILS the build):
    fleet.cognition, exchange.quant, exchange.governance, fleet.fin,
    fleet.simenv, fleet.layers.*, fleet.gcp, fleet.api

A deliberately-violating fixture (``_boundary_bad_fixture.py``) is shipped and
asserted to be CAUGHT, so the test is self-validating.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EPISTEMIC_DIR = _REPO_ROOT / "fleet" / "epistemic"

# Empty packages in the financial/domain/authority/execution space that the
# neutral layer may NEVER depend on.
_FORBIDDEN_PREFIXES = (
    "fleet.cognition",
    "exchange.quant",
    "exchange.governance",
    "fleet.fin",
    "fleet.simenv",
    "fleet.layers",
    "fleet.gcp",
    "fleet.api",
)

# The only dependency the neutral substrate is permitted (R2 / F2 of the design).
_ALLOWED_PREFIXES = (
    "fleet.crypto",
)


def _violations_in_source(src: str) -> list[str]:
    """Return human-readable violation strings for forbidden imports/usages."""
    violations: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        mod = None
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name
                if mod in _FORBIDDEN_PREFIXES or _startswith(mod, _FORBIDDEN_PREFIXES):
                    violations.append(f"import {mod}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod in _FORBIDDEN_PREFIXES or _startswith(mod, _FORBIDDEN_PREFIXES):
                violations.append(f"from {mod} import ...")
        elif isinstance(node, ast.Attribute):
            chain = _dotted(node)
            if chain and _startswith(chain, _FORBIDDEN_PREFIXES):
                violations.append(f"qualified use {chain}")
    return violations


def _startswith(name: str, prefixes) -> bool:
    return any(name == p or name.startswith(p + ".") for p in prefixes)


def _dotted(node: ast.AST) -> str:
    """Reconstruct a dotted name from an Attribute/Name chain (best effort)."""
    parts: list[str] = []
    cur: ast.AST | None = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def test_epistemic_boundary_enforced():
    """Every module under fleet/epistemic may only import allowed targets."""
    assert _EPISTEMIC_DIR.is_dir(), f"missing {_EPISTEMIC_DIR}"
    py_files = [p for p in _EPISTEMIC_DIR.rglob("*.py")]
    assert py_files, "no python files found in fleet/epistemic"

    all_violations: list[tuple[str, list[str]]] = []
    for path in py_files:
        # Skip the self-validating bad fixture (handled separately).
        if path.name == "_boundary_bad_fixture.py":
            continue
        src = path.read_text(encoding="utf-8")
        v = _violations_in_source(src)
        if v:
            all_violations.append((os.path.relpath(path, _REPO_ROOT), v))

    assert not all_violations, (
        "fleet/epistemic layer imports a forbidden (domain/authority/execution) module:\n"
        + "\n".join(f"  {f}: {', '.join(v)}" for f, v in all_violations)
    )


def test_epistemic_boundary_checker_self_validates():
    """The checker must actually catch a violating module."""
    fixture = _EPISTEMIC_DIR / "_boundary_bad_fixture.py"
    assert fixture.is_file(), "self-validation fixture missing"
    v = _violations_in_source(fixture.read_text(encoding="utf-8"))
    assert v, "epistemic boundary checker failed to detect the deliberately-bad fixture"


def test_epistemic_package_imports_without_forbidden_transitive_deps():
    """Importing fleet.epistemic must not pull in forbidden heavy modules."""
    import sys

    before = set(sys.modules)
    import fleet.epistemic  # noqa: F401

    after = set(sys.modules)
    newly_loaded = {m for m in (after - before) if not m.startswith("_")}
    forbidden = {
        "fleet.cognition",
        "exchange.quant",
        "exchange.governance",
        "fleet.fin",
        "fleet.simenv",
        "fleet.layers",
        "fleet.gcp",
        "fleet.api",
    }
    leaked = sorted(m for m in newly_loaded if any(m == f or m.startswith(f + ".") for f in forbidden))
    assert not leaked, f"fleet.epistemic transitively imported forbidden modules: {leaked}"
