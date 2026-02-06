# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for CombinedOrchestrator controller detection integration."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from _pytest.monkeypatch import MonkeyPatch

from nac_test.combined_orchestrator import CombinedOrchestrator
from nac_test.core.types import PyATSResults

PYATS_TEST_FILE_CONTENT = """
# PyATS test file
from pyats import aetest
from nac_test_pyats_common.iosxe import IOSXETestBase
class Test(IOSXETestBase):
    @aetest.test
    def test(self):
        pass
"""


class TestCombinedOrchestratorController:
    """Tests for CombinedOrchestrator controller detection."""

    @pytest.fixture(autouse=True)
    def clean_controller_env(self, monkeypatch: MonkeyPatch) -> None:
        """Clear all controller-related environment variables before each test."""
        for key in list(os.environ.keys()):
            if any(
                prefix in key
                for prefix in ["ACI_", "SDWAN_", "CC_", "MERAKI_", "FMC_", "ISE_"]
            ):
                monkeypatch.delenv(key, raising=False)

    def test_combined_orchestrator_detects_controller_on_init(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that CombinedOrchestrator detects controller type during initialization."""
        # Set up ACI credentials
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        # Create test directories
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        output_dir = tmp_path / "output"

        # Initialize CombinedOrchestrator
        orchestrator = CombinedOrchestrator(
            data_paths=[data_dir],
            templates_dir=templates_dir,
            output_dir=output_dir,
            merged_data_filename="merged.yaml",
        )

        # Verify controller type was detected
        assert orchestrator.controller_type == "ACI"

    def test_combined_orchestrator_exits_on_detection_failure(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that CombinedOrchestrator exits gracefully when controller detection fails."""
        # No controller credentials set (already cleaned by fixture)
        # Create test directories
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        output_dir = tmp_path / "output"

        # Mock typer.secho to prevent output
        with patch("typer.secho"):
            # Initialize should raise typer.Exit
            with pytest.raises(typer.Exit) as exc_info:
                CombinedOrchestrator(
                    data_paths=[data_dir],
                    templates_dir=templates_dir,
                    output_dir=output_dir,
                    merged_data_filename="merged.yaml",
                )

            # Exit code should be 1
            assert exc_info.value.exit_code == 1

    def test_combined_orchestrator_passes_controller_to_pyats(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that CombinedOrchestrator passes controller type to PyATSOrchestrator."""
        # Set up SDWAN credentials
        monkeypatch.setenv("SDWAN_URL", "https://vmanage.test.com")
        monkeypatch.setenv("SDWAN_USERNAME", "admin")
        monkeypatch.setenv("SDWAN_PASSWORD", "password")

        # Create test directories and files
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        data_file = data_dir / "test.yaml"
        data_file.write_text("test: data")

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        test_file = templates_dir / "test_verify.py"
        test_file.write_text(PYATS_TEST_FILE_CONTENT)

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        merged_file = output_dir / "merged.yaml"
        merged_file.write_text("merged: data")

        # Initialize CombinedOrchestrator
        orchestrator = CombinedOrchestrator(
            data_paths=[data_dir],
            templates_dir=templates_dir,
            output_dir=output_dir,
            merged_data_filename="merged.yaml",
            dev_pyats_only=True,  # Run PyATS only mode
        )

        # Verify controller type was detected
        assert orchestrator.controller_type == "SDWAN"

        # Mock discovery to return PyATS tests found
        with patch.object(
            orchestrator, "_discover_test_types", return_value=(True, False)
        ):
            # Mock PyATSOrchestrator to verify it receives the controller type
            with patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator"
            ) as mock_pyats:
                mock_instance = MagicMock()
                # PyATS now returns PyATSResults
                mock_instance.run_tests.return_value = PyATSResults()
                mock_pyats.return_value = mock_instance

                # Mock CombinedReportGenerator (called in unified flow)
                with patch(
                    "nac_test.combined_orchestrator.CombinedReportGenerator"
                ) as mock_generator:
                    mock_gen_instance = MagicMock()
                    mock_gen_instance.generate_combined_summary.return_value = (
                        output_dir / "combined_summary.html"
                    )
                    mock_generator.return_value = mock_gen_instance

                    # Mock typer functions
                    with patch("typer.secho"), patch("typer.echo"):
                        # Run tests
                        orchestrator.run_tests()

                # Verify PyATSOrchestrator was called with controller_type
                mock_pyats.assert_called_once_with(
                    data_paths=[data_dir],
                    test_dir=templates_dir,
                    output_dir=output_dir,
                    merged_data_filename="merged.yaml",
                    minimal_reports=False,
                    custom_testbed_path=None,
                    controller_type="SDWAN",
                )

                # Verify run_tests was called on the instance
                mock_instance.run_tests.assert_called_once()

    def test_render_only_mode_does_not_instantiate_pyats_orchestrator(
        self, tmp_path: Path
    ) -> None:
        """Test that render-only mode NEVER instantiates PyATSOrchestrator.

        This is a critical invariant: render-only mode should only render templates
        without any test execution. PyATSOrchestrator should never be called,
        while Robot would be called to render Robot templates.

        This also verifies backward compatibility: render-only mode should work
        without any controller credentials being set, so we also test the controller
        detection logic to be skipped.
        """
        # No controller credentials set (already cleaned by fixture)
        # This also verifies the fix from PR #509: no controller check in render-only mode

        # Create test directories and files
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        data_file = data_dir / "test.yaml"
        data_file.write_text("test: data")

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Create a PyATS test file to trigger the PyATS code path
        pyats_test = templates_dir / "test_verify.py"
        pyats_test.write_text(PYATS_TEST_FILE_CONTENT)

        # Also create a Robot template to ensure Robot orchestrator runs
        robot_template = templates_dir / "test.robot"
        robot_template.write_text("*** Test Cases ***\nTest\n    Log    Hello")

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        merged_file = output_dir / "merged.yaml"
        merged_file.write_text("test: data")

        # Initialize CombinedOrchestrator with render_only=True
        # This should NOT raise typer.Exit despite missing credentials
        with patch(
            "nac_test.combined_orchestrator.detect_controller_type"
        ) as mock_detect:
            orchestrator = CombinedOrchestrator(
                data_paths=[data_dir],
                templates_dir=templates_dir,
                output_dir=output_dir,
                merged_data_filename="merged.yaml",
                render_only=True,  # Critical: render-only mode
            )
            mock_detect.assert_not_called()

        # Verify controller_type is empty (no detection occurred)
        assert orchestrator.controller_type is None

        # Mock PyATSOrchestrator to verify it's never instantiated
        with patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats:
            # Mock RobotOrchestrator to verify it is called
            with patch(
                "nac_test.combined_orchestrator.RobotOrchestrator"
            ) as mock_robot:
                mock_robot_instance = MagicMock()
                mock_robot.return_value = mock_robot_instance

                # Mock typer functions to suppress output
                with patch("typer.echo"), patch("typer.secho"):
                    # Run tests
                    orchestrator.run_tests()

            # CRITICAL ASSERTION: PyATSOrchestrator must NEVER be instantiated
            mock_pyats.assert_not_called()
            # Robot must be called
            mock_robot.assert_called_once()

    def test_combined_orchestrator_production_mode_passes_controller(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that CombinedOrchestrator passes controller type in production mode."""
        # Set up CC credentials
        monkeypatch.setenv("CC_URL", "https://cc.test.com")
        monkeypatch.setenv("CC_USERNAME", "admin")
        monkeypatch.setenv("CC_PASSWORD", "password")

        # Create test directories and files
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        data_file = data_dir / "test.yaml"
        data_file.write_text("test: data")

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        test_file = templates_dir / "test_verify.py"
        test_file.write_text(PYATS_TEST_FILE_CONTENT)

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        merged_file = output_dir / "merged.yaml"
        merged_file.write_text("merged: data")

        # Initialize CombinedOrchestrator (production mode - no dev flags)
        orchestrator = CombinedOrchestrator(
            data_paths=[data_dir],
            templates_dir=templates_dir,
            output_dir=output_dir,
            merged_data_filename="merged.yaml",
        )

        # Verify controller type was detected
        assert orchestrator.controller_type == "CC"

        # Mock PyATSOrchestrator and discovery
        with patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats:
            mock_instance = MagicMock()
            # PyATS now returns PyATSResults
            mock_instance.run_tests.return_value = PyATSResults()
            mock_pyats.return_value = mock_instance

            # Mock TestDiscovery to return PyATS files
            with patch(
                "nac_test.combined_orchestrator.TestDiscovery"
            ) as mock_discovery:
                mock_discovery_instance = MagicMock()
                mock_discovery_instance.discover_pyats_tests.return_value = (
                    [Path(test_file)],
                    [],
                )
                mock_discovery.return_value = mock_discovery_instance

                # Mock typer functions
                with patch("typer.echo"):
                    # Run tests
                    orchestrator.run_tests()

                # Verify PyATSOrchestrator was called with controller_type
                mock_pyats.assert_called_once_with(
                    data_paths=[data_dir],
                    test_dir=templates_dir,
                    output_dir=output_dir,
                    merged_data_filename="merged.yaml",
                    minimal_reports=False,
                    custom_testbed_path=None,
                    controller_type="CC",
                )

                # Verify run_tests was called on the instance
                mock_instance.run_tests.assert_called_once()
