# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

import os
import re
import shutil
import tempfile
from collections.abc import Iterator

import pytest
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


@pytest.mark.parametrize("fixture_name", ["tmpdir", "temp_cwd_dir"])
def test_nac_test_ordering(request: pytest.FixtureRequest, fixture_name: str) -> None:
    # Get the fixture value dynamically based on the parameter
    output_dir = request.getfixturevalue(fixture_name)

    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_list/"
    templates_path = "tests/integration/fixtures/templates_ordering/"
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
    assert os.path.exists(os.path.join(output_dir, "suite_1", "concurrent.robot"))
    assert os.path.exists(os.path.join(output_dir, "suite_1", "non-concurrent.robot"))
    assert not os.path.exists(os.path.join(output_dir, "suite_1", "empty_suite.robot"))
    assert os.path.exists(os.path.join(output_dir, "keywords.resource"))

    with open(os.path.join(output_dir, "ordering.txt")) as fd:
        content = fd.read()
        print(content)
        assert re.search(
            r"^--test.*Suite 1\.Concurrent\.Concurrent Test 1$", content, re.M
        ), "First --test entry missing"
        assert re.search(
            r"^--test.*Suite 1.Concurrent.Concurrent Test 2$", content, re.M
        ), "Second --test entry missing"
        assert re.search(r"^--suite.*Suite 1.Non-Concurrent$", content, re.M), (
            "Non-Concurrent suite entry missing"
        )
