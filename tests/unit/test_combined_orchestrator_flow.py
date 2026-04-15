# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for CombinedOrchestrator.run_tests() flow control.

These tests verify the orchestration flow using mocks to ensure:
- Correct orchestrators are called based on discovery results
- Dev mode flags properly filter which test types run
- render_only mode skips dashboard generation
- Combined dashboard is generated for all execution modes
"""

import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from _pytest.monkeypatch import MonkeyPatch

from nac_test.combined_orchestrator import CombinedOrchestrator
from nac_test.core.types import CombinedResults, PyATSResults, TestResults
from tests.unit.conftest import AUTH_SUCCESS


class TestCombinedOrchestratorFlow:
    """Tests for CombinedOrchestrator.run_tests() execution flow."""

    @pytest.fixture(autouse=True)
    def setup_controller_env(self, monkeypatch: MonkeyPatch) -> None:
        """Set up controller environment for all tests."""
        # Clear any existing controller env vars
        for key in list(os.environ.keys()):
            if any(
                prefix in key
                for prefix in ["ACI_", "SDWAN_", "CC_", "MERAKI_", "FMC_", "ISE_"]
            ):
                monkeypatch.delenv(key, raising=False)
        # Set up ACI credentials for all tests
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

    @pytest.fixture(autouse=True)
    def _mock_preflight_auth(self) -> Generator[None, None, None]:
        """Mock controller detection and preflight auth for all tests.

        These are only reached when has_pyats=True and not render_only,
        but having them present for all tests is harmless.
        """
        with (
            patch(
                "nac_test.combined_orchestrator.detect_controller_type",
                return_value="ACI",
            ),
            patch(
                "nac_test.combined_orchestrator.preflight_auth_check",
                return_value=AUTH_SUCCESS,
            ),
        ):
            yield

    @pytest.fixture
    def orchestrator(self, tmp_path: Path) -> CombinedOrchestrator:
        """Create a CombinedOrchestrator instance for testing."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        return CombinedOrchestrator(
            data_paths=[data_dir],
            templates_dir=templates_dir,
            output_dir=output_dir,
        )

    @pytest.fixture
    def pyats_results(self) -> PyATSResults:
        """Create sample PyATS test results."""
        api_results = TestResults(passed=4, failed=1, skipped=0)
        d2d_results = TestResults(passed=4, failed=0, skipped=1)
        return PyATSResults(api=api_results, d2d=d2d_results)

    @pytest.fixture
    def robot_results(self) -> TestResults:
        """Create sample Robot test results."""
        return TestResults(passed=4, failed=1, skipped=0)

    @pytest.fixture
    def mock_pyats_instance(self, pyats_results: PyATSResults) -> MagicMock:
        """Shared mock for PyATSOrchestrator instance with default results."""
        m = MagicMock()
        m.run_tests.return_value = pyats_results
        return m

    @pytest.fixture
    def mock_robot_instance(self, robot_results: TestResults) -> MagicMock:
        """Shared mock for RobotOrchestrator instance with default results."""
        m = MagicMock()
        m.run_tests.return_value = robot_results
        return m

    @pytest.fixture
    def mock_gen_instance(self) -> MagicMock:
        """Shared mock for CombinedReportGenerator instance."""
        m = MagicMock()
        m.generate_combined_summary.return_value = Path("/tmp/combined_summary.html")
        return m


class TestDiscoveryBasedFlow(TestCombinedOrchestratorFlow):
    """Tests for flow control based on _discover_test_types() results."""

    def test_no_tests_found_returns_empty_results(
        self, orchestrator: CombinedOrchestrator
    ) -> None:
        """When no tests are discovered, return empty CombinedResults without calling orchestrators."""
        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(False, False)
            ),
            patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats,
            patch("nac_test.combined_orchestrator.RobotOrchestrator") as mock_robot,
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator"
            ) as mock_generator,
            patch("typer.echo"),
        ):
            result = orchestrator.run_tests()

        # No orchestrators should be called
        mock_pyats.assert_not_called()
        mock_robot.assert_not_called()
        mock_generator.assert_not_called()

        # Should return empty CombinedResults
        assert isinstance(result, CombinedResults)
        assert result.total == 0
        assert result.passed == 0
        assert result.failed == 0

    def test_only_pyats_discovered_runs_pyats_only(
        self,
        orchestrator: CombinedOrchestrator,
        mock_pyats_instance: MagicMock,
        mock_gen_instance: MagicMock,
    ) -> None:
        """When only PyATS tests are discovered, only PyATS orchestrator runs."""
        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(True, False)
            ),
            patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator",
                return_value=mock_pyats_instance,
            ) as mock_pyats,
            patch("nac_test.combined_orchestrator.RobotOrchestrator") as mock_robot,
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator",
                return_value=mock_gen_instance,
            ) as mock_generator,
            patch("typer.echo"),
        ):
            result = orchestrator.run_tests()

        # Only PyATS should be called
        mock_pyats.assert_called_once()
        mock_pyats_instance.run_tests.assert_called_once()
        mock_robot.assert_not_called()

        # Dashboard should still be generated
        mock_generator.assert_called_once()
        mock_gen_instance.generate_combined_summary.assert_called_once()

        # Results should match PyATS results (API + D2D)
        assert result.total == 10
        assert result.passed == 8
        assert result.api is not None
        assert result.d2d is not None
        assert result.robot is None

    def test_only_robot_discovered_runs_robot_only(
        self,
        orchestrator: CombinedOrchestrator,
        mock_robot_instance: MagicMock,
        mock_gen_instance: MagicMock,
    ) -> None:
        """When only Robot tests are discovered, only Robot orchestrator runs."""
        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(False, True)
            ),
            patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats,
            patch(
                "nac_test.combined_orchestrator.RobotOrchestrator",
                return_value=mock_robot_instance,
            ) as mock_robot,
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator",
                return_value=mock_gen_instance,
            ) as mock_generator,
            patch("typer.echo"),
        ):
            result = orchestrator.run_tests()

        # Only Robot should be called
        mock_pyats.assert_not_called()
        mock_robot.assert_called_once()
        mock_robot_instance.run_tests.assert_called_once()

        # Dashboard should still be generated
        mock_generator.assert_called_once()

        # Results should match Robot results
        assert result.total == 5
        assert result.passed == 4
        assert result.robot is not None
        assert result.api is None
        assert result.d2d is None

    def test_both_discovered_runs_both_orchestrators(
        self,
        orchestrator: CombinedOrchestrator,
        mock_pyats_instance: MagicMock,
        mock_robot_instance: MagicMock,
        mock_gen_instance: MagicMock,
    ) -> None:
        """When both test types are discovered, both orchestrators run."""
        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(True, True)
            ),
            patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator",
                return_value=mock_pyats_instance,
            ) as mock_pyats,
            patch(
                "nac_test.combined_orchestrator.RobotOrchestrator",
                return_value=mock_robot_instance,
            ) as mock_robot,
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator",
                return_value=mock_gen_instance,
            ) as mock_generator,
            patch("typer.echo"),
        ):
            result = orchestrator.run_tests()

        # Both should be called
        mock_pyats.assert_called_once()
        mock_pyats_instance.run_tests.assert_called_once()
        mock_robot.assert_called_once()
        mock_robot_instance.run_tests.assert_called_once()

        # Dashboard should be generated
        mock_generator.assert_called_once()

        # Results should be combined
        assert result.total == 15  # 10 + 5
        assert result.passed == 12  # 8 + 4
        assert result.api is not None
        assert result.d2d is not None
        assert result.robot is not None


class TestDevModeFlow(TestCombinedOrchestratorFlow):
    """Tests for dev mode flag behavior."""

    def test_dev_pyats_only_skips_robot(
        self,
        tmp_path: Path,
        monkeypatch: MonkeyPatch,
        mock_pyats_instance: MagicMock,
        mock_gen_instance: MagicMock,
    ) -> None:
        """dev_pyats_only flag should skip Robot even if Robot tests are discovered."""
        # Set up controller env
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        orchestrator = CombinedOrchestrator(
            data_paths=[data_dir],
            templates_dir=templates_dir,
            output_dir=output_dir,
            dev_pyats_only=True,
        )

        # Discovery returns both test types
        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(True, True)
            ),
            patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator",
                return_value=mock_pyats_instance,
            ) as mock_pyats,
            patch("nac_test.combined_orchestrator.RobotOrchestrator") as mock_robot,
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator",
                return_value=mock_gen_instance,
            ) as mock_generator,
            patch("typer.echo"),
            patch("typer.secho"),
        ):
            result = orchestrator.run_tests()

        # PyATS should run, Robot should NOT
        mock_pyats.assert_called_once()
        mock_robot.assert_not_called()

        # Dashboard should still be generated
        mock_generator.assert_called_once()

        # Results should only include PyATS
        assert result.total == 10

    def test_dev_robot_only_skips_pyats(
        self,
        tmp_path: Path,
        monkeypatch: MonkeyPatch,
        mock_robot_instance: MagicMock,
        mock_gen_instance: MagicMock,
    ) -> None:
        """dev_robot_only flag should skip PyATS even if PyATS tests are discovered."""
        # Set up controller env
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        orchestrator = CombinedOrchestrator(
            data_paths=[data_dir],
            templates_dir=templates_dir,
            output_dir=output_dir,
            dev_robot_only=True,
        )

        # Discovery returns both test types
        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(True, True)
            ),
            patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats,
            patch(
                "nac_test.combined_orchestrator.RobotOrchestrator",
                return_value=mock_robot_instance,
            ) as mock_robot,
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator",
                return_value=mock_gen_instance,
            ) as mock_generator,
            patch("typer.echo"),
            patch("typer.secho"),
        ):
            result = orchestrator.run_tests()

        # Robot should run, PyATS should NOT
        mock_pyats.assert_not_called()
        mock_robot.assert_called_once()

        # Dashboard should still be generated
        mock_generator.assert_called_once()

        # Results should only include Robot
        assert result.total == 5

    def test_dev_pyats_only_generates_dashboard(
        self,
        tmp_path: Path,
        monkeypatch: MonkeyPatch,
        mock_pyats_instance: MagicMock,
        mock_gen_instance: MagicMock,
    ) -> None:
        """dev_pyats_only mode should still generate the combined dashboard."""
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        orchestrator = CombinedOrchestrator(
            data_paths=[data_dir],
            templates_dir=templates_dir,
            output_dir=output_dir,
            dev_pyats_only=True,
        )

        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(True, False)
            ),
            patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator",
                return_value=mock_pyats_instance,
            ),
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator",
                return_value=mock_gen_instance,
            ) as mock_generator,
            patch("typer.echo"),
            patch("typer.secho"),
        ):
            orchestrator.run_tests()

        # Dashboard should be generated
        mock_generator.assert_called_once_with(output_dir)
        mock_gen_instance.generate_combined_summary.assert_called_once()

        # Verify CombinedResults was passed to generator with PyATS data
        call_args = mock_gen_instance.generate_combined_summary.call_args
        assert call_args is not None
        combined_results = call_args[0][0]
        assert isinstance(combined_results, CombinedResults)
        assert combined_results.api is not None
        assert combined_results.d2d is not None


class TestRenderOnlyMode(TestCombinedOrchestratorFlow):
    """Tests for render_only mode behavior."""

    def test_render_only_skips_dashboard_generation(
        self, tmp_path: Path, monkeypatch: MonkeyPatch, robot_results: TestResults
    ) -> None:
        """render_only mode should skip dashboard generation."""
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        orchestrator = CombinedOrchestrator(
            data_paths=[data_dir],
            templates_dir=templates_dir,
            output_dir=output_dir,
            render_only=True,
        )

        mock_robot_instance = MagicMock()
        mock_robot_instance.run_tests.return_value = robot_results

        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(False, True)
            ),
            patch(
                "nac_test.combined_orchestrator.RobotOrchestrator",
                return_value=mock_robot_instance,
            ) as mock_robot,
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator"
            ) as mock_generator,
            patch("typer.echo"),
        ):
            orchestrator.run_tests()

        # Robot orchestrator should be called
        mock_robot.assert_called_once()

        # Dashboard should NOT be generated
        mock_generator.assert_not_called()

    def test_render_only_converts_robot_exception_to_results(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """render_only mode should convert Robot exceptions to TestResults with errors."""
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        orchestrator = CombinedOrchestrator(
            data_paths=[data_dir],
            templates_dir=templates_dir,
            output_dir=output_dir,
            render_only=True,
        )

        mock_robot_instance = MagicMock()
        mock_robot_instance.run_tests.side_effect = ValueError("Template error")

        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(False, True)
            ),
            patch(
                "nac_test.combined_orchestrator.RobotOrchestrator",
                return_value=mock_robot_instance,
            ),
            patch("typer.echo"),
        ):
            # Should not raise exception - should convert to TestResults.from_error()
            results = orchestrator.run_tests()

            # Verify that the error was properly converted to TestResults
            assert results.robot is not None
            assert results.robot.has_error
            assert results.robot.reason is not None
            assert "Template error" in results.robot.reason

    def test_non_render_only_catches_robot_exception(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Non render_only mode should catch Robot exceptions and record error in results."""
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        orchestrator = CombinedOrchestrator(
            data_paths=[data_dir],
            templates_dir=templates_dir,
            output_dir=output_dir,
            render_only=False,  # Not render-only
        )

        mock_robot_instance = MagicMock()
        mock_robot_instance.run_tests.side_effect = ValueError("Execution error")
        mock_gen_instance = MagicMock()
        mock_gen_instance.generate_combined_summary.return_value = Path(
            "/tmp/combined_summary.html"
        )

        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(False, True)
            ),
            patch(
                "nac_test.combined_orchestrator.RobotOrchestrator",
                return_value=mock_robot_instance,
            ),
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator",
                return_value=mock_gen_instance,
            ) as mock_generator,
            patch("typer.echo"),
            patch("typer.style"),
        ):
            # Should NOT raise - exception is caught
            result = orchestrator.run_tests()

        # Results should have zero tests but record the error
        assert result.total == 0
        assert result.has_errors is True
        assert "Execution error" in result.errors[0]

        # Robot should be set with error
        assert result.robot is not None
        assert result.robot.has_error is True

        # Dashboard should still be generated
        mock_generator.assert_called_once()


class TestDashboardGeneration(TestCombinedOrchestratorFlow):
    """Tests for combined dashboard generation."""

    def test_dashboard_receives_by_framework_data(
        self,
        orchestrator: CombinedOrchestrator,
        mock_pyats_instance: MagicMock,
        mock_robot_instance: MagicMock,
        mock_gen_instance: MagicMock,
    ) -> None:
        """Dashboard generator should receive frameworks dict from combined results."""
        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(True, True)
            ),
            patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator",
                return_value=mock_pyats_instance,
            ),
            patch(
                "nac_test.combined_orchestrator.RobotOrchestrator",
                return_value=mock_robot_instance,
            ),
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator",
                return_value=mock_gen_instance,
            ),
            patch("typer.echo"),
        ):
            orchestrator.run_tests()

        # Verify generate_combined_summary was called with CombinedResults
        mock_gen_instance.generate_combined_summary.assert_called_once()
        call_args = mock_gen_instance.generate_combined_summary.call_args
        assert call_args is not None

        combined_results = call_args[0][0]
        # Should be CombinedResults with all frameworks populated
        assert isinstance(combined_results, CombinedResults)
        assert combined_results.api is not None
        assert combined_results.d2d is not None
        assert combined_results.robot is not None

    def test_dashboard_generated_even_with_empty_results(
        self, orchestrator: CombinedOrchestrator
    ) -> None:
        """Dashboard should be generated even when orchestrators return empty results."""
        # PyATS returns PyATSResults with None attributes when no tests found
        empty_pyats_results = PyATSResults()
        mock_pyats_instance = MagicMock()
        mock_pyats_instance.run_tests.return_value = empty_pyats_results
        mock_gen_instance = MagicMock()
        mock_gen_instance.generate_combined_summary.return_value = Path(
            "/tmp/combined_summary.html"
        )

        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(True, False)
            ),
            patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator",
                return_value=mock_pyats_instance,
            ),
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator",
                return_value=mock_gen_instance,
            ) as mock_generator,
            patch("typer.echo"),
        ):
            orchestrator.run_tests()

        # Dashboard should still be generated
        mock_generator.assert_called_once()
        mock_gen_instance.generate_combined_summary.assert_called_once()


class TestExecutionSummary(TestCombinedOrchestratorFlow):
    """Tests for execution summary printing."""

    def test_print_execution_summary_called_when_not_render_only(
        self,
        orchestrator: CombinedOrchestrator,
        mock_pyats_instance: MagicMock,
        mock_gen_instance: MagicMock,
    ) -> None:
        """_print_execution_summary should be called when not in render_only mode."""
        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(True, False)
            ),
            patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator",
                return_value=mock_pyats_instance,
            ),
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator",
                return_value=mock_gen_instance,
            ),
            patch.object(orchestrator, "_print_execution_summary") as mock_print,
            patch("typer.echo"),
        ):
            orchestrator.run_tests()

        # Summary should be printed
        mock_print.assert_called_once()
        call_args = mock_print.call_args
        # Single arg is CombinedResults (signature changed in #540)
        results = call_args[0][0]
        assert isinstance(results, CombinedResults)
        assert results.total == 10

    def test_print_execution_summary_not_called_in_render_only(
        self, tmp_path: Path, monkeypatch: MonkeyPatch, robot_results: TestResults
    ) -> None:
        """_print_execution_summary should NOT be called in render_only mode."""
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        orchestrator = CombinedOrchestrator(
            data_paths=[data_dir],
            templates_dir=templates_dir,
            output_dir=output_dir,
            render_only=True,
        )

        mock_robot_instance = MagicMock()
        mock_robot_instance.run_tests.return_value = robot_results

        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(False, True)
            ),
            patch(
                "nac_test.combined_orchestrator.RobotOrchestrator",
                return_value=mock_robot_instance,
            ),
            patch.object(orchestrator, "_print_execution_summary") as mock_print,
            patch("typer.echo"),
        ):
            orchestrator.run_tests()

        # Summary should NOT be printed in render_only mode
        mock_print.assert_not_called()


class TestStaleArtifactWarnings(TestCombinedOrchestratorFlow):
    """Tests for stale artifact warning functionality."""

    def test_warning_fires_when_stale_robot_files_present(
        self, orchestrator: CombinedOrchestrator
    ) -> None:
        """Warning fires when stale Robot files present and Robot framework didn't run."""
        # Create stale Robot artifacts in output directory
        (orchestrator.output_dir / "log.html").touch()
        (orchestrator.output_dir / "output.xml").touch()
        (orchestrator.output_dir / "report.html").touch()

        # Only PyATS tests discovered, Robot didn't run
        empty_pyats_results = PyATSResults()
        mock_pyats_instance = MagicMock()
        mock_pyats_instance.run_tests.return_value = empty_pyats_results
        mock_gen_instance = MagicMock()
        mock_gen_instance.generate_combined_summary.return_value = None

        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(True, False)
            ),
            patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator",
                return_value=mock_pyats_instance,
            ),
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator",
                return_value=mock_gen_instance,
            ),
            patch("typer.echo"),
            patch("typer.secho") as mock_secho,
        ):
            orchestrator.run_tests()

        assert mock_secho.call_count == 2

        first_call = mock_secho.call_args_list[0]
        warning_message = first_call[0][0]
        assert "Stale artifacts from a previous run" in warning_message
        assert first_call[1]["fg"] == typer.colors.YELLOW
        assert first_call[1]["err"] is True

        second_call = mock_secho.call_args_list[1]
        files_message = second_call[0][0]
        assert "log.html" in files_message
        assert "output.xml" in files_message
        assert "report.html" in files_message
        assert second_call[1]["fg"] == typer.colors.YELLOW
        assert second_call[1]["err"] is True

    def test_warning_does_not_fire_when_run_was_clean(
        self, orchestrator: CombinedOrchestrator, robot_results: TestResults
    ) -> None:
        """Warning does NOT fire when Robot framework ran and produced artifacts."""
        # Create Robot artifacts in output directory
        (orchestrator.output_dir / "log.html").touch()
        (orchestrator.output_dir / "output.xml").touch()
        (orchestrator.output_dir / "report.html").touch()

        # Robot tests ran and produced results
        mock_robot_instance = MagicMock()
        mock_robot_instance.run_tests.return_value = robot_results
        mock_gen_instance = MagicMock()
        mock_gen_instance.generate_combined_summary.return_value = None

        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(False, True)
            ),
            patch(
                "nac_test.combined_orchestrator.RobotOrchestrator",
                return_value=mock_robot_instance,
            ),
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator",
                return_value=mock_gen_instance,
            ),
            patch("typer.echo"),
            patch("typer.secho") as mock_secho,
        ):
            orchestrator.run_tests()

        # Warning should NOT have been called (Robot framework ran)
        mock_secho.assert_not_called()

    def test_warning_fires_when_robot_ran_but_empty(
        self, orchestrator: CombinedOrchestrator
    ) -> None:
        """Warning fires when Robot ran but produced empty results (e.g., all tests filtered out)."""
        # Create Robot artifacts in output directory
        (orchestrator.output_dir / "log.html").touch()
        (orchestrator.output_dir / "output.xml").touch()
        (orchestrator.output_dir / "report.html").touch()

        # Robot tests ran but produced empty results (total=0)
        empty_robot_results = TestResults()
        mock_robot_instance = MagicMock()
        mock_robot_instance.run_tests.return_value = empty_robot_results
        mock_gen_instance = MagicMock()
        mock_gen_instance.generate_combined_summary.return_value = None

        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(False, True)
            ),
            patch(
                "nac_test.combined_orchestrator.RobotOrchestrator",
                return_value=mock_robot_instance,
            ),
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator",
                return_value=mock_gen_instance,
            ),
            patch("typer.echo"),
            patch("typer.secho") as mock_secho,
        ):
            orchestrator.run_tests()

        # Warning SHOULD fire because robot results are empty
        assert mock_secho.call_count == 2

        first_call = mock_secho.call_args_list[0]
        warning_message = first_call[0][0]
        assert "Stale artifacts from a previous run" in warning_message
        assert first_call[1]["fg"] == typer.colors.YELLOW

    def test_warning_includes_correct_filenames(
        self, orchestrator: CombinedOrchestrator
    ) -> None:
        """Warning includes correct file names when stale artifacts present."""
        # Create only some stale Robot artifacts
        (orchestrator.output_dir / "log.html").touch()
        (orchestrator.output_dir / "xunit.xml").touch()
        # Don't create output.xml and report.html

        # Only PyATS tests discovered, Robot didn't run
        empty_pyats_results = PyATSResults()
        mock_pyats_instance = MagicMock()
        mock_pyats_instance.run_tests.return_value = empty_pyats_results
        mock_gen_instance = MagicMock()
        mock_gen_instance.generate_combined_summary.return_value = None

        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(True, False)
            ),
            patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator",
                return_value=mock_pyats_instance,
            ),
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator",
                return_value=mock_gen_instance,
            ),
            patch("typer.echo"),
            patch("typer.secho") as mock_secho,
        ):
            orchestrator.run_tests()

        assert mock_secho.call_count == 2
        second_call = mock_secho.call_args_list[1]
        files_message = second_call[0][0]
        assert "log.html" in files_message
        assert "xunit.xml" in files_message
        assert "output.xml" not in files_message
        assert "report.html" not in files_message

    def test_no_warning_when_no_stale_files(
        self, orchestrator: CombinedOrchestrator
    ) -> None:
        """No warning when no stale files present."""
        # Don't create any stale artifacts

        # Only PyATS tests discovered, Robot didn't run
        empty_pyats_results = PyATSResults()
        mock_pyats_instance = MagicMock()
        mock_pyats_instance.run_tests.return_value = empty_pyats_results
        mock_gen_instance = MagicMock()
        mock_gen_instance.generate_combined_summary.return_value = None

        with (
            patch.object(
                orchestrator, "_discover_test_types", return_value=(True, False)
            ),
            patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator",
                return_value=mock_pyats_instance,
            ),
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator",
                return_value=mock_gen_instance,
            ),
            patch("typer.echo"),
            patch("typer.secho") as mock_secho,
        ):
            orchestrator.run_tests()

        # Warning should NOT have been called (no stale files)
        mock_secho.assert_not_called()


class TestWindowsPlatformBehavior(TestCombinedOrchestratorFlow):
    """Tests for Windows platform behavior (PYATS_SUPPORTED=False)."""

    @pytest.fixture
    def orchestrator_with_both_types(
        self, orchestrator: CombinedOrchestrator
    ) -> CombinedOrchestrator:
        """Add both Robot and PyATS test files to the orchestrator's templates directory."""
        # Robot template
        (orchestrator.templates_dir / "test.robot").write_text(
            "*** Test Cases ***\nDummy\n    Log    ok"
        )
        return orchestrator

    def test_pyats_found_but_not_supported_shows_warning_and_runs_robot(
        self,
        orchestrator_with_both_types: CombinedOrchestrator,
        robot_results: TestResults,
    ) -> None:
        """When PyATS tests found but PYATS_SUPPORTED is False, warn and run Robot only."""
        mock_robot_instance = MagicMock()
        mock_robot_instance.run_tests.return_value = robot_results

        mock_gen_instance = MagicMock()
        mock_gen_instance.generate_combined_summary.return_value = Path(
            "/tmp/combined_summary.html"
        )

        with (
            patch("nac_test.combined_orchestrator.PYATS_SUPPORTED", False),
            # Mock discovery to return both test types found
            patch.object(
                orchestrator_with_both_types,
                "_discover_test_types",
                return_value=(True, True),
            ),
            patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats,
            patch("nac_test.combined_orchestrator.RobotOrchestrator") as mock_robot,
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator"
            ) as mock_generator,
            patch("typer.echo"),
            patch("typer.secho") as mock_secho,
        ):
            mock_robot.return_value = mock_robot_instance
            mock_generator.return_value = mock_gen_instance

            result = orchestrator_with_both_types.run_tests()

        # PyATS should NOT be called (not supported)
        mock_pyats.assert_not_called()

        # Robot SHOULD be called
        mock_robot.assert_called_once()
        mock_robot_instance.run_tests.assert_called_once()

        # Warning should be emitted about PyATS tests found but skipped
        mock_secho.assert_any_call(
            "\n⚠️  PyATS tests found but skipped — PyATS is not supported on Windows.",
            fg=typer.colors.YELLOW,
        )

        # Results should only include Robot
        assert result.robot is not None
        assert result.api is None
        assert result.d2d is None

    def test_no_pyats_tests_and_not_supported_no_warning(
        self,
        orchestrator_with_both_types: CombinedOrchestrator,
        robot_results: TestResults,
    ) -> None:
        """When no PyATS tests found and PYATS_SUPPORTED is False, no warning shown."""
        mock_robot_instance = MagicMock()
        mock_robot_instance.run_tests.return_value = robot_results

        mock_gen_instance = MagicMock()
        mock_gen_instance.generate_combined_summary.return_value = Path(
            "/tmp/combined_summary.html"
        )

        with (
            patch("nac_test.combined_orchestrator.PYATS_SUPPORTED", False),
            # Mock discovery to return only Robot tests found (no PyATS)
            patch.object(
                orchestrator_with_both_types,
                "_discover_test_types",
                return_value=(False, True),
            ),
            patch("nac_test.combined_orchestrator.PyATSOrchestrator") as mock_pyats,
            patch("nac_test.combined_orchestrator.RobotOrchestrator") as mock_robot,
            patch(
                "nac_test.combined_orchestrator.CombinedReportGenerator"
            ) as mock_generator,
            patch("typer.echo"),
            patch("typer.secho") as mock_secho,
        ):
            mock_robot.return_value = mock_robot_instance
            mock_generator.return_value = mock_gen_instance

            result = orchestrator_with_both_types.run_tests()

        # PyATS should NOT be called
        mock_pyats.assert_not_called()

        # Robot SHOULD be called
        mock_robot.assert_called_once()

        # NO warning should be emitted about PyATS (no PyATS tests found)
        pyats_warning_calls = [
            call
            for call in mock_secho.call_args_list
            if "PyATS" in str(call) and "not supported" in str(call)
        ]
        assert len(pyats_warning_calls) == 0, "Should not warn when no PyATS tests"

        # Results should only include Robot
        assert result.robot is not None
        assert result.api is None


class TestDiscoverTestTypes(TestCombinedOrchestratorFlow):
    """Tests for _discover_test_types() method."""

    @pytest.fixture
    def orchestrator_with_robot(
        self, orchestrator: CombinedOrchestrator
    ) -> CombinedOrchestrator:
        """Add a Robot template to the orchestrator's templates directory."""
        (orchestrator.templates_dir / "test.robot").write_text(
            "*** Test Cases ***\nDummy\n    Log    ok"
        )
        return orchestrator

    def test_discovers_robot_files(
        self, orchestrator_with_robot: CombinedOrchestrator
    ) -> None:
        """Should discover Robot files when present."""
        has_pyats, has_robot = orchestrator_with_robot._discover_test_types()

        # Robot should be discovered (we created a .robot file)
        assert has_robot is True
        # PyATS should be False (no valid PyATS test files)
        assert has_pyats is False

    def test_no_tests_returns_false_false(
        self, orchestrator: CombinedOrchestrator
    ) -> None:
        """When no test files exist, both should be False."""
        has_pyats, has_robot = orchestrator._discover_test_types()

        assert has_pyats is False
        assert has_robot is False
