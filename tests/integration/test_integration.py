# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import os
import re
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml  # type: ignore
from robot import run as robot_run  # type: ignore[attr-defined]
from typer.testing import CliRunner

import nac_test.cli.main

pytestmark = pytest.mark.integration


@pytest.fixture
def temp_cwd_dir() -> Iterator[str]:
    """Create a unique temporary directory in the current working directory.
    The directory is automatically cleaned up after the test completes.
    """
    temp_dir = tempfile.mkdtemp(dir=os.getcwd(), prefix="output_")
    yield temp_dir
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


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


def test_nac_test(tmpdir: str) -> None:
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
            tmpdir,
        ],
    )
    assert result.exit_code == 0


def test_nac_test_env(tmpdir: str) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_env/"
    templates_path = "tests/integration/fixtures/templates/"
    os.environ["DEF"] = "value"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            tmpdir,
        ],
    )
    assert result.exit_code == 0


def test_nac_test_filter(tmpdir: str) -> None:
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
            tmpdir,
        ],
    )
    assert result.exit_code == 0


def test_nac_test_test(tmpdir: str) -> None:
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
            tmpdir,
        ],
    )
    assert result.exit_code == 0


def test_nac_test_render(tmpdir: str) -> None:
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
            tmpdir,
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
            tmpdir,
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
            tmpdir,
            "--render-only",
        ],
    )
    assert result.exit_code == 0


def test_nac_test_list(tmpdir: str) -> None:
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
            tmpdir,
        ],
    )
    assert os.path.exists(os.path.join(tmpdir, "ABC", "test1.robot"))
    assert os.path.exists(os.path.join(tmpdir, "DEF", "test1.robot"))
    assert os.path.exists(os.path.join(tmpdir, "_abC", "test1.robot"))
    assert result.exit_code == 0


def test_nac_test_list_folder(tmpdir: str) -> None:
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
            tmpdir,
        ],
    )
    assert os.path.exists(os.path.join(tmpdir, "test1", "ABC.robot"))
    assert os.path.exists(os.path.join(tmpdir, "test1", "DEF.robot"))
    assert os.path.exists(os.path.join(tmpdir, "test1", "_abC.robot"))
    assert result.exit_code == 0


def test_nac_test_list_chunked(tmpdir: str) -> None:
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
            tmpdir,
        ],
    )
    assert result.exit_code == 0
    assert not os.path.exists(os.path.join(tmpdir, "ABC", "test1.robot"))
    assert not os.path.exists(os.path.join(tmpdir, "DEF", "test1.robot"))
    # files and their content are checked here
    verify_file_content(Path(templates_path) / "expected_content.yaml", Path(tmpdir))


def test_nac_test_verbosity_debug(tmpdir: str) -> None:
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
            tmpdir,
            "-v",
            "DEBUG",
        ],
    )

    assert result.exit_code == 0, "Robot/Pabot wasn't called with DEBUG loglevel"


def test_load_robotlibs(tmpdir: str) -> None:
    result = robot_run(
        "tests/integration/fixtures/templates_robotlibs/robotlibs.robot",
        outputdir=tmpdir,
    )
    assert result == 0


@pytest.mark.parametrize("fixture_name", ["tmpdir", "temp_cwd_dir"])
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


def test_nac_test_ordering_no_concurrent_suites(tmpdir: str) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_ordering_2/"
    # create a leftover ordering.txt to also make sure the file
    # is removed by nac-test
    with open(os.path.join(tmpdir, "ordering.txt"), "w"):
        pass

    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            tmpdir,
        ],
    )

    assert result.exit_code == 0
    assert not os.path.exists(os.path.join(tmpdir, "ordering.txt")), (
        "ordering.txt file should not exist"
    )


def test_nac_test_no_testlevelsplit(tmpdir: str) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_list/"
    templates_path = "tests/integration/fixtures/templates_ordering_1/"
    os.environ["NAC_TEST_NO_TESTLEVELSPLIT"] = "1"

    try:
        result = runner.invoke(
            nac_test.cli.main.app,
            [
                "-d",
                data_path,
                "-t",
                templates_path,
                "-o",
                tmpdir,
                "--render-only",  # test execution would fail without testlevelsplit
            ],
        )
        assert result.exit_code == 0

        assert not os.path.exists(os.path.join(tmpdir, "ordering.txt")), (
            "ordering.txt file should not exist when NAC_TEST_NO_TESTLEVELSPLIT is set"
        )
    finally:
        del os.environ["NAC_TEST_NO_TESTLEVELSPLIT"]


@pytest.mark.parametrize(
    "cli_args, expected_filename",
    [
        ([], "merged_data_model_test_variables.yaml"),
        (["--merged-data-filename", "custom.yaml"], "custom.yaml"),
    ],
)
def test_nac_test_render_output_model(
    tmpdir: str, cli_args: list[str], expected_filename: str
) -> None:
    """Tests the creation of the merged data model YAML file."""
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_merge/"
    templates_path = "tests/integration/fixtures/templates/"
    output_model_path = os.path.join(tmpdir, expected_filename)
    expected_model_path = "tests/integration/fixtures/data_merge/result.yaml"

    base_args = [
        "-d",
        os.path.join(data_path, "file1.yaml"),
        "-d",
        os.path.join(data_path, "file2.yaml"),
        "-t",
        templates_path,
        "-o",
        tmpdir,
        "--render-only",
    ]

    result = runner.invoke(nac_test.cli.main.app, base_args + cli_args)
    assert result.exit_code == 0
    assert os.path.exists(output_model_path)
    assert filecmp.cmp(output_model_path, expected_model_path, shallow=False)
