# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import os
import re
import shutil
import tempfile
from collections.abc import Iterator

import pytest
from robot import run as robot_run
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
            "--no-testlevelsplit",
        ],
    )
    assert result.exit_code == 0

    assert not os.path.exists(os.path.join(tmpdir, "ordering.txt")), (
        "ordering.txt file should not exist when --no-testlevelsplit is used"
    )
