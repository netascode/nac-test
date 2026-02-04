# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Pytest fixtures for E2E tests.

This module provides E2E-specific fixtures:
- E2EResults dataclass for capturing test run results
- Scenario execution helper and individual scenario fixtures
- SDWAN user testbed for D2D tests

Common fixtures (mock_api_server, class_mocker, etc.) are inherited
from the global tests/conftest.py.
"""

import tempfile
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

import nac_test.cli.main
from tests.e2e.config import E2EScenario
from tests.e2e.mocks.mock_server import MockAPIServer


@dataclass
class E2EResults:
    """Results from an E2E test run.

    Attributes:
        scenario: The E2E scenario that was executed.
        output_dir: Path to the output directory containing all reports.
        exit_code: CLI exit code.
        stdout: CLI standard output.
        stderr: CLI standard error.
        cli_result: The full CliRunner result object.
    """

    scenario: E2EScenario
    output_dir: Path
    exit_code: int
    stdout: str
    stderr: str
    cli_result: Any  # typer.testing.Result


# =============================================================================
# Session-scoped fixtures
# =============================================================================


@pytest.fixture(scope="session")
def sdwan_user_testbed() -> Generator[str, None, None]:
    """Create a user testbed YAML with mock device connections for D2D tests.

    This fixture creates a temporary testbed file that configures mock device
    connections using the mock_unicon.py script. The testbed includes two
    SDWAN edge devices (sd-dc-c8kv-01 and sd-dc-c8kv-02).

    Returns:
        Path string to the testbed YAML file.
    """
    project_root = Path(__file__).parent.parent.parent.absolute()
    mock_script = project_root / "tests" / "e2e" / "mocks" / "mock_unicon.py"

    testbed_content = f"""
testbed:
  name: e2e_test_testbed
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

    with tempfile.NamedTemporaryFile(
        mode="w", suffix="_testbed.yaml", delete=False
    ) as f:
        f.write(testbed_content)
        testbed_path = Path(f.name)

    try:
        yield str(testbed_path)
    finally:
        if testbed_path.exists():
            testbed_path.unlink()


# =============================================================================
# E2E scenario execution
# =============================================================================


def _run_e2e_scenario(
    scenario: E2EScenario,
    mock_api_server: MockAPIServer,
    sdwan_user_testbed: str | None,
    tmp_path_factory: pytest.TempPathFactory,
    class_mocker: pytest.MonkeyPatch,
) -> E2EResults:
    """Execute an E2E scenario and return results.

    This is the core execution logic shared by all scenarios.

    Args:
        scenario: The scenario configuration to execute.
        mock_api_server: The mock API server instance.
        sdwan_user_testbed: Path to the testbed YAML (None if not required).
        tmp_path_factory: Pytest temp path factory.
        class_mocker: Class-scoped monkeypatch.

    Returns:
        E2EResults containing all execution results.
    """
    # Create scenario-specific temp directory
    output_dir = tmp_path_factory.mktemp(f"e2e_{scenario.name}")

    # Configure environment - use architecture as env var prefix
    arch = scenario.architecture  # e.g., "SDWAN", "ACI", "CC"
    class_mocker.setenv(f"{arch}_URL", mock_api_server.url)
    class_mocker.setenv(f"{arch}_USERNAME", "mock_user")
    class_mocker.setenv(f"{arch}_PASSWORD", "mock_pass")
    # IOSXE credentials needed for D2D tests (device access)
    class_mocker.setenv("IOSXE_USERNAME", "mock_user")
    class_mocker.setenv("IOSXE_PASSWORD", "mock_pass")

    # Build CLI arguments
    cli_args = [
        "-d",
        scenario.data_path,
        "-t",
        scenario.templates_path,
        "-o",
        str(output_dir),
        "--verbosity",
        "DEBUG",
    ]

    # Add testbed argument only if scenario requires it (D2D tests)
    if scenario.requires_testbed and sdwan_user_testbed:
        cli_args.extend(["--testbed", sdwan_user_testbed])

    # Add Robot variable if specified
    if scenario.robot_variable:
        cli_args.extend(["--variable", scenario.robot_variable])

    # Execute CLI
    runner = CliRunner()
    result = runner.invoke(nac_test.cli.main.app, cli_args)

    return E2EResults(
        scenario=scenario,
        output_dir=output_dir,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr if hasattr(result, "stderr") else "",
        cli_result=result,
    )


# =============================================================================
# Individual scenario fixtures (class-scoped for caching)
# =============================================================================


@pytest.fixture(scope="class")
def e2e_success_results(
    mock_api_server: MockAPIServer,
    sdwan_user_testbed: str,
    tmp_path_factory: pytest.TempPathFactory,
    class_mocker: pytest.MonkeyPatch,
) -> E2EResults:
    """Execute the success scenario once and cache results for the class."""
    from tests.e2e.config import SUCCESS_SCENARIO

    return _run_e2e_scenario(
        SUCCESS_SCENARIO,
        mock_api_server,
        sdwan_user_testbed,
        tmp_path_factory,
        class_mocker,
    )


@pytest.fixture(scope="class")
def e2e_failure_results(
    mock_api_server: MockAPIServer,
    sdwan_user_testbed: str,
    tmp_path_factory: pytest.TempPathFactory,
    class_mocker: pytest.MonkeyPatch,
) -> E2EResults:
    """Execute the all-fail scenario once and cache results for the class."""
    from tests.e2e.config import ALL_FAIL_SCENARIO

    return _run_e2e_scenario(
        ALL_FAIL_SCENARIO,
        mock_api_server,
        sdwan_user_testbed,
        tmp_path_factory,
        class_mocker,
    )


@pytest.fixture(scope="class")
def e2e_mixed_results(
    mock_api_server: MockAPIServer,
    sdwan_user_testbed: str,
    tmp_path_factory: pytest.TempPathFactory,
    class_mocker: pytest.MonkeyPatch,
) -> E2EResults:
    """Execute the mixed scenario once and cache results for the class."""
    from tests.e2e.config import MIXED_SCENARIO

    return _run_e2e_scenario(
        MIXED_SCENARIO,
        mock_api_server,
        sdwan_user_testbed,
        tmp_path_factory,
        class_mocker,
    )


@pytest.fixture(scope="class")
def e2e_robot_only_results(
    mock_api_server: MockAPIServer,
    tmp_path_factory: pytest.TempPathFactory,
    class_mocker: pytest.MonkeyPatch,
) -> E2EResults:
    """Execute the robot-only scenario once and cache results for the class.

    Note: This scenario does not require a testbed (no D2D tests).
    """
    from tests.e2e.config import ROBOT_ONLY_SCENARIO

    return _run_e2e_scenario(
        ROBOT_ONLY_SCENARIO,
        mock_api_server,
        None,  # No testbed needed
        tmp_path_factory,
        class_mocker,
    )


@pytest.fixture(scope="class")
def e2e_pyats_api_only_results(
    mock_api_server: MockAPIServer,
    tmp_path_factory: pytest.TempPathFactory,
    class_mocker: pytest.MonkeyPatch,
) -> E2EResults:
    """Execute the PyATS API-only scenario once and cache results for the class.

    Note: This scenario does not require a testbed (no D2D tests).
    """
    from tests.e2e.config import PYATS_API_ONLY_SCENARIO

    return _run_e2e_scenario(
        PYATS_API_ONLY_SCENARIO,
        mock_api_server,
        None,  # No testbed needed
        tmp_path_factory,
        class_mocker,
    )


@pytest.fixture(scope="class")
def e2e_pyats_d2d_only_results(
    mock_api_server: MockAPIServer,
    sdwan_user_testbed: str,
    tmp_path_factory: pytest.TempPathFactory,
    class_mocker: pytest.MonkeyPatch,
) -> E2EResults:
    """Execute the PyATS D2D-only scenario once and cache results for the class."""
    from tests.e2e.config import PYATS_D2D_ONLY_SCENARIO

    return _run_e2e_scenario(
        PYATS_D2D_ONLY_SCENARIO,
        mock_api_server,
        sdwan_user_testbed,
        tmp_path_factory,
        class_mocker,
    )


@pytest.fixture(scope="class")
def e2e_pyats_cc_results(
    mock_api_server: MockAPIServer,
    sdwan_user_testbed: str,
    tmp_path_factory: pytest.TempPathFactory,
    class_mocker: pytest.MonkeyPatch,
) -> E2EResults:
    """Execute the PyATS Catalyst Center (API + D2D) scenario once and cache results."""
    from tests.e2e.config import PYATS_CC_SCENARIO

    return _run_e2e_scenario(
        PYATS_CC_SCENARIO,
        mock_api_server,
        sdwan_user_testbed,  # D2D tests need testbed
        tmp_path_factory,
        class_mocker,
    )
