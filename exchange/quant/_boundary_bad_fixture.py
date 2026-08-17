"""Deliberately-violating fixture for the exchange/quant import-wall test.

This module imports a FORBIDDEN authority module (``fleet.fin.domain.assess``)
so the boundary checker has something to catch. It is asserted to be detected by
``exchange/tests/test_boundary_quant.py`` — if the checker ever stops firing,
that test FAILS (self-validation), proving the wall is live.
"""
from fleet.fin.domain import assess  # FORBIDDEN — authority import inside quant

FORBIDDEN_REF = assess
