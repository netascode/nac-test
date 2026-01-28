# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
Integration tests for Connection Broker functionality.

These tests verify that:
1. Connection pooling works - connections are reused across test files
2. Command caching works - identical commands return cached results

The tests run multiple test files that execute the same command on the same devices,
then validate connection logs to ensure pooling and caching are functioning correctly.
"""

import logging
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import nac_test.cli.main
from tests.integration.mocks.mock_server import MockAPIServer

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.integration


def _validate_broker_connection_pooling(
    output_dir: str | Path,
    expected_devices: int,
    expected_test_files: int,
) -> None:
    """Validate that connection broker properly pooled connections.

    With working broker:
    - Should create N connections (one per device)
    - Connection logs should be in broker's output location, not device dirs

    Without broker (or bypassed):
    - Would create N*M connections (one per device per test file)
    - Connection logs would be in each device directory

    Args:
        output_dir: Base output directory
        expected_devices: Number of unique devices tested
        expected_test_files: Number of test files executed

    Raises:
        AssertionError: If connection pooling validation fails
    """
    output_path = Path(output_dir)
    d2d_results = output_path / "pyats_results" / "d2d"

    assert d2d_results.exists(), f"D2D results directory not found: {d2d_results}"

    # Count CLI log files in device directories
    # With working broker, should be 0 (broker manages connections centrally)
    device_cli_logs = list(d2d_results.glob("**/*-cli-*.log"))

    assert len(device_cli_logs) == 0, (
        f"Found {len(device_cli_logs)} CLI log files in device directories:\n"
        f"{[str(log.relative_to(output_path)) for log in device_cli_logs]}\n\n"
        f"With working connection broker, device directories should NOT contain CLI logs.\n"
        f"This indicates the broker was bypassed and direct connections were made.\n\n"
        f"Expected: 0 logs (broker manages connections)\n"
        f"Actual: {len(device_cli_logs)} logs\n\n"
        f"If this test fails, check:\n"
        f"1. --testbed-file is NOT passed when broker is active\n"
        f"2. runtime.tasks.run() is used (not run(testbed=runtime.testbed))\n"
        f"3. NAC_TEST_BROKER_SOCKET environment variable is set"
    )

    # Use print instead of logger to avoid I/O errors with closed file handles
    print(
        "✓ Connection pooling validated: 0 CLI logs in device directories "
        "(broker managing connections centrally)"
    )


def _validate_command_caching_from_output(
    cli_output: str,
    expected_devices: int,
    expected_test_files: int,
) -> None:
    """Validate command caching by parsing broker debug messages from CLI output.

    Args:
        cli_output: Captured stdout/stderr from nac-test execution
        expected_devices: Number of unique devices
        expected_test_files: Number of test files (each executes same command)

    Raises:
        AssertionError: If command caching validation fails
    """
    # Count cache hits and misses from broker debug messages
    cache_hits = cli_output.count("Broker cache hit")
    cache_misses = cli_output.count("Broker cache miss")

    print("Cache statistics from broker logs:")
    print(f"  Cache hits: {cache_hits}")
    print(f"  Cache misses: {cache_misses}")

    # With working cache:
    # - Expected misses = expected_devices (one per device, first execution)
    # - Expected hits = expected_devices * (expected_test_files - 1)
    expected_cache_misses = expected_devices
    expected_cache_hits = expected_devices * (expected_test_files - 1)

    assert cache_misses == expected_cache_misses, (
        f"Unexpected cache miss count!\n"
        f"Expected: {expected_cache_misses} (one per device)\n"
        f"Actual: {cache_misses}\n\n"
        f"This may indicate tests are not executing as expected."
    )

    assert cache_hits >= expected_cache_hits, (
        f"Command caching NOT working correctly!\n\n"
        f"Expected cache hits: {expected_cache_hits} (minimum)\n"
        f"Actual cache hits: {cache_hits}\n\n"
        f"With {expected_test_files} test files on {expected_devices} devices:\n"
        f"  Total test runs: {expected_devices * expected_test_files}\n"
        f"  Expected cache misses: {expected_cache_misses} (first execution per device)\n"
        f"  Expected cache hits: {expected_cache_hits} (remaining executions)\n\n"
        f"If this fails, check:\n"
        f"1. Broker command cache is initialized\n"
        f"2. Cache lookups happen before command execution\n"
        f"3. Cache is shared across all broker clients"
    )

    cache_hit_rate = (
        cache_hits / (cache_hits + cache_misses)
        if (cache_hits + cache_misses) > 0
        else 0
    )
    print(
        f"✓ Command caching validated:\n"
        f"  Total requests: {cache_hits + cache_misses}\n"
        f"  Cache misses: {cache_misses} (initial executions)\n"
        f"  Cache hits: {cache_hits}\n"
        f"  Cache hit rate: {cache_hit_rate:.1%}"
    )


def test_connection_broker_pooling_and_caching(
    mock_api_server: MockAPIServer,
    tmpdir: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that connection broker properly pools connections and caches commands.

    This test:
    1. Runs 3 test files on 2 devices (6 total test executions)
    2. All test files execute the same command: 'show sdwan control connections'
    3. Validates that only 2 connections were created (not 6)
    4. Validates that the command was executed only 2 times (not 6)
    5. Verifies cache hit rate is 66.7% (4 cache hits out of 6 runs)

    Expected behavior with working broker:
    - Connection pooling: 2 connections (one per device)
    - Command caching: 2 executions + 4 cache hits
    - Cache hit rate: 66.7%

    Without broker or with broken broker:
    - Would create 6 connections (one per test per device)
    - Would execute command 6 times (no caching)
    - Cache hit rate: 0%
    """
    from nac_test_pyats_common.common.base_device_resolver import BaseDeviceResolver

    # Get absolute path to mock_unicon.py
    project_root = Path(__file__).parent.parent.parent.absolute()
    mock_script = project_root / "tests" / "integration" / "mocks" / "mock_unicon.py"

    # Save original method
    original_build_device_dict = BaseDeviceResolver.build_device_dict

    def mock_build_device_dict(
        self: BaseDeviceResolver, device_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Wrapper that injects 'command' key for mock device connections."""
        device_dict: dict[str, Any] = original_build_device_dict(self, device_data)
        hostname = device_dict.get("hostname", "unknown")
        device_dict["command"] = f"python {mock_script} iosxe --hostname {hostname}"
        return device_dict

    # Mock the build_device_dict method
    with patch.object(BaseDeviceResolver, "build_device_dict", mock_build_device_dict):
        runner = CliRunner()

        # Set up environment for SDWAN tests
        monkeypatch.setenv("SDWAN_URL", mock_api_server.url)
        monkeypatch.setenv("SDWAN_USERNAME", "admin")
        monkeypatch.setenv("SDWAN_PASSWORD", "admin")
        monkeypatch.setenv("IOSXE_USERNAME", "admin")
        monkeypatch.setenv("IOSXE_PASSWORD", "admin")

        # Use broker test fixtures
        data_path = "tests/integration/fixtures/data_broker/"
        templates_path = "tests/integration/fixtures/templates_broker/"
        output_dir = tmpdir

        result = runner.invoke(
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

        # Note: We're validating broker functionality, not test results
        # Tests may pass or fail depending on mock data, but we can still validate
        # that connection pooling and command caching worked correctly
        print(f"\nnac-test completed with exit code: {result.exit_code}")

        # First check if tests passed - if they failed due to event loop issues,
        # we need to fix that before validating broker functionality
        if result.exit_code != 0:
            print("\n❌ Tests failed with non-zero exit code")
            print("=" * 80)
            print("STDOUT:")
            print(result.stdout)
            print("=" * 80)
            if result.stderr:
                print("STDERR:")
                print(result.stderr)
                print("=" * 80)

        assert result.exit_code == 0, (
            f"nac-test failed with exit code {result.exit_code}. "
            f"Cannot validate broker functionality until tests pass."
        )

        # Validate connection pooling
        # Expected: 2 devices, 3 test files
        print("\nValidating connection pooling...")
        _validate_broker_connection_pooling(
            output_dir=output_dir,
            expected_devices=2,
            expected_test_files=3,
        )

        # Validate command caching from captured output
        # All 3 test files execute: 'show sdwan control connections'
        print("\nValidating command caching...")
        _validate_command_caching_from_output(
            cli_output=result.stdout,
            expected_devices=2,
            expected_test_files=3,
        )

        print("\n✓ All broker validations passed!")
