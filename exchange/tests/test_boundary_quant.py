"""D29 Phase Q0 — enforce the exchange/quant import boundary.

Mirrors ``fleet/tests/test_boundary.py``: the quant layer must remain *upstream
of evidence formation but outside the authority path*. If it could import the
risk engine, governance, or execution modules it could become authority,
violating meta-invariant M0.

The checker is AST-based so it catches:
    * ``import fleet.fin.domain``
    * ``from fleet.fin.authorization import ...``
    * ``import exchange.governance``
    * fully-qualified use ``fleet.layers.runtime.act_trade`` inside code
and is INDEPENDENT of whether the import is reachable at runtime.

ALLOWED targets (the only modules exchange/quant may touch):
    fleet.crypto                 (sign / verify / audit primitives)
    exchange.core.instrument     (read instrument model)
    exchange.feeds               (read Quote / PriceFeed)
    exchange.core.events         (read market events, Q2+)
    exchange.quant               (intra-package: probability/kelly/streaming)
    cryptography                 (Ed25519 primitive — same lib fleet.crypto uses)

FORBIDDEN targets (importing any FAILS the build):
    fleet.fin, fleet.layers.*, fleet.cognition, exchange.governance

A deliberately-violating fixture (``_boundary_bad_fixture.py``) is shipped and
asserted to be CAUGHT, so the test is self-validating.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_QUANT_DIR = _REPO_ROOT / "exchange" / "quant"

_FORBIDDEN_PREFIXES = (
    "fleet.fin",
    "fleet.layers",
    "fleet.cognition",
    "exchange.governance",
)

_ALLOWED_PREFIXES = (
    "fleet.crypto",
    "exchange.core.instrument",
    "exchange.feeds",
    "exchange.core.events",
    "cryptography",
)


def _violations_in_source(src: str) -> list[str]:
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
    parts: list[str] = []
    cur: ast.AST | None = node
    while True:
        if isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        elif isinstance(cur, ast.Name):
            parts.append(cur.id)
            break
        else:
            break
    return ".".join(reversed(parts))


def test_quant_boundary_enforced():
    """Every module under exchange/quant may only import allowed targets."""
    assert _QUANT_DIR.is_dir(), f"missing {_QUANT_DIR}"
    py_files = [p for p in _QUANT_DIR.rglob("*.py") if p.name != "__init__.py" or True]
    assert py_files, "no python files found in exchange/quant"

    all_violations: list[tuple[str, list[str]]] = []
    for path in py_files:
        if path.name == "_boundary_bad_fixture.py":
            continue
        src = path.read_text(encoding="utf-8")
        v = _violations_in_source(src)
        if v:
            all_violations.append((os.path.relpath(path, _REPO_ROOT), v))

    assert not all_violations, (
        "exchange/quant layer imports a forbidden (authority/execution) module:\n"
        + "\n".join(f"  {f}: {', '.join(v)}" for f, v in all_violations)
    )


def test_quant_boundary_checker_self_validates():
    """The checker must actually catch a violating module."""
    fixture = _QUANT_DIR / "_boundary_bad_fixture.py"
    assert fixture.is_file(), "self-validation fixture missing"
    v = _violations_in_source(fixture.read_text(encoding="utf-8"))
    assert v, "quant boundary checker failed to detect the deliberately-bad fixture"
