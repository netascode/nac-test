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
import re
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
    )

    # Use print instead of logger to avoid I/O errors with closed file handles
    print(
        "✓ Connection pooling validated: 0 CLI logs in device directories "
        "(broker managing connections centrally)"
    )


def _validate_broker_statistics(
    cli_output: str,
    expected_devices: int,
    expected_test_files: int,
) -> None:
    """Validate broker statistics from CLI output.

    Args:
        cli_output: Captured stdout/stderr from nac-test execution
        expected_devices: Number of unique devices
        expected_test_files: Number of test files per device

    Raises:
        AssertionError: If statistics validation fails
    """
    pattern = r"BROKER_STATISTICS: connection_hits=(\d+), connection_misses=(\d+), command_hits=(\d+), command_misses=(\d+)"
    match = re.search(pattern, cli_output)

    assert match, (
        "Broker statistics not found in output.\n"
        "Expected to find BROKER_STATISTICS log line during broker shutdown."
    )

    connection_hits = int(match.group(1))
    connection_misses = int(match.group(2))
    command_hits = int(match.group(3))
    command_misses = int(match.group(4))

    print("\nBroker Statistics:")
    print(f"  Connection cache hits: {connection_hits}")
    print(f"  Connection cache misses: {connection_misses}")
    print(f"  Command cache hits: {command_hits}")
    print(f"  Command cache misses: {command_misses}")

    # Validate connection cache
    # Expected: one miss per device (first connection), remaining are hits
    expected_connection_misses = expected_devices
    expected_connection_hits = expected_devices * (expected_test_files - 1)

    assert connection_misses == expected_connection_misses, (
        f"Expected {expected_connection_misses} connection cache misses, "
        f"got {connection_misses}"
    )

    assert connection_hits >= expected_connection_hits, (
        f"Expected at least {expected_connection_hits} connection cache hits, "
        f"got {connection_hits}"
    )

    # Validate command cache
    # Expected: one miss per device (first command execution), remaining are hits
    expected_command_misses = expected_devices
    expected_command_hits = expected_devices * (expected_test_files - 1)

    assert command_misses == expected_command_misses, (
        f"Expected {expected_command_misses} command cache misses, got {command_misses}"
    )

    assert command_hits >= expected_command_hits, (
        f"Expected at least {expected_command_hits} command cache hits, "
        f"got {command_hits}"
    )

    print("✓ Broker statistics validated successfully")


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

        # Use workspace directory for easier debugging
        # outputdir_path = Path("workspace") / "integration_test_output"
        # outputdir_path.mkdir(parents=True, exist_ok=True)
        # output_dir = str(outputdir_path)

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

        # First check if tests passed - if they failed, show output for debugging
        assert result.exit_code == 0, (
            f"nac-test failed with exit code {result.exit_code}. "
            f"Cannot validate broker functionality until tests pass.\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr or '(empty)'}"
        )

        # Validate connection pooling
        # Expected: 2 devices, 3 test files
        _validate_broker_connection_pooling(
            output_dir=output_dir,
            expected_devices=2,
            expected_test_files=3,
        )

        # Validate broker statistics from CLI output
        # All 3 test files execute: 'show sdwan control connections'
        # Combine stdout and stderr since logs might be in either
        cli_output = result.stdout + (result.stderr or "")
        _validate_broker_statistics(
            cli_output=cli_output,
            expected_devices=2,
            expected_test_files=3,
        )

        print("\n✓ All broker validations passed!")


def test_broker_validation_detects_non_broker_connections(tmpdir: str) -> None:
    """Test that validation correctly detects when broker is NOT being used.

    This verifies that _validate_broker_connection_pooling properly fails
    when CLI logs appear in device directories (indicating direct connections
    instead of broker-managed connections).
    """
    from pathlib import Path

    # Create fake directory structure with CLI logs (as if broker wasn't used)
    output_dir = Path(tmpdir)
    d2d_results = output_dir / "pyats_results" / "d2d"
    device_dir = d2d_results / "device-01"
    device_dir.mkdir(parents=True, exist_ok=True)

    # Create a fake CLI log file (this should NOT exist when broker is active)
    cli_log = device_dir / "device-01-cli-12345.log"
    cli_log.write_text("Fake CLI log content")

    # Validation should FAIL because CLI logs exist in device directories
    with pytest.raises(AssertionError, match="CLI log files in device directories"):
        _validate_broker_connection_pooling(
            output_dir=output_dir,
            expected_devices=1,
            expected_test_files=1,
        )

    print("✓ Validation correctly detected non-broker connections")
