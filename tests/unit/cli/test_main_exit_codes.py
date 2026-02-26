# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tests for main.py exit code handling."""

from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from typer.testing import CliRunner, Result

from nac_test.cli.main import app
from nac_test.core.constants import (
    EXIT_DATA_ERROR,
    EXIT_ERROR,
    EXIT_FAILURE_CAP,
    EXIT_INTERRUPTED,
    EXIT_INVALID_ARGS,
)
from nac_test.core.types import CombinedResults, ErrorType, TestResults


class TestMainExitCodes:
    """Tests for exit code handling in main.py CLI."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()

    def _run_cli_with_temp_dirs(
        self, additional_args: list[str] | None = None
    ) -> Result:
        """Helper method to run CLI with temporary directories."""
        args = additional_args or []
        with (
            TemporaryDirectory() as temp_data,
            TemporaryDirectory() as temp_templates,
            TemporaryDirectory() as temp_output,
        ):
            return self.runner.invoke(
                app, ["-d", temp_data, "-t", temp_templates, "-o", temp_output] + args
            )

    @patch("nac_test.cli.main.CombinedOrchestrator")
    def test_exit_code_0_all_tests_passed(self, mock_orchestrator_cls: Mock) -> None:
        """Test exit code 0 when all tests pass."""
        # Mock orchestrator with successful results
        mock_orchestrator = Mock()
        mock_stats = CombinedResults(robot=TestResults(passed=5, failed=0, skipped=0))
        mock_orchestrator.run_tests.return_value = mock_stats
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = self._run_cli_with_temp_dirs()

        assert result.exit_code == 0

    @patch("nac_test.cli.main.CombinedOrchestrator")
    def test_exit_code_equals_failure_count(self, mock_orchestrator_cls: Mock) -> None:
        """Test exit code equals number of test failures."""
        # Mock orchestrator with 3 test failures
        mock_orchestrator = Mock()
        mock_stats = CombinedResults(robot=TestResults(passed=2, failed=3, skipped=1))
        mock_orchestrator.run_tests.return_value = mock_stats
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = self._run_cli_with_temp_dirs()

        assert result.exit_code == 3

    @patch("nac_test.cli.main.CombinedOrchestrator")
    def test_exit_code_255_for_execution_errors(
        self, mock_orchestrator_cls: Mock
    ) -> None:
        """Test exit code 255 when execution errors occur."""
        # Mock orchestrator with execution error
        mock_orchestrator = Mock()
        mock_stats = CombinedResults(robot=TestResults.from_error("Framework crashed"))
        mock_orchestrator.run_tests.return_value = mock_stats
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = self._run_cli_with_temp_dirs()

        assert result.exit_code == EXIT_ERROR

    @patch("nac_test.cli.main.CombinedOrchestrator")
    def test_exit_code_252_for_robot_invalid_args(
        self, mock_orchestrator_cls: Mock
    ) -> None:
        """Test exit code 252 for Robot Framework invalid arguments."""
        # Mock orchestrator with Robot invalid args
        mock_orchestrator = Mock()
        mock_stats = CombinedResults(
            robot=TestResults.from_error(
                "Invalid Robot Framework arguments passed to nac-test",
                ErrorType.INVALID_ROBOT_ARGS,
            )
        )
        mock_orchestrator.run_tests.return_value = mock_stats
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = self._run_cli_with_temp_dirs()

        assert result.exit_code == EXIT_DATA_ERROR

    @patch("nac_test.cli.main.CombinedOrchestrator")
    def test_exit_code_252_for_empty_results(self, mock_orchestrator_cls: Mock) -> None:
        """Test exit code 252 when no tests are executed."""
        # Mock orchestrator with empty results
        mock_orchestrator = Mock()
        mock_stats = CombinedResults()  # Empty results
        mock_orchestrator.run_tests.return_value = mock_stats
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = self._run_cli_with_temp_dirs()

        assert result.exit_code == EXIT_DATA_ERROR

    @patch("nac_test.cli.main.CombinedOrchestrator")
    def test_priority_errors_over_failures(self, mock_orchestrator_cls: Mock) -> None:
        """Test that errors (255) are prioritized over failures (1-250)."""
        # Mock orchestrator with both errors and failures
        mock_orchestrator = Mock()
        mock_stats = CombinedResults(
            robot=TestResults.from_error("Framework crashed"),
            api=TestResults(passed=0, failed=5, skipped=0),  # 5 failures
        )
        mock_orchestrator.run_tests.return_value = mock_stats
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = self._run_cli_with_temp_dirs()

        # Should return 255 (error) not 5 (failures)
        assert result.exit_code == EXIT_ERROR

    @patch("nac_test.cli.main.CombinedOrchestrator")
    def test_priority_robot_invalid_args_over_other_errors(
        self, mock_orchestrator_cls: Mock
    ) -> None:
        """Test that Robot invalid args (252) are prioritized over other errors (255)."""
        # Mock orchestrator with Robot invalid args and other error
        mock_orchestrator = Mock()
        mock_stats = CombinedResults(
            robot=TestResults.from_error(
                "Invalid arguments passed to nac-test",
                error_type=ErrorType.INVALID_ROBOT_ARGS,
            ),
            api=TestResults.from_error("API execution failed"),  # Generic error
        )
        mock_orchestrator.run_tests.return_value = mock_stats
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = self._run_cli_with_temp_dirs()

        # Should return 252 (Robot invalid args) not 255 (generic error)
        assert result.exit_code == EXIT_DATA_ERROR

    @patch("nac_test.cli.main.CombinedOrchestrator")
    def test_failure_count_capped_at_250(self, mock_orchestrator_cls: Mock) -> None:
        """Test that failure count is capped at 250."""
        # Mock orchestrator with 300 failures
        mock_orchestrator = Mock()
        mock_stats = CombinedResults(robot=TestResults(passed=0, failed=300, skipped=0))
        mock_orchestrator.run_tests.return_value = mock_stats
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = self._run_cli_with_temp_dirs()

        # Should be capped at EXIT_FAILURE_CAP
        assert result.exit_code == EXIT_FAILURE_CAP

    def test_invalid_flag_combination_exits_2(self) -> None:
        """Test that invalid flag combinations exit with code 2."""
        result = self._run_cli_with_temp_dirs(["--pyats", "--robot"])

        assert result.exit_code == EXIT_INVALID_ARGS

    @patch("nac_test.cli.main.CombinedOrchestrator")
    def test_exit_code_253_for_keyboard_interrupt(
        self, mock_orchestrator_cls: Mock
    ) -> None:
        """Test exit code 253 when execution is interrupted by Ctrl+C."""
        mock_orchestrator = Mock()
        mock_orchestrator.run_tests.side_effect = KeyboardInterrupt()
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = self._run_cli_with_temp_dirs()

        assert result.exit_code == EXIT_INTERRUPTED
        assert "interrupted" in result.output.lower()
