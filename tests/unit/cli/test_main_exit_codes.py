# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tests for main.py exit code handling."""

from unittest.mock import Mock, patch

import pytest

from nac_test.core.constants import (
    EXIT_DATA_ERROR,
    EXIT_ERROR,
    EXIT_FAILURE_CAP,
    EXIT_INTERRUPTED,
    EXIT_INVALID_ARGS,
)
from nac_test.core.types import CombinedResults, ErrorType, TestResults

from .conftest import run_cli_with_temp_dirs


class TestMainExitCodes:
    """Tests for exit code handling in main.py CLI."""

    @pytest.mark.parametrize(
        "results,expected_exit_code",
        [
            (CombinedResults(robot=TestResults(passed=5, failed=0, skipped=0)), 0),
            (CombinedResults(robot=TestResults(passed=2, failed=3, skipped=1)), 3),
            (
                CombinedResults(robot=TestResults.from_error("Framework crashed")),
                EXIT_ERROR,
            ),
            (
                CombinedResults(
                    robot=TestResults.from_error(
                        "Invalid args", ErrorType.INVALID_ROBOT_ARGS
                    )
                ),
                EXIT_DATA_ERROR,
            ),
            (CombinedResults(), EXIT_DATA_ERROR),
            (
                CombinedResults(
                    robot=TestResults.from_error("Framework crashed"),
                    api=TestResults(passed=0, failed=5, skipped=0),
                ),
                EXIT_ERROR,
            ),
            (
                CombinedResults(
                    robot=TestResults.from_error(
                        "Invalid args", error_type=ErrorType.INVALID_ROBOT_ARGS
                    ),
                    api=TestResults.from_error("API execution failed"),
                ),
                EXIT_DATA_ERROR,
            ),
            (
                CombinedResults(robot=TestResults(passed=0, failed=300, skipped=0)),
                EXIT_FAILURE_CAP,
            ),
        ],
        ids=[
            "all_tests_passed",
            "exit_code_equals_failure_count",
            "execution_error_returns_255",
            "robot_invalid_args_returns_252",
            "empty_results_returns_252",
            "error_prioritized_over_failures",
            "robot_invalid_args_prioritized_over_other_errors",
            "failure_count_capped_at_250",
        ],
    )
    @patch("nac_test.cli.main.CombinedOrchestrator")
    def test_exit_codes(
        self,
        mock_orchestrator_cls: Mock,
        results: CombinedResults,
        expected_exit_code: int,
    ) -> None:
        """Test exit code handling for various orchestrator results."""
        mock_orchestrator = Mock()
        mock_orchestrator.run_tests.return_value = results
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = run_cli_with_temp_dirs()

        assert result.exit_code == expected_exit_code

    def test_invalid_flag_combination_exits_2(self) -> None:
        """Test that invalid flag combinations exit with code 2."""
        result = run_cli_with_temp_dirs(["--pyats", "--robot"])

        assert result.exit_code == EXIT_INVALID_ARGS

    @patch("nac_test.cli.main.CombinedOrchestrator")
    def test_keyboard_interrupt_returns_253(self, mock_orchestrator_cls: Mock) -> None:
        """Test exit code 253 when execution is interrupted by Ctrl+C."""
        mock_orchestrator = Mock()
        mock_orchestrator.run_tests.side_effect = KeyboardInterrupt()
        mock_orchestrator_cls.return_value = mock_orchestrator

        result = run_cli_with_temp_dirs()

        assert result.exit_code == EXIT_INTERRUPTED
        assert "interrupted" in result.output.lower()
