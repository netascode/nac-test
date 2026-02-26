# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Test PyATS orchestrator controller detection integration."""

from pathlib import Path
from unittest.mock import patch

import pytest

from nac_test.core.constants import EXIT_ERROR
from nac_test.pyats_core.orchestrator import PyATSOrchestrator


class TestOrchestratorControllerDetection:
    """Test controller detection integration in PyATSOrchestrator."""

    def test_orchestrator_detects_controller_on_init(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that PyATSOrchestrator detects controller type during initialization."""
        # Set up ACI environment variables
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        # Create required directories and files
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create a dummy merged data file
        merged_file = output_dir / "merged_data.yaml"
        merged_file.write_text("dummy: data")

        # Initialize orchestrator
        orchestrator = PyATSOrchestrator(
            data_paths=[tmp_path / "data.yaml"],
            test_dir=test_dir,
            output_dir=output_dir,
            merged_data_filename="merged_data.yaml",
        )

        # Verify controller type was detected
        assert orchestrator.controller_type == "ACI"

    def test_orchestrator_exits_on_detection_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that PyATSOrchestrator exits gracefully when controller detection fails."""
        # Clear all controller environment variables
        for env_var in [
            "ACI_URL",
            "ACI_USERNAME",
            "ACI_PASSWORD",
            "SDWAN_URL",
            "SDWAN_USERNAME",
            "SDWAN_PASSWORD",
            "CC_URL",
            "CC_USERNAME",
            "CC_PASSWORD",
        ]:
            monkeypatch.delenv(env_var, raising=False)

        # Create required directories
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create a dummy merged data file
        merged_file = output_dir / "merged_data.yaml"
        merged_file.write_text("dummy: data")

        # Attempt to initialize orchestrator should exit
        with pytest.raises(SystemExit) as exc_info:
            PyATSOrchestrator(
                data_paths=[tmp_path / "data.yaml"],
                test_dir=test_dir,
                output_dir=output_dir,
                merged_data_filename="merged_data.yaml",
            )

        # Verify it exits with EXIT_ERROR (255) for infrastructure errors
        assert exc_info.value.code == EXIT_ERROR

    def test_orchestrator_handles_multiple_controllers_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that PyATSOrchestrator handles multiple controller credentials error."""
        # Set up both ACI and SDWAN environment variables
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")
        monkeypatch.setenv("SDWAN_URL", "https://vmanage.example.com")
        monkeypatch.setenv("SDWAN_USERNAME", "admin")
        monkeypatch.setenv("SDWAN_PASSWORD", "password")

        # Create required directories
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create a dummy merged data file
        merged_file = output_dir / "merged_data.yaml"
        merged_file.write_text("dummy: data")

        # Attempt to initialize orchestrator should exit
        with pytest.raises(SystemExit) as exc_info:
            PyATSOrchestrator(
                data_paths=[tmp_path / "data.yaml"],
                test_dir=test_dir,
                output_dir=output_dir,
                merged_data_filename="merged_data.yaml",
            )

        # Verify it exits with EXIT_ERROR (255) for infrastructure errors
        assert exc_info.value.code == EXIT_ERROR

    def test_validate_environment_uses_detected_controller(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that validate_environment uses the detected controller type."""
        # Set up SDWAN environment variables
        monkeypatch.setenv("SDWAN_URL", "https://vmanage.example.com")
        monkeypatch.setenv("SDWAN_USERNAME", "admin")
        monkeypatch.setenv("SDWAN_PASSWORD", "password")

        # Create required directories and files
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create a dummy merged data file
        merged_file = output_dir / "merged_data.yaml"
        merged_file.write_text("dummy: data")

        # Initialize orchestrator
        orchestrator = PyATSOrchestrator(
            data_paths=[tmp_path / "data.yaml"],
            test_dir=test_dir,
            output_dir=output_dir,
            merged_data_filename="merged_data.yaml",
        )

        # Verify controller type was detected as SDWAN
        assert orchestrator.controller_type == "SDWAN"

        # Mock EnvironmentValidator to verify it receives correct controller type
        with patch(
            "nac_test.pyats_core.orchestrator.EnvironmentValidator"
        ) as mock_validator:
            orchestrator.validate_environment()

            # Verify validate_controller_env was called with SDWAN
            mock_validator.validate_controller_env.assert_called_once_with("SDWAN")

    def test_orchestrator_no_longer_uses_controller_type_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that PyATSOrchestrator ignores CONTROLLER_TYPE environment variable."""
        # Set up ACI credentials
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        # Also set CONTROLLER_TYPE to a different value (should be ignored)
        monkeypatch.setenv("CONTROLLER_TYPE", "SDWAN")

        # Create required directories and files
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create a dummy merged data file
        merged_file = output_dir / "merged_data.yaml"
        merged_file.write_text("dummy: data")

        # Initialize orchestrator
        orchestrator = PyATSOrchestrator(
            data_paths=[tmp_path / "data.yaml"],
            test_dir=test_dir,
            output_dir=output_dir,
            merged_data_filename="merged_data.yaml",
        )

        # Verify controller type was detected based on credentials (ACI), not CONTROLLER_TYPE env var
        assert orchestrator.controller_type == "ACI"
