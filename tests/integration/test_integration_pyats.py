# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

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
    results_files = list(pyats_results_dir.glob("**/results.json"))

    # DEBUG: If test errored, try to find and print the error log
    for results_file in results_files:
        with open(results_file) as f:
            results_data = yaml.safe_load(f)

        if results_data.get("report", {}).get("summary", {}).get("errored", 0) > 0:
            print("\n=== DEBUG: Test ERRORED, searching for error details ===")
            # Look for TaskLog.* files which contain test execution details
            log_dir = results_file.parent
            for log_file in log_dir.glob("*TaskLog*"):
                print(f"\n--- Contents of {log_file.name} ---")
                with open(log_file) as f:
                    print(f.read()[-5000:])  # Print last 5000 chars
            print("=== END ERROR DEBUG ===\n")

    assert len(results_files) > 0, f"No results.json files found in {pyats_results_dir}"

    total_passed = total_failed = 0

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

        # DEBUG: Print full summary for CI debugging
        import json

        print(f"\n=== DEBUG: Full results from {results_file.parent.name} ===")
        print(json.dumps(summary, indent=2))
        print("=== END DEBUG ===\n")

        # Verify tests were run
        assert summary["total"] > 0, (
            f"No tests were run in {results_file.parent.name}: total={summary['total']}"
        )
        total_passed += summary["passed"]
        total_failed += summary["failed"]

    # Verify passed and failed counts
    assert total_passed == passed, f"passed: expected={passed}, actual={total_passed}"
    assert total_failed == failed, f"failed: expected={failed}, actual={total_failed}"


@pytest.mark.parametrize(
    "arch,passed,failed,expected_rc",
    [
        ("aci", 1, 0, 0),
    ],
)
def test_nac_test_pyats_quicksilver_api_only(
    mock_api_server: MockAPIServer,
    tmpdir: str,
    arch: str,
    passed: int,
    failed: int,
    expected_rc: int,
) -> None:
    """
    Verify nac-test with quicksilver-generated tests against mock server
    for API-only architectures (i.e. no d2d tests)
    """
    runner = CliRunner()
    os.environ[f"{arch.upper()}_URL"] = mock_api_server.url
    os.environ[f"{arch.upper()}_USERNAME"] = "does not matter"
    os.environ[f"{arch.upper()}_PASSWORD"] = "does not matter"

    data_path = f"tests/integration/fixtures/data_pyats_qs/{arch}"
    templates_path = f"tests/integration/fixtures/templates_pyats_qs/{arch}/"

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
        for key in [
            f"{arch.upper()}_URL",
            f"{arch.upper()}_USERNAME",
            f"{arch.upper()}_PASSWORD",
        ]:
            os.environ.pop(key, None)


@pytest.mark.parametrize(
    "arch,passed,failed,expected_rc",
    [
        ("sdwan", 3, 0, 0),
    ],
)
def test_nac_test_pyats_quicksilver_api_d2d(
    mock_api_server: MockAPIServer,
    tmpdir: str,
    arch: str,
    passed: int,
    failed: int,
    expected_rc: int,
) -> None:
    """
    Verify nac-test for architectures with both API and D2D tests

    Uses Python mock to inject 'command' key into device dictionaries,
    allowing tests to use command-based mock connections instead of SSH.
    """
    from nac_test_pyats_common.common.base_device_resolver import BaseDeviceResolver

    # Get absolute path to project root to construct an absolute path to mock_unicon.py
    project_root = Path(__file__).parent.parent.parent.absolute()
    mock_script = project_root / "tests" / "integration" / "mocks" / "mock_unicon.py"

    # Save original method so we can call it from our wrapper
    original_build_device_dict = BaseDeviceResolver.build_device_dict

    def mock_build_device_dict(
        self: BaseDeviceResolver, device_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Wrapper that injects 'command' key for mock device connections"""
        device_dict: dict[str, Any] = original_build_device_dict(self, device_data)

        # Inject command key for mock connections using absolute path
        hostname = device_dict.get("hostname", "unknown")
        device_dict["command"] = f"python {mock_script} iosxe --hostname {hostname}"
        return device_dict

    # Mock the build_device_dict method to preserve command key
    with patch.object(BaseDeviceResolver, "build_device_dict", mock_build_device_dict):
        runner = CliRunner()

        # Set up environment for both API (SDWAN_*) and D2D (IOSXE_*) tests
        os.environ[f"{arch.upper()}_URL"] = mock_api_server.url
        os.environ[f"{arch.upper()}_USERNAME"] = "does not matter"
        os.environ[f"{arch.upper()}_PASSWORD"] = "does not matter"
        os.environ["IOSXE_USERNAME"] = "admin"
        os.environ["IOSXE_PASSWORD"] = "admin"

        data_path = f"tests/integration/fixtures/data_pyats_qs/{arch}"
        templates_path = f"tests/integration/fixtures/templates_pyats_qs/{arch}/"

        # outputdir = "/tmp/nac-test-pyats-sdwan-mock"  # static dir for easier debugging
        outputdir = tmpdir

        try:
            result: Result = runner.invoke(
                nac_test.cli.main.app,
                [
                    "-d",
                    data_path,
                    "-t",
                    templates_path,
                    "-o",
                    outputdir,
                    "--verbosity",
                    "DEBUG",
                ],
            )
            assert result.exit_code == expected_rc

            # we have one API test and one D2D test, but the latter with two devices. Each devices
            _validate_pyats_results(outputdir, passed=passed, failed=failed)

        finally:
            # Clean up environment
            for key in [
                f"{arch.upper()}_URL",
                f"{arch.upper()}_USERNAME",
                f"{arch.upper()}_PASSWORD",
                "IOSXE_USERNAME",
                "IOSXE_PASSWORD",
            ]:
                os.environ.pop(key, None)
