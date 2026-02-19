# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tests for core types: TestResults, ExecutionState, PyATSResults, CombinedResults.

Focus: Business logic edge cases, zero-division guards, exit code priority,
state consistency. Basic dataclass attribute access is NOT tested as Python's
dataclass handles it automatically.
"""

import pytest

from nac_test.core.types import (
    CombinedResults,
    ExecutionState,
    PyATSResults,
    TestResults,
)


class TestTestResultsFactoryMethods:
    """Tests for TestResults factory methods."""

    def test_empty_creates_empty_state(self) -> None:
        """empty() creates results with EMPTY state and zero counts."""
        result = TestResults.empty()

        assert result.state == ExecutionState.EMPTY
        assert result.total == 0
        assert result.reason is None

    def test_not_run_creates_skipped_state(self) -> None:
        """not_run() creates results with SKIPPED state."""
        result = TestResults.not_run()

        assert result.state == ExecutionState.SKIPPED
        assert result.total == 0

    def test_not_run_with_reason(self) -> None:
        """not_run() stores reason."""
        result = TestResults.not_run("render-only mode")

        assert result.state == ExecutionState.SKIPPED
        assert result.reason == "render-only mode"

    def test_from_error_creates_error_state(self) -> None:
        """from_error() creates results with ERROR state and message."""
        result = TestResults.from_error("Pabot execution failed")

        assert result.state == ExecutionState.ERROR
        assert result.reason == "Pabot execution failed"
        assert result.total == 0

    def test_default_constructor_creates_success_state(self) -> None:
        """Default constructor creates SUCCESS state."""
        result = TestResults()

        assert result.state == ExecutionState.SUCCESS
        assert result.total == 0


class TestTestResultsTotal:
    """Tests for total property computation."""

    def test_total_sums_all_counts(self) -> None:
        """Total includes passed, failed, skipped, and other."""
        result = TestResults(passed=80, failed=5, skipped=10, other=5)
        assert result.total == 100

    def test_total_with_only_passed(self) -> None:
        """Total works with only passed tests."""
        result = TestResults(passed=10)
        assert result.total == 10

    def test_total_is_zero_for_empty(self) -> None:
        """Total is zero for empty results."""
        result = TestResults.empty()
        assert result.total == 0


class TestTestResultsSuccessRate:
    """Tests for success_rate calculation with edge cases."""

    def test_success_rate_all_passed(self) -> None:
        """100% success rate when all tests pass."""
        result = TestResults(passed=10, failed=0, skipped=0)
        assert result.success_rate == 100.0

    def test_success_rate_some_failed(self) -> None:
        """Correct success rate calculation with failures."""
        result = TestResults(passed=8, failed=2, skipped=0)
        assert result.success_rate == 80.0

    def test_success_rate_excludes_skipped_from_denominator(self) -> None:
        """Success rate excludes skipped tests from calculation."""
        # 8 passed out of 9 non-skipped = 88.89%
        result = TestResults(passed=8, failed=1, skipped=1)
        assert result.success_rate == pytest.approx(88.888, rel=0.01)

    def test_success_rate_zero_division_guard_no_tests(self) -> None:
        """Zero success rate when no tests executed (guards division by zero)."""
        result = TestResults.empty()
        assert result.success_rate == 0.0

    def test_success_rate_zero_division_guard_all_skipped(self) -> None:
        """Zero success rate when all tests skipped (guards division by zero)."""
        result = TestResults(passed=0, failed=0, skipped=5)
        assert result.success_rate == 0.0

    def test_success_rate_includes_other_in_denominator(self) -> None:
        """Success rate includes 'other' tests in denominator."""
        # 80 passed / (100 - 10 skipped) = 80/90 = 88.89%
        result = TestResults(passed=80, failed=5, skipped=10, other=5)
        assert result.success_rate == pytest.approx(88.888, rel=0.01)


class TestTestResultsStateChecks:
    """Tests for state-checking properties."""

    def test_has_failures_true_when_failed_positive(self) -> None:
        """has_failures is True when failed > 0."""
        result = TestResults(passed=9, failed=1)
        assert result.has_failures is True

    def test_has_failures_false_when_failed_zero(self) -> None:
        """has_failures is False when failed == 0."""
        result = TestResults(passed=10, failed=0)
        assert result.has_failures is False

    def test_has_error_reflects_error_state(self) -> None:
        """has_error is True only for ERROR state."""
        assert TestResults.from_error("crash").has_error is True
        assert TestResults.empty().has_error is False
        assert TestResults(passed=10).has_error is False

    def test_is_empty_reflects_total_zero(self) -> None:
        """is_empty is True when total == 0."""
        assert TestResults.empty().is_empty is True
        assert TestResults(passed=1).is_empty is False

    def test_was_not_run_reflects_skipped_state(self) -> None:
        """was_not_run is True only for SKIPPED state."""
        assert TestResults.not_run("reason").was_not_run is True
        assert TestResults.empty().was_not_run is False
        assert TestResults.from_error("crash").was_not_run is False


class TestTestResultsStringRepresentation:
    """Tests for __str__ method."""

    def test_str_format_basic(self) -> None:
        """String format is total/passed/failed/skipped."""
        result = TestResults(passed=8, failed=1, skipped=1)
        assert str(result) == "10/8/1/1"

    def test_str_includes_other_when_nonzero(self) -> None:
        """String includes other count when non-zero."""
        result = TestResults(passed=80, failed=5, skipped=10, other=5)
        assert str(result) == "100/80/5/10/5"

    def test_str_omits_other_when_zero(self) -> None:
        """String omits other count when zero."""
        result = TestResults(passed=10, failed=0, skipped=0, other=0)
        assert str(result) == "10/10/0/0"


class TestExecutionStateDistinction:
    """Tests verifying correct distinction between execution states."""

    def test_empty_vs_error_same_counts_different_state(self) -> None:
        """EMPTY and ERROR states are distinguishable despite same counts."""
        empty = TestResults.empty()
        error = TestResults.from_error("something broke")

        # Both have zero counts
        assert empty.total == error.total == 0

        # But different states and properties
        assert empty.state == ExecutionState.EMPTY
        assert error.state == ExecutionState.ERROR
        assert empty.is_error is False
        assert error.is_error is True

    def test_empty_vs_skipped_same_counts_different_state(self) -> None:
        """EMPTY and SKIPPED states are distinguishable despite same counts."""
        empty = TestResults.empty()
        skipped = TestResults.not_run("render-only")

        # Both have zero counts
        assert empty.total == skipped.total == 0

        # But different states and properties
        assert empty.state == ExecutionState.EMPTY
        assert skipped.state == ExecutionState.SKIPPED
        assert empty.was_not_run is False
        assert skipped.was_not_run is True

    def test_success_vs_empty_both_zero_counts(self) -> None:
        """SUCCESS with zero tests and EMPTY are distinguishable."""
        success_zero = TestResults()  # SUCCESS state with zero counts
        empty = TestResults.empty()

        assert success_zero.total == empty.total == 0
        assert success_zero.state == ExecutionState.SUCCESS
        assert empty.state == ExecutionState.EMPTY


class TestPyATSResultsStringRepresentation:
    """Tests for PyATSResults __str__ method."""

    def test_str_empty(self) -> None:
        """String representation when empty."""
        result = PyATSResults()
        assert str(result) == "PyATSResults(empty)"

    def test_str_api_only(self) -> None:
        """String representation with API only."""
        result = PyATSResults(api=TestResults(passed=4, failed=1, skipped=0))
        assert str(result) == "PyATSResults(API: 5/4/1/0)"

    def test_str_both(self) -> None:
        """String representation with both API and D2D."""
        result = PyATSResults(
            api=TestResults(passed=5, failed=0, skipped=0),
            d2d=TestResults(passed=2, failed=1, skipped=0),
        )
        assert str(result) == "PyATSResults(API: 5/5/0/0, D2D: 3/2/1/0)"


class TestCombinedResultsAggregation:
    """Tests for CombinedResults aggregation logic."""

    def test_total_aggregates_all_frameworks(self) -> None:
        """total property sums across all frameworks."""
        result = CombinedResults(
            api=TestResults(passed=5),
            d2d=TestResults(passed=3),
            robot=TestResults(passed=10),
        )
        assert result.total == 18

    def test_aggregation_ignores_none_results(self) -> None:
        """Aggregation properties ignore None results."""
        result = CombinedResults(
            api=TestResults(passed=5, failed=1),
            d2d=None,
            robot=TestResults(passed=10, failed=2),
        )
        assert result.total == 18
        assert result.passed == 15
        assert result.failed == 3

    def test_errors_collects_all_reasons(self) -> None:
        """errors property collects reasons from all frameworks."""
        result = CombinedResults(
            api=TestResults.from_error("API error"),
            d2d=TestResults(passed=5),  # no error
            robot=TestResults.from_error("Robot error"),
        )
        assert result.errors == ["API error", "Robot error"]

    def test_errors_includes_not_run_reason(self) -> None:
        """errors includes reason from not_run() results."""
        result = CombinedResults(
            api=TestResults(passed=5),
            robot=TestResults.not_run("render-only mode"),
        )
        assert result.errors == ["render-only mode"]


class TestCombinedResultsSuccessRate:
    """Tests for CombinedResults success_rate with edge cases."""

    def test_success_rate_combined_calculation(self) -> None:
        """success_rate calculated correctly across all frameworks."""
        result = CombinedResults(
            api=TestResults(passed=4, failed=1),
            robot=TestResults(passed=4, failed=1),
        )
        assert result.success_rate == 80.0

    def test_success_rate_zero_division_guard_empty(self) -> None:
        """success_rate is 0 when no results (guards division by zero)."""
        result = CombinedResults()
        assert result.success_rate == 0.0

    def test_success_rate_zero_division_guard_all_skipped(self) -> None:
        """success_rate is 0 when all tests skipped across frameworks."""
        result = CombinedResults(
            api=TestResults(passed=0, failed=0, skipped=5),
            robot=TestResults(passed=0, failed=0, skipped=3),
        )
        assert result.success_rate == 0.0


class TestCombinedResultsExitCode:
    """Tests for CombinedResults exit_code with priority and boundaries."""

    def test_exit_code_zero_all_passed(self) -> None:
        """Exit code 0 when all tests pass across frameworks."""
        result = CombinedResults(
            api=TestResults(passed=5),
            robot=TestResults(passed=10),
        )
        assert result.exit_code == 0

    def test_exit_code_sums_failures_across_frameworks(self) -> None:
        """Exit code equals total failures across all frameworks."""
        result = CombinedResults(
            api=TestResults(passed=4, failed=1),
            robot=TestResults(passed=8, failed=2),
        )
        assert result.exit_code == 3

    def test_exit_code_capped_at_250(self) -> None:
        """Exit code is capped at 250 even with many failures across frameworks."""
        result = CombinedResults(
            api=TestResults(passed=0, failed=150),
            robot=TestResults(passed=0, failed=150),
        )
        assert result.exit_code == 250

    def test_exit_code_error_priority_over_failures(self) -> None:
        """Exit code 255 when any framework has error, regardless of failures."""
        result = CombinedResults(
            api=TestResults(passed=0, failed=100),
            robot=TestResults.from_error("crash"),
        )
        assert result.exit_code == 255

    def test_exit_code_252_for_empty(self) -> None:
        """Exit code 252 when no results across any framework."""
        result = CombinedResults()
        assert result.exit_code == 252

    def test_was_not_run_true_when_all_skipped(self) -> None:
        """was_not_run is True when all frameworks were intentionally skipped."""
        result = CombinedResults(
            robot=TestResults.not_run("render-only"),
            api=TestResults.not_run("render-only"),
        )
        assert result.was_not_run is True
        assert result.exit_code == 0

    def test_was_not_run_false_when_mixed_states(self) -> None:
        """was_not_run is False when frameworks have mixed states."""
        result = CombinedResults(
            robot=TestResults.not_run("render-only"),
            api=TestResults(passed=5, failed=0),
        )
        assert result.was_not_run is False

    def test_was_not_run_false_when_empty(self) -> None:
        """was_not_run is False when no frameworks are present."""
        result = CombinedResults()
        assert result.was_not_run is False

    def test_reasons_property_collects_all_reasons(self) -> None:
        """reasons property collects all reason messages from frameworks."""
        result = CombinedResults(
            robot=TestResults.from_error("Robot framework crashed"),
            api=TestResults.not_run("Skipped for testing"),
            d2d=TestResults(passed=5, failed=0),  # No reason
        )
        assert len(result.reasons) == 2
        assert "Robot framework crashed" in result.reasons
        assert "Skipped for testing" in result.reasons

    def test_exit_code_253_for_robot_interrupted_combined(self) -> None:
        """Exit code 253 for Robot Framework execution interrupted in combined results."""
        result = CombinedResults(
            robot=TestResults.from_error("Robot Framework execution was interrupted")
        )
        assert result.exit_code == 253

    def test_exit_code_priority_interrupted_over_other_errors(self) -> None:
        """Exit code 253 (interrupted) is prioritized over generic errors (255)."""
        result = CombinedResults(
            robot=TestResults.from_error("Robot Framework execution was interrupted"),
            api=TestResults.from_error("API execution failed"),  # Generic error
        )
        assert result.exit_code == 253


class TestCombinedResultsStateChecks:
    """Tests for CombinedResults state-checking properties."""

    def test_has_failures_true_when_any_framework_has_failures(self) -> None:
        """has_failures is True when any framework has failures."""
        result = CombinedResults(
            api=TestResults(passed=5),
            robot=TestResults(passed=9, failed=1),
        )
        assert result.has_failures is True

    def test_has_failures_false_when_no_failures(self) -> None:
        """has_failures is False when no failures in any framework."""
        result = CombinedResults(
            api=TestResults(passed=5),
            robot=TestResults(passed=10),
        )
        assert result.has_failures is False

    def test_has_errors_true_when_any_framework_has_error(self) -> None:
        """has_errors is True when any framework has error state."""
        result = CombinedResults(
            api=TestResults(passed=5),
            robot=TestResults.from_error("crash"),
        )
        assert result.has_errors is True

    def test_has_errors_false_when_no_errors(self) -> None:
        """has_errors is False when no errors in any framework."""
        result = CombinedResults(
            api=TestResults(passed=5),
            robot=TestResults(passed=10),
        )
        assert result.has_errors is False

    def test_is_empty_true_when_all_empty(self) -> None:
        """is_empty is True when total is 0 across all frameworks."""
        result = CombinedResults(
            api=TestResults.empty(),
            robot=TestResults.empty(),
        )
        assert result.is_empty is True

    def test_is_empty_false_when_any_has_tests(self) -> None:
        """is_empty is False when any framework has tests."""
        result = CombinedResults(
            api=TestResults.empty(),
            robot=TestResults(passed=1),
        )
        assert result.is_empty is False


class TestCombinedResultsStringRepresentation:
    """Tests for CombinedResults __str__ method."""

    def test_str_empty(self) -> None:
        """String representation when empty."""
        result = CombinedResults()
        assert str(result) == "CombinedResults(empty)"

    def test_str_all_present(self) -> None:
        """String representation with all frameworks."""
        result = CombinedResults(
            api=TestResults(passed=5, failed=0, skipped=0),
            d2d=TestResults(passed=2, failed=1, skipped=0),
            robot=TestResults(passed=8, failed=1, skipped=1),
        )
        expected = "CombinedResults(API: 5/5/0/0, D2D: 3/2/1/0, Robot: 10/8/1/1)"
        assert str(result) == expected
