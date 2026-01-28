# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import logging

import pytest
from typer.testing import CliRunner, Result

import nac_test.cli.main
from tests.integration.mocks.mock_server import MockAPIServer

from .utils import (
    validate_pyats_results,
    validate_reporting_artifacts_pyats_html,
    validate_reporting_artifacts_pyats_robot,
    validate_robot_results,
)

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "enable_robot_html",
    [
        False,  # Default: XML only, no HTML
        True,  # With HTML generation enabled
    ],
    ids=["xml_only", "with_html"],
)
def test_nac_test_robot_pyats(
    mock_api_server: MockAPIServer,
    tmpdir: str,
    monkeypatch: pytest.MonkeyPatch,
    enable_robot_html: bool,
) -> None:
    """
    Verify nac-test with both robot and pyats tests against mock API server

    Tests both with and without Robot Framework HTML generation:
    - xml_only: Only generates output.xml (default behavior)
    - with_html: Generates output.xml, log.html, and report.html
    """
    runner = CliRunner()
    monkeypatch.setenv("SDWAN_URL", mock_api_server.url)
    monkeypatch.setenv("SDWAN_USERNAME", "does not matter")
    monkeypatch.setenv("SDWAN_PASSWORD", "does not matter")

    # Set environment variable to enable HTML generation if requested
    if enable_robot_html:
        monkeypatch.setenv("NAC_TEST_CREATE_ROBOT_HTML", "1")

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

    # Validate both PyATS and Robot Framework results
    validate_pyats_results(output_dir, 1, 0)
    validate_robot_results(output_dir, 2, 0)

    # Validate PyATS HTML reporting artifacts
    validate_reporting_artifacts_pyats_html(output_dir, ["api"])

    # Validate PyATS Robot Framework reporting artifacts
    # Pass check_html parameter based on whether HTML generation was enabled
    validate_reporting_artifacts_pyats_robot(
        output_dir, ["api"], 1, 0, check_html=enable_robot_html
    )
