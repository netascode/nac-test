# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Basic CLI execution tests for nac-test.

This module contains integration tests that verify basic CLI functionality
including command execution, environment variable handling, custom filters,
test file loading, and loglevel settings.
"""

from pathlib import Path

import pytest
from robot import run as robot_run  # type: ignore[attr-defined]
from typer.testing import CliRunner

import nac_test.cli.main

pytestmark = [
    pytest.mark.integration,
    pytest.mark.windows,
    pytest.mark.usefixtures("setup_bogus_controller_env"),
]


@pytest.mark.parametrize("fixture_name", ["tmp_path", "temp_cwd_dir"])
def test_nac_test_basic_execution_succeeds(
    request: pytest.FixtureRequest, fixture_name: str
) -> None:
    """Test that basic nac-test CLI execution completes successfully.

    Verifies that the CLI can process data files and templates without
    errors when provided with valid paths and either an absolute temp output
    directory or a cwd-relative temp output directory.

    Args:
        request: Pytest fixture request for dynamic fixture access.
        fixture_name: Name of the output directory fixture to use.
    """
    runner = CliRunner()
    output_dir = request.getfixturevalue(fixture_name)
    data_path = "tests/integration/fixtures/data/data.yaml"
    templates_path = "tests/integration/fixtures/templates/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-d",
            "tests/integration/fixtures/data/defaults.yaml",
            "-t",
            templates_path,
            "-o",
            str(output_dir),
        ],
    )
    assert result.exit_code == 0, (
        f"Basic CLI execution should succeed, got exit code {result.exit_code}: "
        f"{result.output}"
    )


def test_nac_test_environment_variable_substitution_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that environment variables are substituted correctly in data files.

    Verifies that the CLI can process data files containing environment variable
    references and substitute them with actual values during rendering.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
        monkeypatch: Pytest monkeypatch fixture for setting environment variables.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_env/"
    templates_path = "tests/integration/fixtures/templates/"
    monkeypatch.setenv("DEF", "value")
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, (
        f"Environment variable substitution should succeed, got exit code "
        f"{result.exit_code}: {result.output}"
    )


def test_nac_test_custom_jinja_filter_loading_succeeds(tmp_path: Path) -> None:
    """Test that custom Jinja filters can be loaded and used.

    Verifies that the CLI properly loads custom Jinja filter files from
    the specified filters directory and makes them available during
    template rendering.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_filter/"
    filters_path = "tests/integration/fixtures/filters/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-f",
            filters_path,
            "-o",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, (
        f"Custom Jinja filter loading should succeed, got exit code "
        f"{result.exit_code}: {result.output}"
    )


def test_nac_test_external_test_file_loading_succeeds(tmp_path: Path) -> None:
    """Test that external test files can be loaded via --tests option.

    Verifies that the CLI properly loads and uses test files from a
    specified tests directory separate from the templates.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_test/"
    tests_path = "tests/integration/fixtures/tests/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "--tests",
            tests_path,
            "-o",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, (
        f"External test file loading should succeed, got exit code "
        f"{result.exit_code}: {result.output}"
    )


def test_nac_test_debug_loglevel_flag_accepted(tmp_path: Path) -> None:
    """Test that the DEBUG loglevel flag is accepted and applied.

    Verifies that the CLI accepts the -l DEBUG option and processes
    templates without errors when debug logging is enabled.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_debug/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            str(tmp_path),
            "-l",
            "DEBUG",
        ],
    )

    assert result.exit_code == 0, (
        f"DEBUG loglevel flag should be accepted, got exit code "
        f"{result.exit_code}: {result.output}"
    )


def test_robot_framework_library_loading_succeeds(tmp_path: Path) -> None:
    """Test that Robot Framework libraries can be loaded correctly.

    Verifies that Robot Framework can import and use libraries specified
    in the test file without import errors.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    result = robot_run(
        "tests/integration/fixtures/templates_robotlibs/robotlibs.robot",
        outputdir=str(tmp_path),
    )
    assert result == 0, (
        f"Robot Framework library loading should succeed, got return code {result}"
    )
