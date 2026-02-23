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
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch

from nac_test.combined_orchestrator import CombinedOrchestrator
from nac_test.core.types import CombinedResults, PyATSResults, TestResults


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
            merged_data_filename="merged.yaml",
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


class TestDiscoveryBasedFlow(TestCombinedOrchestratorFlow):
    """Tests for flow control based on _discover_test_types() results."""

    def test_no_tests_found_returns_empty_results(
        self, orchestrator: CombinedOrchestrator
    ) -> None:
        """When no tests are discovered, return empty CombinedResults without calling orchestrators."""
        with patch.object(
            orchestrator, "_discover_test_types", return_value=(False, False)
        ):
            with patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator"
            ) as mock_pyats:
                with patch(
                    "nac_test.combined_orchestrator.RobotOrchestrator"
                ) as mock_robot:
                    with patch(
                        "nac_test.combined_orchestrator.CombinedReportGenerator"
                    ) as mock_generator:
                        with patch("typer.echo"):
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
        pyats_results: PyATSResults,
    ) -> None:
        """When only PyATS tests are discovered, only PyATS orchestrator runs."""
        with patch.object(
            orchestrator, "_discover_test_types", return_value=(True, False)
        ):
            with patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator"
            ) as mock_pyats:
                mock_pyats_instance = MagicMock()
                mock_pyats_instance.run_tests.return_value = pyats_results
                mock_pyats.return_value = mock_pyats_instance

                with patch(
                    "nac_test.combined_orchestrator.RobotOrchestrator"
                ) as mock_robot:
                    with patch(
                        "nac_test.combined_orchestrator.CombinedReportGenerator"
                    ) as mock_generator:
                        mock_gen_instance = MagicMock()
                        mock_gen_instance.generate_combined_summary.return_value = Path(
                            "/tmp/combined_summary.html"
                        )
                        mock_generator.return_value = mock_gen_instance

                        with patch("typer.echo"):
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
        self, orchestrator: CombinedOrchestrator, robot_results: TestResults
    ) -> None:
        """When only Robot tests are discovered, only Robot orchestrator runs."""
        with patch.object(
            orchestrator, "_discover_test_types", return_value=(False, True)
        ):
            with patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator"
            ) as mock_pyats:
                with patch(
                    "nac_test.combined_orchestrator.RobotOrchestrator"
                ) as mock_robot:
                    mock_robot_instance = MagicMock()
                    mock_robot_instance.run_tests.return_value = robot_results
                    mock_robot.return_value = mock_robot_instance

                    with patch(
                        "nac_test.combined_orchestrator.CombinedReportGenerator"
                    ) as mock_generator:
                        mock_gen_instance = MagicMock()
                        mock_gen_instance.generate_combined_summary.return_value = Path(
                            "/tmp/combined_summary.html"
                        )
                        mock_generator.return_value = mock_gen_instance

                        with patch("typer.echo"):
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
        pyats_results: PyATSResults,
        robot_results: TestResults,
    ) -> None:
        """When both test types are discovered, both orchestrators run."""
        with patch.object(
            orchestrator, "_discover_test_types", return_value=(True, True)
        ):
            with patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator"
            ) as mock_pyats:
                mock_pyats_instance = MagicMock()
                mock_pyats_instance.run_tests.return_value = pyats_results
                mock_pyats.return_value = mock_pyats_instance

                with patch(
                    "nac_test.combined_orchestrator.RobotOrchestrator"
                ) as mock_robot:
                    mock_robot_instance = MagicMock()
                    mock_robot_instance.run_tests.return_value = robot_results
                    mock_robot.return_value = mock_robot_instance

                    with patch(
                        "nac_test.combined_orchestrator.CombinedReportGenerator"
                    ) as mock_generator:
                        mock_gen_instance = MagicMock()
                        mock_gen_instance.generate_combined_summary.return_value = Path(
                            "/tmp/combined_summary.html"
                        )
                        mock_generator.return_value = mock_gen_instance

                        with patch("typer.echo"):
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
        pyats_results: PyATSResults,
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
            merged_data_filename="merged.yaml",
            dev_pyats_only=True,
        )

        # Discovery returns both test types
        with patch.object(
            orchestrator, "_discover_test_types", return_value=(True, True)
        ):
            with patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator"
            ) as mock_pyats:
                mock_pyats_instance = MagicMock()
                mock_pyats_instance.run_tests.return_value = pyats_results
                mock_pyats.return_value = mock_pyats_instance

                with patch(
                    "nac_test.combined_orchestrator.RobotOrchestrator"
                ) as mock_robot:
                    with patch(
                        "nac_test.combined_orchestrator.CombinedReportGenerator"
                    ) as mock_generator:
                        mock_gen_instance = MagicMock()
                        mock_gen_instance.generate_combined_summary.return_value = Path(
                            "/tmp/combined_summary.html"
                        )
                        mock_generator.return_value = mock_gen_instance

                        with patch("typer.echo"), patch("typer.secho"):
                            result = orchestrator.run_tests()

        # PyATS should run, Robot should NOT
        mock_pyats.assert_called_once()
        mock_robot.assert_not_called()

        # Dashboard should still be generated
        mock_generator.assert_called_once()

        # Results should only include PyATS
        assert result.total == 10

    def test_dev_robot_only_skips_pyats(
        self, tmp_path: Path, monkeypatch: MonkeyPatch, robot_results: TestResults
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
            merged_data_filename="merged.yaml",
            dev_robot_only=True,
        )

        # Discovery returns both test types
        with patch.object(
            orchestrator, "_discover_test_types", return_value=(True, True)
        ):
            with patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator"
            ) as mock_pyats:
                with patch(
                    "nac_test.combined_orchestrator.RobotOrchestrator"
                ) as mock_robot:
                    mock_robot_instance = MagicMock()
                    mock_robot_instance.run_tests.return_value = robot_results
                    mock_robot.return_value = mock_robot_instance

                    with patch(
                        "nac_test.combined_orchestrator.CombinedReportGenerator"
                    ) as mock_generator:
                        mock_gen_instance = MagicMock()
                        mock_gen_instance.generate_combined_summary.return_value = Path(
                            "/tmp/combined_summary.html"
                        )
                        mock_generator.return_value = mock_gen_instance

                        with patch("typer.echo"), patch("typer.secho"):
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
        pyats_results: PyATSResults,
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
            merged_data_filename="merged.yaml",
            dev_pyats_only=True,
        )

        with patch.object(
            orchestrator, "_discover_test_types", return_value=(True, False)
        ):
            with patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator"
            ) as mock_pyats:
                mock_pyats_instance = MagicMock()
                mock_pyats_instance.run_tests.return_value = pyats_results
                mock_pyats.return_value = mock_pyats_instance

                with patch(
                    "nac_test.combined_orchestrator.CombinedReportGenerator"
                ) as mock_generator:
                    mock_gen_instance = MagicMock()
                    mock_gen_instance.generate_combined_summary.return_value = Path(
                        "/tmp/combined_summary.html"
                    )
                    mock_generator.return_value = mock_gen_instance

                    with patch("typer.echo"), patch("typer.secho"):
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
            merged_data_filename="merged.yaml",
            render_only=True,
        )

        with patch.object(
            orchestrator, "_discover_test_types", return_value=(False, True)
        ):
            with patch(
                "nac_test.combined_orchestrator.RobotOrchestrator"
            ) as mock_robot:
                mock_robot_instance = MagicMock()
                mock_robot_instance.run_tests.return_value = robot_results
                mock_robot.return_value = mock_robot_instance

                with patch(
                    "nac_test.combined_orchestrator.CombinedReportGenerator"
                ) as mock_generator:
                    with patch("typer.echo"):
                        orchestrator.run_tests()

        # Robot orchestrator should be called
        mock_robot.assert_called_once()

        # Dashboard should NOT be generated
        mock_generator.assert_not_called()

    def test_render_only_propagates_robot_exception(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """render_only mode should propagate Robot exceptions immediately."""
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
            merged_data_filename="merged.yaml",
            render_only=True,
        )

        with patch.object(
            orchestrator, "_discover_test_types", return_value=(False, True)
        ):
            with patch(
                "nac_test.combined_orchestrator.RobotOrchestrator"
            ) as mock_robot:
                mock_robot_instance = MagicMock()
                mock_robot_instance.run_tests.side_effect = ValueError("Template error")
                mock_robot.return_value = mock_robot_instance

                with patch("typer.echo"):
                    with pytest.raises(ValueError, match="Template error"):
                        orchestrator.run_tests()

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
            merged_data_filename="merged.yaml",
            render_only=False,  # Not render-only
        )

        with patch.object(
            orchestrator, "_discover_test_types", return_value=(False, True)
        ):
            with patch(
                "nac_test.combined_orchestrator.RobotOrchestrator"
            ) as mock_robot:
                mock_robot_instance = MagicMock()
                mock_robot_instance.run_tests.side_effect = ValueError(
                    "Execution error"
                )
                mock_robot.return_value = mock_robot_instance

                with patch(
                    "nac_test.combined_orchestrator.CombinedReportGenerator"
                ) as mock_generator:
                    mock_gen_instance = MagicMock()
                    mock_gen_instance.generate_combined_summary.return_value = Path(
                        "/tmp/combined_summary.html"
                    )
                    mock_generator.return_value = mock_gen_instance

                    with patch("typer.echo"), patch("typer.style"):
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
        pyats_results: PyATSResults,
        robot_results: TestResults,
    ) -> None:
        """Dashboard generator should receive frameworks dict from combined results."""
        with patch.object(
            orchestrator, "_discover_test_types", return_value=(True, True)
        ):
            with patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator"
            ) as mock_pyats:
                mock_pyats_instance = MagicMock()
                mock_pyats_instance.run_tests.return_value = pyats_results
                mock_pyats.return_value = mock_pyats_instance

                with patch(
                    "nac_test.combined_orchestrator.RobotOrchestrator"
                ) as mock_robot:
                    mock_robot_instance = MagicMock()
                    mock_robot_instance.run_tests.return_value = robot_results
                    mock_robot.return_value = mock_robot_instance

                    with patch(
                        "nac_test.combined_orchestrator.CombinedReportGenerator"
                    ) as mock_generator:
                        mock_gen_instance = MagicMock()
                        mock_gen_instance.generate_combined_summary.return_value = Path(
                            "/tmp/combined_summary.html"
                        )
                        mock_generator.return_value = mock_gen_instance

                        with patch("typer.echo"):
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

        with patch.object(
            orchestrator, "_discover_test_types", return_value=(True, False)
        ):
            with patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator"
            ) as mock_pyats:
                mock_pyats_instance = MagicMock()
                mock_pyats_instance.run_tests.return_value = empty_pyats_results
                mock_pyats.return_value = mock_pyats_instance

                with patch(
                    "nac_test.combined_orchestrator.CombinedReportGenerator"
                ) as mock_generator:
                    mock_gen_instance = MagicMock()
                    mock_gen_instance.generate_combined_summary.return_value = Path(
                        "/tmp/combined_summary.html"
                    )
                    mock_generator.return_value = mock_gen_instance

                    with patch("typer.echo"):
                        orchestrator.run_tests()

        # Dashboard should still be generated
        mock_generator.assert_called_once()
        mock_gen_instance.generate_combined_summary.assert_called_once()


class TestExecutionSummary(TestCombinedOrchestratorFlow):
    """Tests for execution summary printing."""

    def test_print_execution_summary_called_when_not_render_only(
        self,
        orchestrator: CombinedOrchestrator,
        pyats_results: PyATSResults,
    ) -> None:
        """_print_execution_summary should be called when not in render_only mode."""
        with patch.object(
            orchestrator, "_discover_test_types", return_value=(True, False)
        ):
            with patch(
                "nac_test.combined_orchestrator.PyATSOrchestrator"
            ) as mock_pyats:
                mock_pyats_instance = MagicMock()
                mock_pyats_instance.run_tests.return_value = pyats_results
                mock_pyats.return_value = mock_pyats_instance

                with patch(
                    "nac_test.combined_orchestrator.CombinedReportGenerator"
                ) as mock_generator:
                    mock_gen_instance = MagicMock()
                    mock_gen_instance.generate_combined_summary.return_value = Path(
                        "/tmp/combined_summary.html"
                    )
                    mock_generator.return_value = mock_gen_instance

                    with patch.object(
                        orchestrator, "_print_execution_summary"
                    ) as mock_print:
                        with patch("typer.echo"):
                            orchestrator.run_tests()

        # Summary should be printed
        mock_print.assert_called_once()
        call_args = mock_print.call_args
        assert call_args[0][0] is True  # has_pyats
        assert call_args[0][1] is False  # has_robot
        # Third arg is CombinedResults
        results = call_args[0][2]
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
            merged_data_filename="merged.yaml",
            render_only=True,
        )

        with patch.object(
            orchestrator, "_discover_test_types", return_value=(False, True)
        ):
            with patch(
                "nac_test.combined_orchestrator.RobotOrchestrator"
            ) as mock_robot:
                mock_robot_instance = MagicMock()
                mock_robot_instance.run_tests.return_value = robot_results
                mock_robot.return_value = mock_robot_instance

                with patch.object(
                    orchestrator, "_print_execution_summary"
                ) as mock_print:
                    with patch("typer.echo"):
                        orchestrator.run_tests()

        # Summary should NOT be printed in render_only mode
        mock_print.assert_not_called()
