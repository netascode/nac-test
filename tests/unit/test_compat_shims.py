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
from unittest.mock import patch

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

    # Warning must NOT point to a specific replacement import path
    msg = str(shim_warnings[0].message)
    assert "nac_test.robot." not in msg

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


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("filters", Path("filters")),
        (Path("filters"), Path("filters")),
        ("   ", Path("   ")),
    ],
    ids=["none", "empty-string", "string", "path", "whitespace-string"],
)
def test_coerce_optional_path(value: str | Path | None, expected: Path | None) -> None:
    """Verify _coerce_optional_path handles all input variants."""
    from nac_test.robot_writer import _coerce_optional_path

    result = _coerce_optional_path(value)
    assert result == expected


@pytest.mark.parametrize(
    ("path_input", "expected_path"),
    [
        ("some/string/path", Path("some/string/path")),
        (Path("another/path"), Path("another/path")),
    ],
    ids=["str", "path"],
)
def test_run_pabot_coerces_path_arg(
    path_input: str | Path, expected_path: Path
) -> None:
    """Verify run_pabot shim coerces str to Path before delegating."""
    import nac_test.pabot

    with patch("nac_test.pabot._canonical_run_pabot", return_value=0) as mock:
        result = nac_test.pabot.run_pabot(path_input)

    assert result == 0
    assert mock.call_args[0][0] == expected_path


def test_run_pabot_forwards_kwargs() -> None:
    """Verify run_pabot shim forwards kwargs unchanged to canonical."""
    import nac_test.pabot

    with patch("nac_test.pabot._canonical_run_pabot", return_value=0) as mock:
        nac_test.pabot.run_pabot("path", loglevel="DEBUG", console="VERBOSE")

    assert mock.call_args[1] == {"loglevel": "DEBUG", "console": "VERBOSE"}


@pytest.mark.parametrize(
    (
        "data_paths",
        "filters_path",
        "tests_path",
        "expected_data_paths",
        "expected_filters_path",
        "expected_tests_path",
    ),
    [
        (
            ["data1.yml", "data2.yml"],
            "filters",
            "",
            [Path("data1.yml"), Path("data2.yml")],
            Path("filters"),
            None,
        ),
        (
            [Path("data1.yml"), "data2.yml"],
            None,
            Path("tests"),
            [Path("data1.yml"), Path("data2.yml")],
            None,
            Path("tests"),
        ),
        ([], "", None, [], None, None),
        (
            [Path("a.yml")],
            Path("filters"),
            Path("tests"),
            [Path("a.yml")],
            Path("filters"),
            Path("tests"),
        ),
    ],
    ids=[
        "all-strings-empty-tests",
        "mixed-data-none-filters",
        "empty-data-no-optionals",
        "all-paths-passthrough",
    ],
)
def test_robot_writer_coercion_variants(
    data_paths: list[str | Path],
    filters_path: str | Path | None,
    tests_path: str | Path | None,
    expected_data_paths: list[Path],
    expected_filters_path: Path | None,
    expected_tests_path: Path | None,
) -> None:
    """Verify RobotWriter shim coerces args for various input combinations."""
    import nac_test.robot_writer

    with patch(
        "nac_test.robot_writer._CanonicalRobotWriter.__init__", return_value=None
    ) as mock_init:
        nac_test.robot_writer.RobotWriter(data_paths, filters_path, tests_path)

    args = mock_init.call_args[0]
    assert args[0] == expected_data_paths
    assert args[1] == expected_filters_path
    assert args[2] == expected_tests_path


def test_robot_writer_forwards_kwargs() -> None:
    """Verify RobotWriter shim forwards kwargs unchanged to canonical."""
    import nac_test.robot_writer

    with patch(
        "nac_test.robot_writer._CanonicalRobotWriter.__init__", return_value=None
    ) as mock_init:
        nac_test.robot_writer.RobotWriter(
            ["data.yml"], None, None, include_tags=["tag1"], exclude_tags=["tag2"]
        )

    assert mock_init.call_args[1] == {
        "include_tags": ["tag1"],
        "exclude_tags": ["tag2"],
    }
