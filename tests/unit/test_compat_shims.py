# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tests for backward-compatibility import shims.

Verifies that legacy import paths emit DeprecationWarning and resolve
to the canonical objects, ensuring downstream repos are not broken
by the v2.0 module restructuring.
"""

import importlib
import sys
import warnings

import pytest

# (legacy_module, canonical_module, exported_name)
SHIMS = [
    ("nac_test.pabot", "nac_test.robot.pabot", "run_pabot"),
    ("nac_test.robot_writer", "nac_test.robot.robot_writer", "RobotWriter"),
]


@pytest.mark.parametrize(
    "legacy_module, canonical_module, attr",
    SHIMS,
    ids=[s[0] for s in SHIMS],
)
def test_shim_emits_deprecation_warning(
    legacy_module: str, canonical_module: str, attr: str
) -> None:
    sys.modules.pop(legacy_module, None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        mod = importlib.import_module(legacy_module)

    canonical_mod = importlib.import_module(canonical_module)
    canonical = getattr(canonical_mod, attr)

    shim_warnings = [
        w
        for w in caught
        if issubclass(w.category, DeprecationWarning)
        and f"{legacy_module} has moved" in str(w.message)
    ]
    assert len(shim_warnings) == 1
    assert canonical_module in str(shim_warnings[0].message)
    assert getattr(mod, attr) is canonical
