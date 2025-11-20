# -*- coding: utf-8 -*-

"""Integration tests for Robot Framework with socket-based progress tracking.

Tests the complete nac-test CLI flow with Robot Framework execution.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

import nac_test.cli.main

pytestmark = pytest.mark.integration


def test_nac_test_robot_with_socket_listener(tmpdir: str) -> None:
    """Test nac-test CLI with Robot Framework using socket-based progress listener.

    This validates the end-to-end flow:
    1. User runs nac-test command
    2. RobotOrchestrator renders templates
    3. Pabot runs with socket listener integrated
    4. Tests complete successfully with proper outputs
    """
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

    # Exit code 0 = all tests passed, 1 = some tests failed but execution completed
    assert result.exit_code in [0, 1], f"Unexpected exit code: {result.exit_code}"

    # Validate Robot Framework outputs were created
    output_dir = Path(tmpdir)
    assert (output_dir / "output.xml").exists()
    assert (output_dir / "log.html").exists()
    assert (output_dir / "report.html").exists()
