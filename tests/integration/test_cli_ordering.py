# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Robot test ordering tests for nac-test CLI.

This module contains integration tests that verify the ordering.txt file
generation for Robot Framework test execution, including concurrent test
handling and test-level splitting behavior.
"""

import os
import re
import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from typer.testing import CliRunner

import nac_test.cli.main

pytestmark = pytest.mark.integration


@pytest.fixture
def temp_cwd_dir() -> Generator[str, None, None]:
    """Create a unique temporary directory in the current working directory.

    The directory is automatically cleaned up after the test completes.

    Yields:
        Path to the temporary directory.
    """
    temp_dir = tempfile.mkdtemp(dir=os.getcwd(), prefix="output_")
    yield temp_dir
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


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


@pytest.mark.parametrize("fixture_name", ["tmp_path", "temp_cwd_dir"])
def test_ordering_file_contains_concurrent_tests_and_non_concurrent_suites(
    request: pytest.FixtureRequest, fixture_name: str
) -> None:
    """Test that ordering.txt contains correct entries for concurrent and non-concurrent tests.

    Verifies that:
    - Test cases with Test Concurrency metadata are listed with --test flag
    - Suites without Test Concurrency are listed with --suite flag
    - All expected robot files are rendered correctly
    - Supports both tmp_path (system temp) and temp_cwd_dir (cwd) locations

    Args:
        request: Pytest fixture request for dynamic fixture access.
        fixture_name: Name of the output directory fixture to use.
    """
    # Get the fixture value dynamically based on the parameter
    output_dir = request.getfixturevalue(fixture_name)

    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_list/"
    templates_path = "tests/integration/fixtures/templates_ordering_1/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            output_dir,
        ],
    )
    assert result.exit_code == 0, (
        f"Ordering test execution should succeed, got exit code {result.exit_code}: "
        f"{result.output}"
    )

    # Verify expected robot files were rendered
    expected_files = [
        "suite_1/concurrent.robot",
        "suite_1/non-concurrent.robot",
        "suite_1/lowercase-concurrent.robot",
        "suite_1/mixedcase-concurrent.robot",
        "suite_1/disabled-concurrent.robot",
        "suite_1/empty_suite.robot",
        "keywords.resource",
    ]
    for file_path in expected_files:
        assert os.path.exists(os.path.join(output_dir, file_path)), (
            f"Expected rendered robot file missing: {file_path}"
        )

    with open(os.path.join(output_dir, "ordering.txt")) as fd:
        content = fd.read()

        # Test cases with Test Concurrency enabled (should use --test mode)
        concurrent_tests = [
            ("Suite 1.Concurrent.Concurrent Test 1", "Test Concurrency = True"),
            ("Suite 1.Concurrent.Concurrent Test 2", "Test Concurrency = True"),
            (
                "Suite 1.Lowercase-Concurrent.Lowercase Concurrent Test 1",
                "test concurrency = True",
            ),
            (
                "Suite 1.Lowercase-Concurrent.Lowercase Concurrent Test 2",
                "test concurrency = True",
            ),
            (
                "Suite 1.Mixedcase-Concurrent.Mixed Case Concurrent Test 1",
                "TeSt CoNcUrReNcY = True",
            ),
            (
                "Suite 1.Mixedcase-Concurrent.Mixed Case Concurrent Test 2",
                "TeSt CoNcUrReNcY = True",
            ),
        ]

        for test_path, description in concurrent_tests:
            pattern = rf"^--test.*{re.escape(test_path)}$"
            assert re.search(pattern, content, re.M), (
                f"Missing --test entry for '{test_path}' ({description}) in "
                f"ordering.txt"
            )

        # Suites without concurrency (should use --suite mode)
        non_concurrent_suites = [
            ("Suite 1.Non-Concurrent", "no Test Concurrency metadata"),
            ("Suite 1.Disabled-Concurrent", "Test Concurrency = False"),
        ]

        for suite_path, description in non_concurrent_suites:
            pattern = rf"^--suite.*{re.escape(suite_path)}$"
            assert re.search(pattern, content, re.M), (
                f"Missing --suite entry for '{suite_path}' ({description}) in "
                f"ordering.txt"
            )


def test_ordering_file_not_created_when_no_concurrent_suites_exist(
    tmp_path: Path,
) -> None:
    """Test that ordering.txt is not created when no concurrent suites exist.

    Verifies that the CLI removes any existing ordering.txt and does not
    create a new one when there are no test suites with Test Concurrency
    metadata enabled.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_ordering_2/"
    # Create a leftover ordering.txt to verify it gets removed
    (tmp_path / "ordering.txt").touch()

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
        f"Test execution should succeed without concurrent suites, got exit code "
        f"{result.exit_code}: {result.output}"
    )
    assert not (tmp_path / "ordering.txt").exists(), (
        "ordering.txt file should not exist when no concurrent test suites are present"
    )


def test_ordering_file_not_created_when_testlevelsplit_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that ordering.txt is not created when NAC_TEST_NO_TESTLEVELSPLIT is set.

    Verifies that setting the NAC_TEST_NO_TESTLEVELSPLIT environment variable
    disables test-level splitting and prevents ordering.txt from being created,
    even when concurrent test suites are present.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
        monkeypatch: Pytest monkeypatch fixture for setting environment variables.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_list/"
    templates_path = "tests/integration/fixtures/templates_ordering_1/"
    monkeypatch.setenv("NAC_TEST_NO_TESTLEVELSPLIT", "1")

    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            str(tmp_path),
            "--render-only",  # Test execution would fail without testlevelsplit
        ],
    )
    assert result.exit_code == 0, (
        f"Render-only with NO_TESTLEVELSPLIT should succeed, got exit code "
        f"{result.exit_code}: {result.output}"
    )

    assert not (tmp_path / "ordering.txt").exists(), (
        "ordering.txt file should not exist when NAC_TEST_NO_TESTLEVELSPLIT is set"
    )
