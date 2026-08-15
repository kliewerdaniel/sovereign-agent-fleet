"""DELIBERATELY VIOLATING FIXTURE — DO NOT FIX.

This module exists only so ``fleet/tests/test_boundary.py`` can prove its
checker actually catches forbidden imports. It must import a forbidden module
(gateway/policy/runtime/fin/...) and/or use a forbidden qualified path. If this
file ever stops being flagged, the boundary test itself is broken.

This file is skipped by the package-wide scan and only inspected by
``test_boundary_checker_self_validates``.
"""
from fleet.layers.gateway import Gateway  # forbidden: authority issuer
from fleet.layers.policy import decide  # forbidden: authorization policy
import fleet.fin  # forbidden: financial risk engine

# Also a fully-qualified use that should be caught:
_trigger = fleet.layers.runtime.act_trade
