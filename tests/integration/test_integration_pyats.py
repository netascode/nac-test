# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import os
from pathlib import Path

import pytest
import yaml  # type: ignore
from typer.testing import CliRunner, Result

import nac_test.cli.main
from tests.integration.mocks.mock_server import MockAPIServer

pytestmark = pytest.mark.integration


def validate_pyats_results(output_dir: str | Path) -> None:
    """Validate PyATS test results from results.json files.

    Args:
        output_dir: Base output directory containing pyats_results/

    Raises:
        AssertionError: If validation fails (no tests run, tests failed, etc.)
    """
    output_path = Path(output_dir)
    pyats_results_dir = output_path / "pyats_results"
    assert pyats_results_dir.exists(), (
        f"PyATS results directory not found: {pyats_results_dir}"
    )

    # Find all results.json files (can be in api/ or d2d/ subdirs)
    results_files = list(pyats_results_dir.glob("*/results.json"))
    assert len(results_files) > 0, f"No results.json files found in {pyats_results_dir}"

    # Validate each results.json file
    for results_file in results_files:
        with open(results_file) as f:
            results_data = yaml.safe_load(f)

        # Check that results were generated
        assert "report" in results_data, f"No 'report' key in {results_file}"
        assert "summary" in results_data["report"], (
            f"No 'summary' in report for {results_file}"
        )

        summary = results_data["report"]["summary"]

        # Verify tests were run
        assert summary["total"] > 0, (
            f"No tests were run in {results_file.parent.name}: total={summary['total']}"
        )

        # Verify 100% success rate
        assert summary["success_rate"] == 100.0, (
            f"Tests failed in {results_file.parent.name}: "
            f"success_rate={summary['success_rate']}%, "
            f"passed={summary['passed']}, failed={summary['failed']}, "
            f"errored={summary['errored']}"
        )


@pytest.mark.skip("not yet finished")
def test_nac_test_pyats(tmpdir: str) -> None:
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_pyats/"
    result = runner.invoke(
        nac_test.cli.main.app,
        ["-d", data_path, "-t", templates_path, "-o", tmpdir, "--verbosity", "DEBUG"],
    )
    assert result.exit_code == 0
    pytest.fail("not yet finished")


def test_nac_test_qs(mock_api_server: MockAPIServer) -> None:
    runner = CliRunner()
    os.environ["ACI_URL"] = mock_api_server.url
    os.environ["ACI_USERNAME"] = "does not matter"
    os.environ["ACI_PASSWORD"] = "does not matter"
    os.environ["CONTROLLER_TYPE"] = "ACI"

    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_quicksilver/"

    output_dir = "/tmp/nac-test-qs"  # use static output dir for easier debugging
    result: Result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            output_dir,
            "--verbosity",
            "DEBUG",
        ],
    )

    assert result.exit_code == 0

    # Verify PyATS test results using helper function
    validate_pyats_results(output_dir)
