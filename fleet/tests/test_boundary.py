"""D28 Phase 1 — enforce the cognition/governance import boundary.

This test is the structural guarantee behind the Sovereign Cognitive
Architecture: ``fleet/cognition`` must remain *downstream of evidence creation
but upstream of authority*. If it could import the governance/authorization
modules it could become authority, violating meta-invariant M0.

The checker is AST-based so it catches:
    * ``import fleet.layers.gateway``
    * ``from fleet.layers.policy import decide``
    * fully-qualified use ``fleet.layers.runtime.act_trade`` inside code
and it is INDEPENDENT of whether the import is reachable at runtime.

ALLOWED targets (the only governance-adjacent modules cognition may touch):
    fleet.crypto                 (sign / verify / audit primitives)
    fleet.layers.handoff         (emit signed Handoffs, read the ledger)

FORBIDDEN targets (importing any of these FAILS the build):
    fleet.layers.gateway, fleet.layers.policy, fleet.layers.registry,
    fleet.layers.runtime, fleet.layers.incident, fleet.layers.verification,
    fleet.layers.approval, fleet.layers.consensus, fleet.layers.armor,
    fleet.layers.brain, fleet.layers.compliance, fleet.fin, fleet.simenv,
    fleet.gcp

A deliberately-violating fixture (``_boundary_bad_fixture.py``) is shipped and
asserted to be CAUGHT, so the test is self-validating: if the checker ever
stops firing, the fixture assertion fails the suite.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COGNITION_DIR = _REPO_ROOT / "fleet" / "cognition"

# Modules cognition may NEVER import (authority / execution / heavy env).
_FORBIDDEN_PREFIXES = (
    "fleet.layers.gateway",
    "fleet.layers.policy",
    "fleet.layers.registry",
    "fleet.layers.runtime",
    "fleet.layers.incident",
    "fleet.layers.verification",
    "fleet.layers.approval",
    "fleet.layers.consensus",
    "fleet.layers.armor",
    "fleet.layers.brain",
    "fleet.layers.compliance",
    "fleet.fin",
    "fleet.simenv",
    "fleet.gcp",
)

# Empty string => allow bare "fleet.crypto" / "fleet.layers.handoff" only.
_ALLOWED_PREFIXES = (
    "fleet.crypto",
    "fleet.layers.handoff",
)


def _violations_in_source(src: str) -> list[str]:
    """Return human-readable violation strings for forbidden imports/usages."""
    violations: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # A syntax error is not an import violation; the linter catches those.
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
        # Also catch fully-qualified attribute access like fleet.layers.runtime.act_trade
        elif isinstance(node, ast.Attribute):
            chain = _dotted(node)
            if chain and (_startswith(chain, _FORBIDDEN_PREFIXES)):
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


def test_cognition_boundary_enforced():
    """Every module under fleet/cognition may only import allowed targets."""
    assert _COGNITION_DIR.is_dir(), f"missing {_COGNITION_DIR}"
    py_files = [p for p in _COGNITION_DIR.rglob("*.py")]
    assert py_files, "no python files found in fleet/cognition"

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
        "cognition layer imports a forbidden (authority/execution) module:\n"
        + "\n".join(f"  {f}: {', '.join(v)}" for f, v in all_violations)
    )


def test_boundary_checker_self_validates():
    """The checker must actually catch a violating module."""
    fixture = _COGNITION_DIR / "_boundary_bad_fixture.py"
    assert fixture.is_file(), "self-validation fixture missing"
    v = _violations_in_source(fixture.read_text(encoding="utf-8"))
    assert v, "boundary checker failed to detect the deliberately-bad fixture"
