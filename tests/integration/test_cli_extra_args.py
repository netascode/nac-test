# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Extra arguments tests for nac-test CLI.

This module contains integration tests that verify the handling of extra
arguments passed to Robot Framework via the -- separator.

Note: As of v2.x, Robot Framework arguments MUST be passed after the --
separator. Arguments without the separator are rejected by the CLI.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

import nac_test.cli.main
from nac_test.core.constants import EXIT_DATA_ERROR, EXIT_INVALID_ARGS

pytestmark = [
    pytest.mark.integration,
    pytest.mark.windows,
]


def test_extra_args_with_valid_variable_succeeds(tmp_path: Path) -> None:
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
        f"Extra args with valid variable should succeed, got exit "
        f"code {result.exit_code}: {result.output}"
    )


def test_extra_args_with_illegal_argument_fails(tmp_path: Path) -> None:
    """Test that illegal Robot Framework arguments fail.

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
    assert result.exit_code == EXIT_DATA_ERROR, (
        f"Extra args with illegal argument should fail with exit code "
        f"{EXIT_DATA_ERROR}, got {result.exit_code}: {result.output}"
    )


def test_extra_args_with_testlevelsplit_flag_fails(tmp_path: Path) -> None:
    """Test that --testlevelsplit flag is rejected as a pabot argument.

    Verifies that passing --testlevelsplit (which is a pabot argument,
    not a robot argument) causes an error since pabot arguments are
    not allowed in extra arguments.

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
            "--testlevelsplit",
        ],
    )
    assert result.exit_code == EXIT_INVALID_ARGS, (
        f"--testlevelsplit flag should fail as pabot arg with exit code "
        f"{EXIT_INVALID_ARGS}, got {result.exit_code}: {result.output}"
    )


def test_extra_args_with_controlled_option_fails(tmp_path: Path) -> None:
    """Test that nac-test controlled options are rejected in extra args.

    Verifies that passing options controlled by nac-test (like --include)
    via the -- separator causes an error with guidance to use the
    nac-test equivalent.

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
            "--include",
            "sometag",
        ],
    )
    assert result.exit_code == EXIT_INVALID_ARGS, (
        f"--include should fail as controlled option with exit code "
        f"{EXIT_INVALID_ARGS}, got {result.exit_code}: {result.output}"
    )
    assert "nac-test" in result.output.lower() or "controlled" in result.output.lower()
