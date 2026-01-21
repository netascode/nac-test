# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import filecmp
import os
import re
import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
import yaml  # type: ignore
from robot import run as robot_run  # type: ignore[attr-defined]
from typer.testing import CliRunner

import nac_test.cli.main

pytestmark = pytest.mark.integration


@pytest.fixture
def temp_cwd_dir() -> Generator[str, None, None]:
    """Create a unique temporary directory in the current working directory.
    The directory is automatically cleaned up after the test completes.
    """
    temp_dir = tempfile.mkdtemp(dir=os.getcwd(), prefix="output_")
    yield temp_dir
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture(scope="function", autouse=True)
def setup_bogus_controller_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up environment variables for a bogus ACI controller
    to prevent nac-test from exiting early.

    Uses monkeypatch for safe, automatic cleanup that preserves
    original environment state even if tests fail.
    """
    monkeypatch.setenv("ACI_URL", "foo")
    monkeypatch.setenv("ACI_USERNAME", "foo")
    monkeypatch.setenv("ACI_PASSWORD", "foo")


def verify_file_content(expected_yaml_path: Path, output_dir: Path) -> None:
    """Verify that files in output_dir match the expected content from YAML.

    Args:
        expected_yaml_path: Path to YAML file with structure {filename: content}
        output_dir: Base directory where the files should exist

    Raises:
        AssertionError: If any file content doesn't match expected content
    """
    with open(expected_yaml_path) as f:
        expected_files = yaml.safe_load(f)

    for filename, expected_content in expected_files.items():
        file_path = output_dir / filename
        assert file_path.exists(), f"Expected file does not exist: {file_path}"

        actual_content = file_path.read_text()
        assert actual_content.strip() == expected_content.strip(), (
            f"Content mismatch in {filename}:\n"
            f"Expected:\n{expected_content}\n"
            f"Actual:\n{actual_content}"
        )


def test_nac_test(tmp_path: Path) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates/"
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
    assert result.exit_code == 0


def test_nac_test_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    assert result.exit_code == 0


def test_nac_test_filter(tmp_path: Path) -> None:
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
    assert result.exit_code == 0


def test_nac_test_test(tmp_path: Path) -> None:
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
    assert result.exit_code == 0


def test_nac_test_render(tmp_path: Path) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_fail/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            str(tmp_path),
            "--render-only",
        ],
    )
    assert result.exit_code == 0
    templates_path = "tests/integration/fixtures/templates_missing/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            str(tmp_path),
            "--render-only",
        ],
    )
    assert result.exit_code == 1
    templates_path = "tests/integration/fixtures/templates_missing_default/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            str(tmp_path),
            "--render-only",
        ],
    )
    assert result.exit_code == 0


def test_nac_test_list(tmp_path: Path) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_list/"
    templates_path = "tests/integration/fixtures/templates_list/"
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
    assert (tmp_path / "ABC" / "test1.robot").exists()
    assert (tmp_path / "DEF" / "test1.robot").exists()
    assert (tmp_path / "_abC" / "test1.robot").exists()
    assert result.exit_code == 0


def test_nac_test_list_folder(tmp_path: Path) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_list/"
    templates_path = "tests/integration/fixtures/templates_list_folder/"
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
    assert (tmp_path / "test1" / "ABC.robot").exists()
    assert (tmp_path / "test1" / "DEF.robot").exists()
    assert (tmp_path / "test1" / "_abC.robot").exists()
    assert result.exit_code == 0


def test_nac_test_list_chunked(tmp_path: Path) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_list_chunked/"
    templates_path = "tests/integration/fixtures/templates_list_chunked/"
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
    assert result.exit_code == 0
    assert not (tmp_path / "ABC" / "test1.robot").exists()
    assert not (tmp_path / "DEF" / "test1.robot").exists()
    # files and their content are checked here
    verify_file_content(Path(templates_path) / "expected_content.yaml", tmp_path)


def test_nac_test_verbosity_debug(tmp_path: Path) -> None:
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
            "-v",
            "DEBUG",
        ],
    )

    assert result.exit_code == 0, "Robot/Pabot wasn't called with DEBUG loglevel"


def test_load_robotlibs(tmp_path: Path) -> None:
    result = robot_run(
        "tests/integration/fixtures/templates_robotlibs/robotlibs.robot",
        outputdir=str(tmp_path),
    )
    assert result == 0


@pytest.mark.parametrize("fixture_name", ["tmp_path", "temp_cwd_dir"])
def test_nac_test_ordering(request: pytest.FixtureRequest, fixture_name: str) -> None:
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
    assert result.exit_code == 0

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
            f"Expected file missing: {file_path}"
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
                f"Missing --test entry for '{test_path}' ({description})"
            )

        # Suites without concurrency (should use --suite mode)
        non_concurrent_suites = [
            ("Suite 1.Non-Concurrent", "no Test Concurrency metadata"),
            ("Suite 1.Disabled-Concurrent", "Test Concurrency = False"),
        ]

        for suite_path, description in non_concurrent_suites:
            pattern = rf"^--suite.*{re.escape(suite_path)}$"
            assert re.search(pattern, content, re.M), (
                f"Missing --suite entry for '{suite_path}' ({description})"
            )


def test_nac_test_ordering_no_concurrent_suites(tmp_path: Path) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_ordering_2/"
    # create a leftover ordering.txt to also make sure the file
    # is removed by nac-test
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

    assert result.exit_code == 0
    assert not (tmp_path / "ordering.txt").exists(), (
        "ordering.txt file should not exist"
    )


def test_nac_test_no_testlevelsplit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
            "--render-only",  # test execution would fail without testlevelsplit
        ],
    )
    assert result.exit_code == 0

    assert not (tmp_path / "ordering.txt").exists(), (
        "ordering.txt file should not exist when NAC_TEST_NO_TESTLEVELSPLIT is set"
    )


@pytest.mark.parametrize(
    "extra_args,expected_exit_code",
    [
        (["--", "--variable", "MY_TEST_VAR:expected_value"], 0),
        (["--variable", "MY_TEST_VAR:expected_value"], 0),
        (["--", "--illegal_argument", "MY_VAR:value"], 252),
        (["--illegal_argument", "MY_VAR:value"], 252),
        # --testlevelsplit is not a valid robot arg
        (["--testlevelsplit"], 252),
    ],
)
def test_nac_test_extra_args(
    tmp_path: Path, extra_args: list[str], expected_exit_code: int
) -> None:
    """Test extra Robot Framework arguments with/without -- separator."""
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
        ]
        + extra_args,
    )
    assert result.exit_code == expected_exit_code


@pytest.mark.parametrize(
    "cli_args, expected_filename",
    [
        ([], "merged_data_model_test_variables.yaml"),
        (["--merged-data-filename", "custom.yaml"], "custom.yaml"),
    ],
)
def test_nac_test_render_output_model(
    tmp_path: Path, cli_args: list[str], expected_filename: str
) -> None:
    """Tests the creation of the merged data model YAML file."""
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_merge/"
    templates_path = "tests/integration/fixtures/templates/"
    output_model_path = tmp_path / expected_filename
    expected_model_path = "tests/integration/fixtures/data_merge/result.yaml"

    base_args = [
        "-d",
        os.path.join(data_path, "file1.yaml"),
        "-d",
        os.path.join(data_path, "file2.yaml"),
        "-t",
        templates_path,
        "-o",
        str(tmp_path),
        "--render-only",
    ]

    result = runner.invoke(nac_test.cli.main.app, base_args + cli_args)
    assert result.exit_code == 0
    assert output_model_path.exists()
    assert filecmp.cmp(output_model_path, expected_model_path, shallow=False)
