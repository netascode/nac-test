# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import logging
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner, Result

import nac_test.cli.main
from tests.integration.mocks.mock_server import MockAPIServer

from .utils import validate_pyats_results

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "arch,env_prefix,passed,failed,expected_rc",
    [
        ("aci", "ACI", 1, 0, 0),
    ],
)
def test_nac_test_pyats_quicksilver_api_only(
    mock_api_server: MockAPIServer,
    tmpdir: str,
    arch: str,
    env_prefix: str,
    passed: int,
    failed: int,
    expected_rc: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verify nac-test with quicksilver-generated tests against mock server
    for API-only architectures (i.e. no d2d tests)
    """
    runner = CliRunner()
    monkeypatch.setenv(f"{env_prefix}_URL", mock_api_server.url)
    monkeypatch.setenv(f"{env_prefix}_USERNAME", "does not matter")
    monkeypatch.setenv(f"{env_prefix}_PASSWORD", "does not matter")

    data_path = f"tests/integration/fixtures/data_pyats_qs/{arch}"
    templates_path = f"tests/integration/fixtures/templates_pyats_qs/{arch}/"

    output_dir = tmpdir

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

    validate_pyats_results(output_dir, passed, failed)


@pytest.mark.parametrize(
    "arch,env_prefix,passed,failed,expected_rc",
    [
        ("sdwan", "SDWAN", 3, 0, 0),
        ("catc", "CC", 3, 0, 0),
    ],
)
def test_nac_test_pyats_quicksilver_api_d2d(
    mock_api_server: MockAPIServer,
    tmpdir: str,
    arch: str,
    env_prefix: str,
    passed: int,
    failed: int,
    expected_rc: int,
    monkeypatch: pytest.MonkeyPatch,
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
        monkeypatch.setenv(f"{env_prefix}_URL", mock_api_server.url)
        monkeypatch.setenv(f"{env_prefix}_USERNAME", "does not matter")
        monkeypatch.setenv(f"{env_prefix}_PASSWORD", "does not matter")
        monkeypatch.setenv("IOSXE_USERNAME", "admin")
        monkeypatch.setenv("IOSXE_PASSWORD", "admin")

        data_path = f"tests/integration/fixtures/data_pyats_qs/{arch}"
        templates_path = f"tests/integration/fixtures/templates_pyats_qs/{arch}/"

        outputdir = tmpdir

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

        # we have one API test and one D2D test, but the latter with two devices
        validate_pyats_results(outputdir, passed=passed, failed=failed)


@pytest.mark.parametrize(
    "arch,passed,failed,expected_rc",
    [
        ("sdwan", 3, 0, 0),
    ],
)
def test_nac_test_pyats_quicksilver_api_d2d_with_testbed(
    mock_api_server: MockAPIServer,
    tmpdir: str,
    arch: str,
    passed: int,
    failed: int,
    expected_rc: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verify nac-test for architectures with both API and D2D tests using user testbed.

    Uses the new --testbed feature to provide custom device connection information
    via a user-provided testbed.yaml instead of patching the resolver.
    """
    # Get absolute path to project root to construct path to mock_unicon.py
    project_root = Path(__file__).parent.parent.parent.absolute()
    mock_script = project_root / "tests" / "integration" / "mocks" / "mock_unicon.py"

    # Create a user testbed YAML with mock device connections
    # Devices sd-dc-c8kv-01 and sd-dc-c8kv-02 are from the SDWAN fixture data
    user_testbed_yaml = f"""
testbed:
  name: integration_test_testbed
  credentials:
    default:
      username: admin
      password: admin

devices:
  sd-dc-c8kv-01:
    os: iosxe
    type: router
    connections:
      cli:
        command: python {mock_script} iosxe --hostname sd-dc-c8kv-01

  sd-dc-c8kv-02:
    os: iosxe
    type: router
    connections:
      cli:
        command: python {mock_script} iosxe --hostname sd-dc-c8kv-02
"""

    # Write user testbed to temp file
    testbed_path = Path(tmpdir) / "user_testbed.yaml"
    with open(testbed_path, "w") as f:
        f.write(user_testbed_yaml)

    runner = CliRunner()

    # Set up environment for both API (SDWAN_*) and D2D (IOSXE_*) tests
    monkeypatch.setenv(f"{arch.upper()}_URL", mock_api_server.url)
    monkeypatch.setenv(f"{arch.upper()}_USERNAME", "does not matter")
    monkeypatch.setenv(f"{arch.upper()}_PASSWORD", "does not matter")
    monkeypatch.setenv("IOSXE_USERNAME", "admin")
    monkeypatch.setenv("IOSXE_PASSWORD", "admin")

    data_path = f"tests/integration/fixtures/data_pyats_qs/{arch}"
    templates_path = f"tests/integration/fixtures/templates_pyats_qs/{arch}/"

    outputdir = tmpdir

    result: Result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            outputdir,
            "--testbed",
            str(testbed_path),
            "--verbosity",
            "DEBUG",
        ],
    )
    assert result.exit_code == expected_rc

    # we have one API test and one D2D test, but the latter with two devices
    validate_pyats_results(outputdir, passed=passed, failed=failed)
