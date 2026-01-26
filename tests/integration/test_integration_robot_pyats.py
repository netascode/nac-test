# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import logging

import pytest
from typer.testing import CliRunner, Result

import nac_test.cli.main
from tests.integration.mocks.mock_server import MockAPIServer

from .utils import _validate_pyats_results

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.integration


def test_nac_test_robot_pyats(
    mock_api_server: MockAPIServer,
    tmpdir: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verify nac-test with both robot and pyats tests against mock API server
    """
    runner = CliRunner()
    monkeypatch.setenv("SDWAN_URL", mock_api_server.url)
    monkeypatch.setenv("SDWAN_USERNAME", "does not matter")
    monkeypatch.setenv("SDWAN_PASSWORD", "does not matter")

    data_path = "tests/integration/fixtures/data_robot_pyats/data.yaml"
    templates_path = "tests/integration/fixtures/templates_robot_pyats"

    output_dir = tmpdir
    output_dir = "/tmp/nac_test_robot_pyats_output"

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

    _validate_pyats_results(output_dir, 1, 0)
