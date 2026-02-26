# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for PyATSOrchestrator controller_type parameter."""

import os
from pathlib import Path
from unittest.mock import patch

from _pytest.monkeypatch import MonkeyPatch

from nac_test.pyats_core.orchestrator import PyATSOrchestrator


class TestOrchestratorControllerParam:
    """Tests for PyATSOrchestrator controller_type parameter."""

    def test_orchestrator_uses_provided_controller_type(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that PyATSOrchestrator uses provided controller_type instead of detecting."""
        # Clear all controller environment variables
        for key in list(os.environ.keys()):
            if any(
                prefix in key
                for prefix in ["ACI_", "SDWAN_", "CC_", "MERAKI_", "FMC_", "ISE_"]
            ):
                monkeypatch.delenv(key, raising=False)

        # Create test directories
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        merged_file = output_dir / "merged.yaml"
        merged_file.write_text("test: data")

        # Mock detect_controller_type to verify it's NOT called
        with patch(
            "nac_test.pyats_core.orchestrator.detect_controller_type"
        ) as mock_detect:
            # Initialize with explicit controller_type
            orchestrator = PyATSOrchestrator(
                data_paths=[tmp_path / "data"],
                test_dir=test_dir,
                output_dir=output_dir,
                merged_data_filename="merged.yaml",
                controller_type="SDWAN",  # Explicitly provide controller type
            )

            # Verify controller type was set correctly
            assert orchestrator.controller_type == "SDWAN"

            # Verify detect_controller_type was NOT called
            mock_detect.assert_not_called()

    def test_orchestrator_falls_back_to_detection_when_none(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that PyATSOrchestrator detects controller when controller_type is None."""
        # Set up ACI credentials
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        # Create test directories
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        merged_file = output_dir / "merged.yaml"
        merged_file.write_text("test: data")

        # Initialize without controller_type (should detect)
        orchestrator = PyATSOrchestrator(
            data_paths=[tmp_path / "data"],
            test_dir=test_dir,
            output_dir=output_dir,
            merged_data_filename="merged.yaml",
            controller_type=None,  # Don't provide controller type
        )

        # Verify controller type was detected
        assert orchestrator.controller_type == "ACI"

    def test_orchestrator_defaults_to_detection(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that PyATSOrchestrator detects controller when parameter not provided."""
        # Set up CC credentials
        monkeypatch.setenv("CC_URL", "https://cc.test.com")
        monkeypatch.setenv("CC_USERNAME", "admin")
        monkeypatch.setenv("CC_PASSWORD", "password")

        # Create test directories
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        merged_file = output_dir / "merged.yaml"
        merged_file.write_text("test: data")

        # Initialize without controller_type parameter at all
        orchestrator = PyATSOrchestrator(
            data_paths=[tmp_path / "data"],
            test_dir=test_dir,
            output_dir=output_dir,
            merged_data_filename="merged.yaml",
            # No controller_type parameter
        )

        # Verify controller type was detected
        assert orchestrator.controller_type == "CC"

    def test_validate_environment_uses_provided_controller(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that validate_environment uses the provided controller type."""
        # Clear all controller environment variables
        for key in list(os.environ.keys()):
            if any(
                prefix in key
                for prefix in ["ACI_", "SDWAN_", "CC_", "MERAKI_", "FMC_", "ISE_"]
            ):
                monkeypatch.delenv(key, raising=False)

        # Create test directories
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        merged_file = output_dir / "merged.yaml"
        merged_file.write_text("test: data")

        # Initialize with explicit controller_type
        orchestrator = PyATSOrchestrator(
            data_paths=[tmp_path / "data"],
            test_dir=test_dir,
            output_dir=output_dir,
            merged_data_filename="merged.yaml",
            controller_type="ACI",  # Explicitly provide controller type
        )

        # Mock EnvironmentValidator to verify it receives the correct controller type
        with patch(
            "nac_test.pyats_core.orchestrator.EnvironmentValidator.validate_controller_env"
        ) as mock_validate:
            orchestrator.validate_environment()

            # Verify validate was called with the provided controller type
            mock_validate.assert_called_once_with("ACI")
