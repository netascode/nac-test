# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tests for backward-compatibility import shims.

Verifies that legacy import paths emit DeprecationWarning and resolve
to the canonical objects, ensuring downstream repos are not broken
by the v2.0 module restructuring.
"""

import importlib
import inspect
import sys
import warnings
from pathlib import Path

import pytest

# (legacy_module, canonical_module, exported_name)
SHIMS = [
    ("nac_test.pabot", "nac_test.robot.pabot", "run_pabot"),
    ("nac_test.robot_writer", "nac_test.robot.robot_writer", "RobotWriter"),
]

# Expected required (no-default) parameters for exported callables.
# Guards against signature changes that would break downstream callers.
# Format: (module, attr, {param_name: annotation, ...})
EXPECTED_SIGNATURES = [
    ("nac_test.robot.pabot", "run_pabot", {"path": Path}),
    (
        "nac_test.robot.robot_writer",
        "RobotWriter",
        {
            "data_paths": list[Path],
            "filters_path": Path | None,
            "tests_path": Path | None,
        },
    ),
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
        and f"'{legacy_module}' is deprecated" in str(w.message)
    ]
    assert len(shim_warnings) == 1
    assert getattr(mod, attr) is canonical


@pytest.mark.parametrize(
    "module, attr, expected_params",
    EXPECTED_SIGNATURES,
    ids=[s[1] for s in EXPECTED_SIGNATURES],
)
def test_signature_contract(
    module: str, attr: str, expected_params: dict[str, type]
) -> None:
    """Guard against required-arg changes that would break downstream callers."""
    obj = getattr(importlib.import_module(module), attr)
    sig = inspect.signature(obj)
    required = {
        name: p.annotation
        for name, p in sig.parameters.items()
        if p.default is inspect.Parameter.empty
    }
    assert required == expected_params
