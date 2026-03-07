# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for controller detection in combined test execution.

Controller detection is now handled lazily by PyATSOrchestrator.run_tests(),
not by CombinedOrchestrator. These tests verify:
1. PyATSOrchestrator detects controller lazily (after dry-run check)
2. Detection failure returns error results (not sys.exit)
3. Dry-run mode skips controller detection entirely
4. Robot-only execution doesn't require controller credentials
"""

from unittest.mock import MagicMock, patch

import pytest

from nac_test.combined_orchestrator import CombinedOrchestrator
from nac_test.core.types import ExecutionState, PyATSResults, TestResults
from nac_test.pyats_core.orchestrator import PyATSOrchestrator

from .conftest import PYATS_TEST_FILE_CONTENT, ROBOT_TEST_FILE_CONTENT, PyATSTestEnv


class TestPyATSOrchestratorControllerDetection:
    """Tests for PyATSOrchestrator lazy controller detection."""

    @pytest.fixture(autouse=True)
    def _clean_env(self, clean_controller_env: None) -> None:
        """Apply shared clean_controller_env fixture to all tests in this class."""

    def test_controller_type_is_none_after_init(
        self, pyats_test_env: PyATSTestEnv
    ) -> None:
        """Test that controller_type is None after initialization (lazy detection)."""
        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_env.data_dir],
            test_dir=pyats_test_env.test_dir,
            output_dir=pyats_test_env.output_dir,
            merged_data_filename=pyats_test_env.merged_file.name,
        )

        assert orchestrator.controller_type is None

    def test_dry_run_skips_controller_detection(
        self, pyats_test_env: PyATSTestEnv
    ) -> None:
        """Test that dry-run mode skips controller detection entirely."""
        (pyats_test_env.test_dir / "test_verify.py").write_text(PYATS_TEST_FILE_CONTENT)

        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_env.data_dir],
            test_dir=pyats_test_env.test_dir,
            output_dir=pyats_test_env.output_dir,
            merged_data_filename=pyats_test_env.merged_file.name,
            dry_run=True,
        )

        with patch(
            "nac_test.pyats_core.orchestrator.detect_controller_type"
        ) as mock_detect:
            result = orchestrator.run_tests()

        mock_detect.assert_not_called()
        assert orchestrator.controller_type is None
        assert result.d2d is not None
        assert result.d2d.state == ExecutionState.SKIPPED

    def test_detection_failure_returns_error_results(
        self, pyats_test_env: PyATSTestEnv
    ) -> None:
        """Test that detection failure returns error results without sys.exit."""
        (pyats_test_env.test_dir / "test_verify.py").write_text(PYATS_TEST_FILE_CONTENT)

        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_env.data_dir],
            test_dir=pyats_test_env.test_dir,
            output_dir=pyats_test_env.output_dir,
            merged_data_filename=pyats_test_env.merged_file.name,
        )

        result = orchestrator.run_tests()

        assert result.api is not None
        assert result.api.state == ExecutionState.ERROR
        assert "Controller detection failed" in (result.api.reason or "")
        assert result.d2d is not None
        assert result.d2d.state == ExecutionState.ERROR

    def test_controller_detected_when_credentials_present(
        self, pyats_test_env: PyATSTestEnv, aci_controller_env: None
    ) -> None:
        """Test that controller is detected when credentials are present."""
        (pyats_test_env.test_dir / "test_verify.py").write_text(PYATS_TEST_FILE_CONTENT)

        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_env.data_dir],
            test_dir=pyats_test_env.test_dir,
            output_dir=pyats_test_env.output_dir,
            merged_data_filename=pyats_test_env.merged_file.name,
            dry_run=True,
        )

        assert orchestrator.controller_type is None

        orchestrator_real = PyATSOrchestrator(
            data_paths=[pyats_test_env.data_dir],
            test_dir=pyats_test_env.test_dir,
            output_dir=pyats_test_env.output_dir,
            merged_data_filename=pyats_test_env.merged_file.name,
        )

        assert orchestrator_real.controller_type is None

        from nac_test.pyats_core.orchestrator import detect_controller_type

        detected = detect_controller_type()
        assert detected == "ACI"


class TestCombinedOrchestratorDelegation:
    """Tests for CombinedOrchestrator delegation to PyATSOrchestrator."""

    @pytest.fixture(autouse=True)
    def _clean_env(self, clean_controller_env: None) -> None:
        """Apply shared clean_controller_env fixture to all tests in this class."""

    def test_combined_orchestrator_delegates_to_pyats(
        self, pyats_test_env: PyATSTestEnv, aci_controller_env: None
    ) -> None:
        """Test that CombinedOrchestrator delegates controller detection to PyATSOrchestrator."""
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

    def test_detection_failure_allows_robot_to_run(
        self, pyats_test_env: PyATSTestEnv
    ) -> None:
        """Test that Robot tests still run when PyATS controller detection fails."""
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
            mock_pyats.return_value.run_tests.return_value = PyATSResults(
                api=TestResults.from_error("Controller detection failed"),
                d2d=TestResults.from_error("Controller detection failed"),
            )
            mock_robot.return_value.run_tests.return_value = TestResults(passed=1)
            mock_generator.return_value.generate_combined_summary.return_value = None

            result = orchestrator.run_tests()

        mock_pyats.assert_called_once()
        mock_robot.assert_called_once()
        assert result.api is not None
        assert result.api.state == ExecutionState.ERROR
        assert result.robot is not None
        assert result.robot.passed == 1
