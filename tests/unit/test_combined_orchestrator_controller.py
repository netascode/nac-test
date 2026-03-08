# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for CombinedOrchestrator controller detection and pre-flight auth.

Tests verify that CombinedOrchestrator correctly handles:
- Controller detection (exits on failure)
- Pre-flight auth check (sets pre_flight_failure, allows Robot to continue)
- Dry-run mode (skips all auth)
- Render-only mode (skips PyATS entirely)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from _pytest.monkeypatch import MonkeyPatch

from nac_test.cli.validators import AuthCheckResult, AuthOutcome
from nac_test.combined_orchestrator import CombinedOrchestrator
from nac_test.core.constants import EXIT_ERROR
from nac_test.core.types import PyATSResults, TestResults
from nac_test.utils.logging import DEFAULT_LOGLEVEL

from .conftest import (
    AUTH_SUCCESS,
    PYATS_TEST_FILE_CONTENT,
    ROBOT_TEST_FILE_CONTENT,
    PyATSTestEnv,
)


class TestCombinedOrchestratorController:
    """Tests for CombinedOrchestrator controller detection and pre-flight auth."""

    @pytest.fixture(autouse=True)
    def _clean_env(self, clean_controller_env: None) -> None:
        """Apply shared clean_controller_env fixture to all tests in this class."""

    def test_controller_type_is_none_after_init(
        self, pyats_test_env: PyATSTestEnv, aci_controller_env: None
    ) -> None:
        """Controller type should be None after __init__ (detection deferred to run_tests)."""
        orchestrator = CombinedOrchestrator(
            data_paths=[pyats_test_env.data_dir],
            templates_dir=pyats_test_env.test_dir,
            output_dir=pyats_test_env.output_dir,
            merged_data_filename=pyats_test_env.merged_file.name,
        )

        assert orchestrator.controller_type is None

    def test_controller_detected_during_run_tests(
        self, pyats_test_env: PyATSTestEnv, aci_controller_env: None
    ) -> None:
        """Controller type should be detected when run_tests() is called with PyATS tests."""
        (pyats_test_env.test_dir / "test_verify.py").write_text(PYATS_TEST_FILE_CONTENT)

        orchestrator = CombinedOrchestrator(
            data_paths=[pyats_test_env.data_dir],
            templates_dir=pyats_test_env.test_dir,
            output_dir=pyats_test_env.output_dir,
            merged_data_filename=pyats_test_env.merged_file.name,
            dev_pyats_only=True,
        )

        assert orchestrator.controller_type is None

        with (
            patch(
                "nac_test.combined_orchestrator.preflight_auth_check",
                return_value=AUTH_SUCCESS,
            ),
            patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats,
            patch("nac_test.combined_orchestrator.CombinedReportGenerator") as mock_gen,
            patch("typer.echo"),
            patch("typer.secho"),
            patch.object(CombinedOrchestrator, "_check_python_version"),
        ):
            mock_instance = MagicMock()
            mock_instance.run_tests.return_value = PyATSResults()
            mock_pyats.return_value = mock_instance
            mock_gen_instance = MagicMock()
            mock_gen_instance.generate_combined_summary.return_value = None
            mock_gen.return_value = mock_gen_instance

            orchestrator.run_tests()

        assert orchestrator.controller_type == "ACI"

    def test_detection_failure_exits_during_run_tests(
        self, pyats_test_env: PyATSTestEnv
    ) -> None:
        """Detection failure should raise typer.Exit during run_tests(), not __init__."""
        (pyats_test_env.test_dir / "test_verify.py").write_text(PYATS_TEST_FILE_CONTENT)

        orchestrator = CombinedOrchestrator(
            data_paths=[pyats_test_env.data_dir],
            templates_dir=pyats_test_env.test_dir,
            output_dir=pyats_test_env.output_dir,
            merged_data_filename=pyats_test_env.merged_file.name,
            dev_pyats_only=True,
        )

        with (
            patch("typer.secho"),
        ):
            with pytest.raises(typer.Exit) as exc_info:
                orchestrator.run_tests()

            assert exc_info.value.exit_code == EXIT_ERROR

    def test_preflight_auth_failure_sets_pre_flight_failure_and_allows_robot(
        self, pyats_test_env: PyATSTestEnv, aci_controller_env: None
    ) -> None:
        """Pre-flight auth failure should set pre_flight_failure and allow Robot to run."""
        (pyats_test_env.test_dir / "test_verify.py").write_text(PYATS_TEST_FILE_CONTENT)
        (pyats_test_env.test_dir / "test.robot").write_text(ROBOT_TEST_FILE_CONTENT)

        orchestrator = CombinedOrchestrator(
            data_paths=[pyats_test_env.data_dir],
            templates_dir=pyats_test_env.test_dir,
            output_dir=pyats_test_env.output_dir,
            merged_data_filename=pyats_test_env.merged_file.name,
        )

        auth_failure = AuthCheckResult(
            success=False,
            reason=AuthOutcome.BAD_CREDENTIALS,
            controller_type="ACI",
            controller_url="https://apic.test.com",
            detail="Invalid credentials",
        )

        with (
            patch(
                "nac_test.combined_orchestrator.preflight_auth_check",
                return_value=auth_failure,
            ),
            patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats,
            patch("nac_test.combined_orchestrator.RobotOrchestrator") as mock_robot,
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator"
            ) as mock_generator,
            patch("nac_test.combined_orchestrator.display_auth_failure_banner"),
            patch("typer.echo"),
            patch("typer.secho"),
        ):
            mock_robot.return_value.run_tests.return_value = TestResults(passed=1)
            mock_generator.return_value.generate_combined_summary.return_value = None

            result = orchestrator.run_tests()

        mock_pyats.assert_not_called()
        mock_robot.assert_called_once()
        assert result.pre_flight_failure is not None
        assert result.pre_flight_failure.failure_type == "auth"
        assert result.api is None
        assert result.d2d is None
        assert result.robot is not None
        assert result.robot.passed == 1

    def test_preflight_unreachable_sets_pre_flight_failure_and_allows_robot(
        self, pyats_test_env: PyATSTestEnv, aci_controller_env: None
    ) -> None:
        """Pre-flight unreachable should set pre_flight_failure and allow Robot to run."""
        (pyats_test_env.test_dir / "test_verify.py").write_text(PYATS_TEST_FILE_CONTENT)
        (pyats_test_env.test_dir / "test.robot").write_text(ROBOT_TEST_FILE_CONTENT)

        orchestrator = CombinedOrchestrator(
            data_paths=[pyats_test_env.data_dir],
            templates_dir=pyats_test_env.test_dir,
            output_dir=pyats_test_env.output_dir,
            merged_data_filename=pyats_test_env.merged_file.name,
        )

        unreachable_result = AuthCheckResult(
            success=False,
            reason=AuthOutcome.UNREACHABLE,
            controller_type="ACI",
            controller_url="https://apic.test.com",
            detail="Connection refused",
        )

        with (
            patch(
                "nac_test.combined_orchestrator.preflight_auth_check",
                return_value=unreachable_result,
            ),
            patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats,
            patch("nac_test.combined_orchestrator.RobotOrchestrator") as mock_robot,
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator"
            ) as mock_generator,
            patch("nac_test.combined_orchestrator.display_unreachable_banner"),
            patch("typer.echo"),
            patch("typer.secho"),
        ):
            mock_robot.return_value.run_tests.return_value = TestResults(passed=1)
            mock_generator.return_value.generate_combined_summary.return_value = None

            result = orchestrator.run_tests()

        mock_pyats.assert_not_called()
        mock_robot.assert_called_once()
        assert result.pre_flight_failure is not None
        assert result.pre_flight_failure.failure_type == "unreachable"
        assert result.api is None
        assert result.d2d is None
        assert result.robot is not None
        assert result.robot.passed == 1

    def test_combined_orchestrator_passes_controller_to_pyats(
        self, pyats_test_env: PyATSTestEnv, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that CombinedOrchestrator passes controller type to PyATSOrchestrator."""
        monkeypatch.setenv("SDWAN_URL", "https://vmanage.test.com")
        monkeypatch.setenv("SDWAN_USERNAME", "admin")
        monkeypatch.setenv("SDWAN_PASSWORD", "password")

        (pyats_test_env.test_dir / "test_verify.py").write_text(PYATS_TEST_FILE_CONTENT)

        sdwan_auth = AuthCheckResult(
            success=True,
            reason=AuthOutcome.SUCCESS,
            controller_type="SDWAN",
            controller_url="https://vmanage.test.com",
            detail="OK",
        )

        orchestrator = CombinedOrchestrator(
            data_paths=[pyats_test_env.data_dir],
            templates_dir=pyats_test_env.test_dir,
            output_dir=pyats_test_env.output_dir,
            merged_data_filename=pyats_test_env.merged_file.name,
            dev_pyats_only=True,
        )

        with (
            patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats,
            patch("nac_test.combined_orchestrator.CombinedReportGenerator") as mock_gen,
            patch(
                "nac_test.combined_orchestrator.preflight_auth_check",
                return_value=sdwan_auth,
            ),
            patch("typer.secho"),
            patch("typer.echo"),
            patch.object(CombinedOrchestrator, "_check_python_version"),
        ):
            mock_instance = MagicMock()
            mock_instance.run_tests.return_value = PyATSResults()
            mock_pyats.return_value = mock_instance
            mock_gen.return_value.generate_combined_summary.return_value = None

            orchestrator.run_tests()

            mock_pyats.assert_called_once_with(
                data_paths=[pyats_test_env.data_dir],
                test_dir=pyats_test_env.test_dir,
                output_dir=pyats_test_env.output_dir,
                merged_data_filename=pyats_test_env.merged_file.name,
                minimal_reports=False,
                custom_testbed_path=None,
                controller_type="SDWAN",
                dry_run=False,
                verbose=False,
                loglevel=DEFAULT_LOGLEVEL,
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
            patch(
                "nac_test.combined_orchestrator.detect_controller_type"
            ) as mock_detect,
            patch("typer.echo"),
            patch("typer.secho"),
        ):
            mock_robot.return_value = MagicMock()

            orchestrator.run_tests()

        mock_detect.assert_not_called()
        mock_pyats.assert_not_called()
        mock_robot.assert_called_once()

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
