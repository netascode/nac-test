# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for PyATSOrchestrator controller_type parameter."""

from unittest.mock import patch

from nac_test.pyats_core.orchestrator import PyATSOrchestrator

from .conftest import PyATSTestDirs


class TestOrchestratorControllerParam:
    """Tests for PyATSOrchestrator controller_type parameter."""

    def test_orchestrator_uses_provided_controller_type(
        self, clean_controller_env: None, pyats_test_dirs: PyATSTestDirs
    ) -> None:
        """Test that PyATSOrchestrator uses provided controller_type instead of detecting."""
        with patch(
            "nac_test.pyats_core.orchestrator.detect_controller_type"
        ) as mock_detect:
            orchestrator = PyATSOrchestrator(
                data_paths=[pyats_test_dirs.output_dir.parent / "data"],
                test_dir=pyats_test_dirs.test_dir,
                output_dir=pyats_test_dirs.output_dir,
                merged_data_filename="merged.yaml",
                controller_type="SDWAN",
            )

            assert orchestrator.controller_type == "SDWAN"
            mock_detect.assert_not_called()

    def test_orchestrator_falls_back_to_detection_when_none(
        self, aci_controller_env: None, pyats_test_dirs: PyATSTestDirs
    ) -> None:
        """Test that PyATSOrchestrator detects controller when controller_type is None."""
        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_dirs.output_dir.parent / "data"],
            test_dir=pyats_test_dirs.test_dir,
            output_dir=pyats_test_dirs.output_dir,
            merged_data_filename="merged.yaml",
            controller_type=None,
        )

        assert orchestrator.controller_type == "ACI"

    def test_orchestrator_defaults_to_detection(
        self, cc_controller_env: None, pyats_test_dirs: PyATSTestDirs
    ) -> None:
        """Test that PyATSOrchestrator detects controller when parameter not provided."""
        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_dirs.output_dir.parent / "data"],
            test_dir=pyats_test_dirs.test_dir,
            output_dir=pyats_test_dirs.output_dir,
            merged_data_filename="merged.yaml",
        )

        assert orchestrator.controller_type == "CC"

    def test_validate_environment_uses_provided_controller(
        self, clean_controller_env: None, pyats_test_dirs: PyATSTestDirs
    ) -> None:
        """Test that validate_environment uses the provided controller type."""
        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_dirs.output_dir.parent / "data"],
            test_dir=pyats_test_dirs.test_dir,
            output_dir=pyats_test_dirs.output_dir,
            merged_data_filename="merged.yaml",
            controller_type="ACI",
        )

        with patch(
            "nac_test.pyats_core.orchestrator.EnvironmentValidator.validate_controller_env"
        ) as mock_validate:
            orchestrator.validate_environment()
            mock_validate.assert_called_once_with("ACI")
