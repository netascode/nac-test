# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tests for core types: TestResults, ExecutionState, PyATSResults, CombinedResults."""

import pytest

from nac_test.core.types import (
    CombinedResults,
    ExecutionState,
    PyATSResults,
    TestResults,
)


class TestExecutionState:
    """Tests for ExecutionState enum."""

    def test_all_states_exist(self) -> None:
        """Verify all expected states are defined."""
        assert ExecutionState.SUCCESS
        assert ExecutionState.EMPTY
        assert ExecutionState.SKIPPED
        assert ExecutionState.ERROR

    def test_states_are_distinct(self) -> None:
        """Verify each state has a unique value."""
        states = [s.value for s in ExecutionState]
        assert len(states) == len(set(states))


class TestTestResultsFactoryMethods:
    """Tests for TestResults factory methods."""

    def test_empty_creates_empty_state(self) -> None:
        """empty() creates results with EMPTY state and zero counts."""
        result = TestResults.empty()

        assert result.state == ExecutionState.EMPTY
        assert result.total == 0
        assert result.passed == 0
        assert result.failed == 0
        assert result.skipped == 0
        assert result.reason is None

    def test_not_run_creates_skipped_state(self) -> None:
        """not_run() creates results with SKIPPED state."""
        result = TestResults.not_run()

        assert result.state == ExecutionState.SKIPPED
        assert result.total == 0
        assert result.reason is None

    def test_not_run_with_reason(self) -> None:
        """not_run() stores reason in error field."""
        result = TestResults.not_run("render-only mode")

        assert result.state == ExecutionState.SKIPPED
        assert result.reason == "render-only mode"

    def test_from_error_creates_error_state(self) -> None:
        """from_error() creates results with ERROR state and message."""
        result = TestResults.from_error("Pabot execution failed")

        assert result.state == ExecutionState.ERROR
        assert result.reason == "Pabot execution failed"
        assert result.total == 0
        assert result.passed == 0
        assert result.failed == 0
        assert result.skipped == 0

    def test_constructor_calculates_total(self) -> None:
        """Constructor auto-calculates total from counts."""
        result = TestResults(passed=8, failed=1, skipped=1)

        assert result.state == ExecutionState.SUCCESS
        assert result.total == 10
        assert result.passed == 8
        assert result.failed == 1
        assert result.skipped == 1
        assert result.other == 0
        assert result.reason is None

    def test_constructor_with_other(self) -> None:
        """Constructor includes 'other' status tests in total."""
        result = TestResults(passed=80, failed=5, skipped=10, other=5)

        assert result.total == 100
        assert result.passed == 80
        assert result.failed == 5
        assert result.skipped == 10
        assert result.other == 5

    def test_default_constructor_creates_success_state(self) -> None:
        """Default constructor creates SUCCESS state."""
        result = TestResults()

        assert result.state == ExecutionState.SUCCESS
        assert result.total == 0


class TestTestResultsProperties:
    """Tests for TestResults computed properties."""

    def test_success_rate_all_passed(self) -> None:
        """100% success rate when all tests pass."""
        result = TestResults(passed=10, failed=0, skipped=0)
        assert result.success_rate == 100.0

    def test_success_rate_some_failed(self) -> None:
        """Correct success rate calculation with failures."""
        result = TestResults(passed=8, failed=2, skipped=0)
        assert result.success_rate == 80.0

    def test_success_rate_excludes_skipped(self) -> None:
        """Success rate excludes skipped tests from calculation."""
        # 8 passed out of 9 non-skipped = 88.89%
        result = TestResults(passed=8, failed=1, skipped=1)
        assert result.success_rate == pytest.approx(88.888, rel=0.01)

    def test_success_rate_zero_when_no_tests(self) -> None:
        """Zero success rate when no tests executed."""
        result = TestResults.empty()
        assert result.success_rate == 0.0

    def test_success_rate_zero_when_all_skipped(self) -> None:
        """Zero success rate when all tests are skipped."""
        result = TestResults(passed=0, failed=0, skipped=5)
        assert result.success_rate == 0.0

    def test_success_rate_with_other_statuses(self) -> None:
        """Success rate calculation includes 'other' tests in denominator."""
        result = TestResults(passed=80, failed=5, skipped=10, other=5)
        assert result.success_rate == pytest.approx(88.888, rel=0.01)

    def test_has_failures_true(self) -> None:
        """has_failures is True when failed > 0."""
        result = TestResults(passed=9, failed=1, skipped=0)
        assert result.has_failures is True

    def test_has_failures_false(self) -> None:
        """has_failures is False when failed == 0."""
        result = TestResults(passed=10, failed=0, skipped=0)
        assert result.has_failures is False

    def test_has_error_true(self) -> None:
        """has_error is True when error is set."""
        result = TestResults.from_error("Something went wrong")
        assert result.has_error is True

    def test_has_error_false(self) -> None:
        """has_error is False when no error."""
        result = TestResults(passed=10)
        assert result.has_error is False

    def test_is_empty_true(self) -> None:
        """is_empty is True when total == 0."""
        result = TestResults.empty()
        assert result.is_empty is True

    def test_is_empty_false(self) -> None:
        """is_empty is False when total > 0."""
        result = TestResults(passed=1)
        assert result.is_empty is False

    def test_is_error_true(self) -> None:
        """is_error is True when state is ERROR."""
        result = TestResults.from_error("crash")
        assert result.is_error is True

    def test_is_error_false_for_empty(self) -> None:
        """is_error is False for EMPTY state."""
        result = TestResults.empty()
        assert result.is_error is False

    def test_is_error_false_for_success(self) -> None:
        """is_error is False for SUCCESS state."""
        result = TestResults(passed=10)
        assert result.is_error is False

    def test_was_not_run_true(self) -> None:
        """was_not_run is True when state is SKIPPED."""
        result = TestResults.not_run("render-only")
        assert result.was_not_run is True

    def test_was_not_run_false_for_empty(self) -> None:
        """was_not_run is False for EMPTY state."""
        result = TestResults.empty()
        assert result.was_not_run is False

    def test_was_not_run_false_for_error(self) -> None:
        """was_not_run is False for ERROR state."""
        result = TestResults.from_error("crash")
        assert result.was_not_run is False


class TestTestResultsExitCode:
    """Tests for exit_code calculation."""

    def test_exit_code_zero_all_passed(self) -> None:
        """Exit code 0 when all tests pass."""
        result = TestResults(passed=10)
        assert result.exit_code == 0

    def test_exit_code_equals_failed_count(self) -> None:
        """Exit code equals number of failures."""
        result = TestResults(passed=7, failed=3)
        assert result.exit_code == 3

    def test_exit_code_capped_at_250(self) -> None:
        """Exit code is capped at 250 for many failures."""
        result = TestResults(passed=0, failed=300)
        assert result.exit_code == 250

    def test_exit_code_255_for_error(self) -> None:
        """Exit code 255 when execution error occurred."""
        result = TestResults.from_error("crash")
        assert result.exit_code == 255

    def test_exit_code_error_takes_precedence(self) -> None:
        """Error exit code takes precedence over failure count."""
        result = TestResults(
            passed=5,
            failed=5,
            reason="also crashed",
            state=ExecutionState.ERROR,
        )
        assert result.exit_code == 255


class TestTestResultsStringRepresentation:
    """Tests for __str__ method."""

    def test_str_format(self) -> None:
        """String format is total/passed/failed/skipped."""
        result = TestResults(passed=8, failed=1, skipped=1)
        assert str(result) == "10/8/1/1"

    def test_str_empty(self) -> None:
        """String for empty results."""
        result = TestResults.empty()
        assert str(result) == "0/0/0/0"

    def test_str_with_other(self) -> None:
        """String includes other count when non-zero."""
        result = TestResults(passed=80, failed=5, skipped=10, other=5)
        assert str(result) == "100/80/5/10/5"


class TestPyATSResults:
    """Tests for PyATSResults container."""

    def test_empty(self) -> None:
        """Empty PyATSResults."""
        result = PyATSResults()
        assert result.api is None
        assert result.d2d is None

    def test_with_api_only(self) -> None:
        """PyATSResults with only API results."""
        api = TestResults(passed=5)
        result = PyATSResults(api=api)
        assert result.api is api
        assert result.d2d is None

    def test_with_d2d_only(self) -> None:
        """PyATSResults with only D2D results."""
        d2d = TestResults(passed=3)
        result = PyATSResults(d2d=d2d)
        assert result.api is None
        assert result.d2d is d2d

    def test_with_both(self) -> None:
        """PyATSResults with both API and D2D."""
        api = TestResults(passed=5)
        d2d = TestResults(passed=3)
        result = PyATSResults(api=api, d2d=d2d)
        assert result.api is api
        assert result.d2d is d2d

    def test_str_empty(self) -> None:
        """String representation when empty."""
        result = PyATSResults()
        assert str(result) == "PyATSResults(empty)"

    def test_str_api_only(self) -> None:
        """String representation with API only."""
        result = PyATSResults(api=TestResults(passed=4, failed=1, skipped=0))
        assert str(result) == "PyATSResults(API: 5/4/1/0)"

    def test_str_both(self) -> None:
        """String representation with both."""
        result = PyATSResults(
            api=TestResults(passed=5, failed=0, skipped=0),
            d2d=TestResults(passed=2, failed=1, skipped=0),
        )
        assert str(result) == "PyATSResults(API: 5/5/0/0, D2D: 3/2/1/0)"


class TestCombinedResults:
    """Tests for CombinedResults aggregation."""

    def test_empty(self) -> None:
        """Empty CombinedResults."""
        result = CombinedResults()
        assert result.api is None
        assert result.d2d is None
        assert result.robot is None

    def test_total_aggregates_all(self) -> None:
        """total property sums across all frameworks."""
        result = CombinedResults(
            api=TestResults(passed=5),
            d2d=TestResults(passed=3),
            robot=TestResults(passed=10),
        )
        assert result.total == 18

    def test_total_ignores_none(self) -> None:
        """total property ignores None results."""
        result = CombinedResults(
            api=TestResults(passed=5),
            d2d=None,
            robot=TestResults(passed=10),
        )
        assert result.total == 15

    def test_passed_aggregates_all(self) -> None:
        """passed property sums across all frameworks."""
        result = CombinedResults(
            api=TestResults(passed=4, failed=1),
            robot=TestResults(passed=8, failed=2),
        )
        assert result.passed == 12

    def test_failed_aggregates_all(self) -> None:
        """failed property sums across all frameworks."""
        result = CombinedResults(
            api=TestResults(passed=4, failed=1),
            robot=TestResults(passed=8, failed=2),
        )
        assert result.failed == 3

    def test_skipped_aggregates_all(self) -> None:
        """skipped property sums across all frameworks."""
        result = CombinedResults(
            api=TestResults(passed=4, failed=0, skipped=1),
            robot=TestResults(passed=8, failed=0, skipped=2),
        )
        assert result.skipped == 3

    def test_other_aggregates_all(self) -> None:
        """other property sums across all frameworks."""
        result = CombinedResults(
            api=TestResults(passed=4, failed=1, skipped=2, other=3),
            robot=TestResults(passed=3, failed=1, skipped=0, other=1),
        )
        assert result.other == 4

    def test_errors_collects_from_all(self) -> None:
        """errors property collects errors from all frameworks."""
        result = CombinedResults(
            api=TestResults.from_error("API error"),
            d2d=TestResults(passed=5),  # no error
            robot=TestResults.from_error("Robot error"),
        )
        assert result.errors == ["API error", "Robot error"]

    def test_errors_empty_when_no_errors(self) -> None:
        """errors property returns empty list when no errors."""
        result = CombinedResults(
            api=TestResults(passed=5),
            robot=TestResults(passed=10),
        )
        assert result.errors == []

    def test_errors_includes_not_run_reason(self) -> None:
        """errors includes reason from not_run() results."""
        result = CombinedResults(
            api=TestResults(passed=5),
            robot=TestResults.not_run("render-only mode"),
        )
        assert result.errors == ["render-only mode"]

    def test_success_rate_combined(self) -> None:
        """success_rate calculated across all frameworks."""
        result = CombinedResults(
            api=TestResults(passed=4, failed=1),
            robot=TestResults(passed=4, failed=1),
        )
        assert result.success_rate == 80.0

    def test_success_rate_zero_when_empty(self) -> None:
        """success_rate is 0 when no results."""
        result = CombinedResults()
        assert result.success_rate == 0.0

    def test_has_failures_true(self) -> None:
        """has_failures is True when any framework has failures."""
        result = CombinedResults(
            api=TestResults(passed=5),
            robot=TestResults(passed=9, failed=1),
        )
        assert result.has_failures is True

    def test_has_failures_false(self) -> None:
        """has_failures is False when no failures."""
        result = CombinedResults(
            api=TestResults(passed=5),
            robot=TestResults(passed=10),
        )
        assert result.has_failures is False

    def test_has_errors_true(self) -> None:
        """has_errors is True when any framework has error."""
        result = CombinedResults(
            api=TestResults(passed=5),
            robot=TestResults.from_error("crash"),
        )
        assert result.has_errors is True

    def test_has_errors_false(self) -> None:
        """has_errors is False when no errors."""
        result = CombinedResults(
            api=TestResults(passed=5),
            robot=TestResults(passed=10),
        )
        assert result.has_errors is False

    def test_is_empty_true(self) -> None:
        """is_empty is True when total is 0."""
        result = CombinedResults(
            api=TestResults.empty(),
            robot=TestResults.empty(),
        )
        assert result.is_empty is True

    def test_is_empty_false(self) -> None:
        """is_empty is False when any tests ran."""
        result = CombinedResults(
            api=TestResults.empty(),
            robot=TestResults(passed=1),
        )
        assert result.is_empty is False

    def test_exit_code_zero_all_passed(self) -> None:
        """Exit code 0 when all pass."""
        result = CombinedResults(
            api=TestResults(passed=5),
            robot=TestResults(passed=10),
        )
        assert result.exit_code == 0

    def test_exit_code_equals_total_failures(self) -> None:
        """Exit code equals total failures across frameworks."""
        result = CombinedResults(
            api=TestResults(passed=4, failed=1),
            robot=TestResults(passed=8, failed=2),
        )
        assert result.exit_code == 3

    def test_exit_code_255_for_errors(self) -> None:
        """Exit code 255 when any framework has error."""
        result = CombinedResults(
            api=TestResults(passed=5),
            robot=TestResults.from_error("crash"),
        )
        assert result.exit_code == 255

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


class TestExecutionStateDistinction:
    """Tests verifying correct distinction between execution states."""

    def test_empty_vs_error_distinction(self) -> None:
        """EMPTY and ERROR states are distinguishable."""
        empty = TestResults.empty()
        error = TestResults.from_error("something broke")

        # Both have zero counts
        assert empty.total == error.total == 0

        # But different states
        assert empty.state == ExecutionState.EMPTY
        assert error.state == ExecutionState.ERROR

        # And different properties
        assert empty.is_error is False
        assert error.is_error is True
        assert empty.has_error is False
        assert error.has_error is True

    def test_empty_vs_skipped_distinction(self) -> None:
        """EMPTY and SKIPPED states are distinguishable."""
        empty = TestResults.empty()
        skipped = TestResults.not_run("render-only")

        # Both have zero counts
        assert empty.total == skipped.total == 0

        # But different states
        assert empty.state == ExecutionState.EMPTY
        assert skipped.state == ExecutionState.SKIPPED

        # And different properties
        assert empty.was_not_run is False
        assert skipped.was_not_run is True

    def test_success_vs_empty_distinction(self) -> None:
        """SUCCESS with zero tests and EMPTY are distinguishable."""
        # SUCCESS state with zero counts (unusual but possible)
        success_zero = TestResults()

        # EMPTY state
        empty = TestResults.empty()

        # Same counts
        assert success_zero.total == empty.total == 0

        # Different states
        assert success_zero.state == ExecutionState.SUCCESS
        assert empty.state == ExecutionState.EMPTY
