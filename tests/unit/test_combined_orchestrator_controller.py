"""Unit tests for CombinedOrchestrator controller detection integration."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from _pytest.monkeypatch import MonkeyPatch

from nac_test.combined_orchestrator import CombinedOrchestrator


class TestCombinedOrchestratorController:
    """Tests for CombinedOrchestrator controller detection."""

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
        # Clear all controller environment variables
        for key in list(os.environ.keys()):
            if any(
                prefix in key
                for prefix in ["ACI_", "SDWAN_", "CC_", "MERAKI_", "FMC_", "ISE_"]
            ):
                monkeypatch.delenv(key, raising=False)

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
        test_file.write_text("# Test file")

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

        # Mock PyATSOrchestrator to verify it receives the controller type
        with patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats:
            mock_instance = MagicMock()
            mock_pyats.return_value = mock_instance

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
                controller_type="SDWAN",
            )

            # Verify run_tests was called on the instance
            mock_instance.run_tests.assert_called_once()

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
        test_file.write_text("# Test file")

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
                    controller_type="CC",
                )

                # Verify run_tests was called on the instance
                mock_instance.run_tests.assert_called_once()
