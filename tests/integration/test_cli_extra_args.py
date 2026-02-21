# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Extra arguments tests for nac-test CLI.

This module contains integration tests that verify the handling of extra
arguments passed to Robot Framework, including valid variables, invalid
arguments, and the -- separator behavior.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

import nac_test.cli.main
from nac_test.core.constants import EXIT_INVALID_ROBOT_ARGS

pytestmark = pytest.mark.integration


@pytest.fixture(scope="function", autouse=True)
def setup_bogus_controller_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up environment variables for a bogus ACI controller.

    Uses monkeypatch for safe, automatic cleanup that preserves
    original environment state even if tests fail.

    Args:
        monkeypatch: Pytest monkeypatch fixture for safe environment manipulation.
    """
    monkeypatch.setenv("ACI_URL", "foo")
    monkeypatch.setenv("ACI_USERNAME", "foo")
    monkeypatch.setenv("ACI_PASSWORD", "foo")


def test_extra_args_with_valid_variable_and_separator_succeeds(tmp_path: Path) -> None:
    """Test that valid Robot Framework variables with -- separator succeed.

    Verifies that passing --variable arguments after the -- separator
    correctly passes them to Robot Framework and the test executes
    successfully.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_extra_args/"

    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            str(tmp_path),
            "--",
            "--variable",
            "MY_TEST_VAR:expected_value",
        ],
    )
    assert result.exit_code == 0, (
        f"Extra args with valid variable and -- separator should succeed, got exit "
        f"code {result.exit_code}: {result.output}"
    )


def test_extra_args_with_valid_variable_without_separator_succeeds(
    tmp_path: Path,
) -> None:
    """Test that valid Robot Framework variables without -- separator succeed.

    Verifies that passing --variable arguments directly (without the --
    separator) is also supported and the test executes successfully.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_extra_args/"

    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            str(tmp_path),
            "--variable",
            "MY_TEST_VAR:expected_value",
        ],
    )
    assert result.exit_code == 0, (
        f"Extra args with valid variable without separator should succeed, got exit "
        f"code {result.exit_code}: {result.output}"
    )


def test_extra_args_with_illegal_argument_and_separator_fails(tmp_path: Path) -> None:
    """Test that illegal Robot Framework arguments with -- separator fail.

    Verifies that passing invalid arguments (like --illegal_argument)
    after the -- separator causes Robot Framework to return an error
    exit code.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_extra_args/"

    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            str(tmp_path),
            "--",
            "--illegal_argument",
            "MY_VAR:value",
        ],
    )
    assert result.exit_code == EXIT_INVALID_ROBOT_ARGS, (
        f"Extra args with illegal argument should fail with exit code "
        f"{EXIT_INVALID_ROBOT_ARGS}, got {result.exit_code}: {result.output}"
    )


def test_extra_args_with_illegal_argument_without_separator_fails(
    tmp_path: Path,
) -> None:
    """Test that illegal Robot Framework arguments without -- separator fail.

    Verifies that passing invalid arguments directly (without the --
    separator) still causes Robot Framework to return an error exit code.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_extra_args/"

    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            str(tmp_path),
            "--illegal_argument",
            "MY_VAR:value",
        ],
    )
    assert result.exit_code == EXIT_INVALID_ROBOT_ARGS, (
        f"Extra args with illegal argument should fail with exit code "
        f"{EXIT_INVALID_ROBOT_ARGS}, got {result.exit_code}: {result.output}"
    )


def test_extra_args_with_testlevelsplit_flag_fails(tmp_path: Path) -> None:
    """Test that --testlevelsplit flag is rejected as an invalid Robot argument.

    Verifies that passing --testlevelsplit (which is a pabot argument,
    not a robot argument) causes Robot Framework to return an error
    exit code since it's not a valid robot argument.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_extra_args/"

    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            str(tmp_path),
            "--testlevelsplit",
        ],
    )
    assert result.exit_code == EXIT_INVALID_ROBOT_ARGS, (
        f"--testlevelsplit flag should fail as invalid robot arg with exit code "
        f"{EXIT_INVALID_ROBOT_ARGS}, got {result.exit_code}: {result.output}"
    )
