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


def _validate_pyats_results(output_dir: str | Path, passed: int, failed: int) -> None:
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

        # Verify passed and failed counts
        assert summary["passed"] == passed, (
            f"Unexpected passed count in {results_file.parent.name}: "
            f"expected={passed}, actual={summary['passed']}"
        )
        assert summary["failed"] == failed, (
            f"Unexpected failed count in {results_file.parent.name}: "
            f"expected={failed}, actual={summary['failed']}"
        )


@pytest.mark.parametrize(
    "arch,passed,failed,expected_rc",
    [
        ("aci", 1, 0, 0),
    ],
)
def test_nac_test_quicksilver_aci(
    mock_api_server: MockAPIServer,
    tmpdir: str,
    arch: str,
    passed: int,
    failed: int,
    expected_rc: int,
) -> None:
    """
    Verify nac-test with quicksilver-generated tests against mock server
    """
    runner = CliRunner()
    os.environ[f"{arch.upper()}_URL"] = mock_api_server.url
    os.environ[f"{arch.upper()}_USERNAME"] = "does not matter"
    os.environ[f"{arch.upper()}_PASSWORD"] = "does not matter"

    data_path = "tests/integration/fixtures/data/"
    templates_path = f"tests/integration/fixtures/templates_qs_{arch}/"

    output_dir = tmpdir
    # output_dir = (
    #     f"/tmp/nac-test-qs_{arch}"  # use static output dir for easier debugging
    # )

    try:
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

        assert result.exit_code == expected_rc

        _validate_pyats_results(output_dir, passed, failed)
    finally:
        # Clean up environment variables
        del os.environ[f"{arch.upper()}_URL"]
        del os.environ[f"{arch.upper()}_USERNAME"]
        del os.environ[f"{arch.upper()}_PASSWORD"]
