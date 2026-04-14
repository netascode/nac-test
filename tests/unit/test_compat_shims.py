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

# Required (no-default) parameters for exported callables at the time the
# shims were written.  When a test below fails, the canonical signature has
# changed — review and, if needed, update the shim layer to keep the legacy
# API working for downstream callers.
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

    # Shim objects are now wrappers/subclasses, not identical to canonical
    shim_obj = getattr(mod, attr)
    if inspect.isclass(shim_obj):
        assert issubclass(shim_obj, canonical)
    else:
        assert callable(shim_obj)


@pytest.mark.parametrize(
    "module, attr, expected_params",
    EXPECTED_SIGNATURES,
    ids=[s[1] for s in EXPECTED_SIGNATURES],
)
def test_shim_signature_reminder(
    module: str, attr: str, expected_params: dict[str, type]
) -> None:
    """Fail when the canonical signature changes so developers review the shim layer."""
    obj = getattr(importlib.import_module(module), attr)
    sig = inspect.signature(obj)
    required = {
        name: p.annotation
        for name, p in sig.parameters.items()
        if p.default is inspect.Parameter.empty
    }
    assert required == expected_params


def test_run_pabot_coerces_str_to_path() -> None:
    """Verify run_pabot shim coerces str to Path before delegating."""
    from unittest.mock import patch

    import nac_test.pabot

    with patch("nac_test.pabot._canonical_run_pabot") as mock_canonical:
        mock_canonical.return_value = 0

        # Test str input → coerced to Path
        result = nac_test.pabot.run_pabot("some/string/path")
        assert result == 0
        mock_canonical.assert_called_once()
        call_args = mock_canonical.call_args
        assert call_args[0][0] == Path("some/string/path")

        mock_canonical.reset_mock()

        # Test Path input → passed through unchanged
        path_input = Path("another/path")
        result = nac_test.pabot.run_pabot(path_input)
        assert result == 0
        mock_canonical.assert_called_once()
        call_args = mock_canonical.call_args
        assert call_args[0][0] is path_input


def test_robot_writer_coerces_str_args() -> None:
    """Verify RobotWriter shim coerces str args to Path before delegating."""
    from unittest.mock import patch

    import nac_test.robot_writer

    with patch(
        "nac_test.robot_writer._CanonicalRobotWriter.__init__"
    ) as mock_canonical_init:
        mock_canonical_init.return_value = None

        # Test str inputs → coerced to Path, empty str → None
        nac_test.robot_writer.RobotWriter(["data/path1", "data/path2"], "filters/", "")

        mock_canonical_init.assert_called_once()
        call_args = mock_canonical_init.call_args
        # When patching __init__, self is not included in call_args
        assert call_args[0][0] == [Path("data/path1"), Path("data/path2")]
        assert call_args[0][1] == Path("filters/")
        assert call_args[0][2] is None
