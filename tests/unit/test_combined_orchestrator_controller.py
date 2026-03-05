# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for CombinedOrchestrator controller detection.

Tests verify that CombinedOrchestrator correctly handles controller detection
before PyATS instantiation, including detection failures, multiple controllers,
and dry-run mode bypassing detection.
"""

from unittest.mock import MagicMock, patch

import pytest

from nac_test.combined_orchestrator import CombinedOrchestrator
from nac_test.core.types import ExecutionState, PyATSResults, TestResults

from .conftest import (
    PYATS_TEST_FILE_CONTENT,
    ROBOT_TEST_FILE_CONTENT,
    PyATSTestEnv,
)


class TestCombinedOrchestratorController:
    """Tests for CombinedOrchestrator dispatch to sub-orchestrators."""

    @pytest.fixture(autouse=True)
    def _clean_env(self, clean_controller_env: None) -> None:
        """Apply shared clean_controller_env fixture to all tests in this class."""

    def test_combined_orchestrator_delegates_to_pyats_with_controller_type(
        self, pyats_test_env: PyATSTestEnv, aci_controller_env: None
    ) -> None:
        """Test that CombinedOrchestrator detects controller and passes it to PyATSOrchestrator."""
        (pyats_test_env.test_dir / "test_verify.py").write_text(PYATS_TEST_FILE_CONTENT)

        orchestrator = CombinedOrchestrator(
            data_paths=[pyats_test_env.data_dir],
            templates_dir=pyats_test_env.test_dir,
            output_dir=pyats_test_env.output_dir,
            merged_data_filename=pyats_test_env.merged_file.name,
        )

        with (
            patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats,
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator"
            ) as mock_generator,
            patch("typer.echo"),
            patch("typer.secho"),
            patch.object(CombinedOrchestrator, "_check_python_version"),
        ):
            mock_pyats.return_value.run_tests.return_value = PyATSResults()
            mock_generator.return_value.generate_combined_summary.return_value = None

            orchestrator.run_tests()

            mock_pyats.assert_called_once_with(
                data_paths=[pyats_test_env.data_dir],
                test_dir=pyats_test_env.test_dir,
                output_dir=pyats_test_env.output_dir,
                merged_data_filename=pyats_test_env.merged_file.name,
                minimal_reports=False,
                custom_testbed_path=None,
                controller_type="ACI",
                dry_run=False,
            )

    def test_robot_only_does_not_invoke_pyats(
        self, pyats_test_env: PyATSTestEnv
    ) -> None:
        """Test that --robot flag skips PyATSOrchestrator entirely."""
        (pyats_test_env.test_dir / "test.robot").write_text(ROBOT_TEST_FILE_CONTENT)

        orchestrator = CombinedOrchestrator(
            data_paths=[pyats_test_env.data_dir],
            templates_dir=pyats_test_env.test_dir,
            output_dir=pyats_test_env.output_dir,
            merged_data_filename=pyats_test_env.merged_file.name,
            dev_robot_only=True,
        )

        with (
            patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats,
            patch("nac_test.combined_orchestrator.RobotOrchestrator") as mock_robot,
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator"
            ) as mock_generator,
            patch("typer.echo"),
            patch("typer.secho"),
        ):
            mock_robot.return_value.run_tests.return_value = TestResults(passed=1)
            mock_generator.return_value.generate_combined_summary.return_value = None

            result = orchestrator.run_tests()

        mock_pyats.assert_not_called()
        mock_robot.assert_called_once()
        assert result.robot is not None
        assert result.robot.passed == 1

    def test_render_only_does_not_invoke_pyats(
        self, pyats_test_env: PyATSTestEnv
    ) -> None:
        """Test that render-only mode skips PyATSOrchestrator entirely."""
        (pyats_test_env.test_dir / "test_verify.py").write_text(PYATS_TEST_FILE_CONTENT)
        (pyats_test_env.test_dir / "test.robot").write_text(ROBOT_TEST_FILE_CONTENT)

        orchestrator = CombinedOrchestrator(
            data_paths=[pyats_test_env.data_dir],
            templates_dir=pyats_test_env.test_dir,
            output_dir=pyats_test_env.output_dir,
            merged_data_filename=pyats_test_env.merged_file.name,
            render_only=True,
        )

        with (
            patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats,
            patch("nac_test.combined_orchestrator.RobotOrchestrator") as mock_robot,
            patch("typer.echo"),
            patch("typer.secho"),
        ):
            mock_robot.return_value = MagicMock()

            orchestrator.run_tests()

        mock_pyats.assert_not_called()
        mock_robot.assert_called_once()

    def test_detection_failure_sets_error_and_allows_robot_to_run(
        self, pyats_test_env: PyATSTestEnv
    ) -> None:
        """Test that Robot tests still run when controller detection fails in CombinedOrchestrator."""
        (pyats_test_env.test_dir / "test_verify.py").write_text(PYATS_TEST_FILE_CONTENT)
        (pyats_test_env.test_dir / "test.robot").write_text(ROBOT_TEST_FILE_CONTENT)

        orchestrator = CombinedOrchestrator(
            data_paths=[pyats_test_env.data_dir],
            templates_dir=pyats_test_env.test_dir,
            output_dir=pyats_test_env.output_dir,
            merged_data_filename=pyats_test_env.merged_file.name,
        )

        with (
            patch(
                "nac_test.combined_orchestrator.detect_controller_type"
            ) as mock_detect,
            patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats,
            patch("nac_test.combined_orchestrator.RobotOrchestrator") as mock_robot,
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator"
            ) as mock_generator,
            patch("typer.echo"),
            patch("typer.secho"),
            patch.object(CombinedOrchestrator, "_check_python_version"),
        ):
            mock_detect.side_effect = ValueError("No controller credentials found")
            mock_robot.return_value.run_tests.return_value = TestResults(passed=1)
            mock_generator.return_value.generate_combined_summary.return_value = None

            result = orchestrator.run_tests()

        mock_pyats.assert_not_called()
        mock_robot.assert_called_once()
        assert result.api is not None
        assert result.api.state == ExecutionState.ERROR
        assert result.d2d is not None
        assert result.d2d.state == ExecutionState.ERROR
        assert result.robot is not None
        assert result.robot.passed == 1

    def test_dry_run_skips_controller_detection(
        self, pyats_test_env: PyATSTestEnv
    ) -> None:
        """Test that dry-run mode passes controller_type=None to PyATSOrchestrator."""
        (pyats_test_env.test_dir / "test_verify.py").write_text(PYATS_TEST_FILE_CONTENT)

        orchestrator = CombinedOrchestrator(
            data_paths=[pyats_test_env.data_dir],
            templates_dir=pyats_test_env.test_dir,
            output_dir=pyats_test_env.output_dir,
            merged_data_filename=pyats_test_env.merged_file.name,
            dry_run=True,
        )

        with (
            patch(
                "nac_test.combined_orchestrator.detect_controller_type"
            ) as mock_detect,
            patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats,
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator"
            ) as mock_generator,
            patch("typer.echo"),
            patch("typer.secho"),
            patch.object(CombinedOrchestrator, "_check_python_version"),
        ):
            mock_pyats.return_value.run_tests.return_value = PyATSResults()
            mock_generator.return_value.generate_combined_summary.return_value = None

            orchestrator.run_tests()

        mock_detect.assert_not_called()
        mock_pyats.assert_called_once()
        call_kwargs = mock_pyats.call_args.kwargs
        assert call_kwargs["controller_type"] is None
        assert call_kwargs["dry_run"] is True

    def test_multiple_controllers_sets_error_and_allows_robot_to_run(
        self, pyats_test_env: PyATSTestEnv, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that multiple controller credentials sets error and allows Robot to run."""
        # Set credentials for multiple controllers (ACI and SDWAN)
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")
        monkeypatch.setenv("SDWAN_URL", "https://vmanage.test.com")
        monkeypatch.setenv("SDWAN_USERNAME", "admin")
        monkeypatch.setenv("SDWAN_PASSWORD", "password")

        (pyats_test_env.test_dir / "test_verify.py").write_text(PYATS_TEST_FILE_CONTENT)
        (pyats_test_env.test_dir / "test.robot").write_text(ROBOT_TEST_FILE_CONTENT)

        orchestrator = CombinedOrchestrator(
            data_paths=[pyats_test_env.data_dir],
            templates_dir=pyats_test_env.test_dir,
            output_dir=pyats_test_env.output_dir,
            merged_data_filename=pyats_test_env.merged_file.name,
        )

        with (
            patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats,
            patch("nac_test.combined_orchestrator.RobotOrchestrator") as mock_robot,
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator"
            ) as mock_generator,
            patch("typer.echo"),
            patch("typer.secho"),
            patch.object(CombinedOrchestrator, "_check_python_version"),
        ):
            mock_robot.return_value.run_tests.return_value = TestResults(passed=1)
            mock_generator.return_value.generate_combined_summary.return_value = None

            result = orchestrator.run_tests()

        mock_pyats.assert_not_called()
        mock_robot.assert_called_once()
        assert result.api is not None
        assert result.api.state == ExecutionState.ERROR
        assert result.d2d is not None
        assert result.d2d.state == ExecutionState.ERROR
        assert result.robot is not None
        assert result.robot.passed == 1
