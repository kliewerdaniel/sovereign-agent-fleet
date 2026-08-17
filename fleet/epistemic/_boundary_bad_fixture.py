"""Deliberately-violating fixture for the epistemic boundary checker.

This module MUST be caught by ``fleet/tests/test_boundary_epistemic.py``. If the
checker ever stops firing, that test's self-validation assertion fails, proving
the guard is live. It is excluded from the "every module must be clean" scan (as
the cognition/quant fixtures are in the existing checkers).
"""
import fleet.fin  # FORBIDDEN — must be caught
from exchange.governance import decide_trade  # FORBIDDEN — must be caught
