# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Core types for nac-test orchestration."""

from dataclasses import dataclass
from enum import Enum


class ExecutionState(str, Enum):
    """Execution state for test results.

    Distinguishes between different outcomes:
        SUCCESS: Tests ran (may have test failures, but execution succeeded)
        EMPTY: No tests found/executed (expected outcome, not an error)
        SKIPPED: Tests intentionally skipped (e.g., render-only mode)
        ERROR: Execution failed with an error (e.g., framework crash)
    """

    SUCCESS = "success"
    EMPTY = "empty"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResults:
    """Test execution results from a single test framework or test type.

    Represents discrete test outcomes from one source (e.g., PyATS API tests,
    PyATS D2D tests, or Robot Framework tests). Does not aggregate across
    frameworks - use CombinedResults for that.

    Attributes:
        passed: Number of tests that passed
        failed: Number of tests that failed (includes errored tests)
        skipped: Number of tests that were skipped
        other: Number of tests with other statuses (blocked, aborted, passx, info)
        reason: Context for non-SUCCESS states (error message or skip reason)
        state: Execution state indicating the outcome type

    Properties:
        total: Total number of tests (computed as passed + failed + skipped + other)

    Note: Robot Framework only has three test statuses (PASS/FAIL/SKIP), so
    `other` will always be 0 for Robot results. PyATS has additional statuses
    (blocked, passx, aborted, info) which are tracked in `other`.

    The total is always computed correctly:
        total = passed + failed + skipped + other

    For success rate calculation, skipped tests are excluded from the denominator
    since they weren't executed. Tests in `other` (blocked, aborted, etc.) ARE
    included in the denominator as they represent tests that were attempted but
    did not pass.
    """

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    other: int = 0
    reason: str | None = None
    state: ExecutionState = ExecutionState.SUCCESS

    @property
    def total(self) -> int:
        """Total number of tests (always computed from counts)."""
        return self.passed + self.failed + self.skipped + self.other

    @classmethod
    def empty(cls) -> "TestResults":
        """Create empty results (no tests found/executed).

        Use when no tests were discovered or matched filters.
        This is an expected outcome, not an error.
        """
        return cls(state=ExecutionState.EMPTY)

    @classmethod
    def not_run(cls, reason: str | None = None) -> "TestResults":
        """Create results for intentionally skipped execution.

        Use when tests were intentionally not run (e.g., render-only mode).

        Args:
            reason: Optional explanation for why tests were skipped
        """
        return cls(state=ExecutionState.SKIPPED, reason=reason)

    @classmethod
    def from_error(cls, reason: str) -> "TestResults":
        """Create TestResults representing an execution error.

        Use when test execution failed due to a framework or infrastructure error
        (not test failures).

        Args:
            reason: Error message describing what went wrong

        Returns:
            TestResults with zero counts, reason recorded, and ERROR state
        """
        return cls(reason=reason, state=ExecutionState.ERROR)

    @property
    def success_rate(self) -> float:
        """Success rate excluding skipped tests (0.0-100.0)."""
        tests_with_results = self.total - self.skipped
        if tests_with_results > 0:
            return (self.passed / tests_with_results) * 100
        return 0.0

    @property
    def has_failures(self) -> bool:
        """Check if any tests failed."""
        return self.failed > 0

    @property
    def has_error(self) -> bool:
        """Check if an execution error occurred (not test failures)."""
        return self.state == ExecutionState.ERROR

    @property
    def is_empty(self) -> bool:
        """Check if no tests were executed."""
        return self.total == 0

    @property
    def is_error(self) -> bool:
        """Check if execution failed with an error."""
        return self.state == ExecutionState.ERROR

    @property
    def was_not_run(self) -> bool:
        """Check if tests were intentionally not run."""
        return self.state == ExecutionState.SKIPPED

    @property
    def exit_code(self) -> int:
        """Calculate appropriate exit code per Robot Framework convention.

        Exit codes:
            0: All tests passed, no errors
            1-250: Number of test failures (capped at 250)
            255: Execution errors occurred (has_error is True)

        This is not yet used, will be refined with #469
        """
        if self.has_error:
            return 255
        if self.has_failures:
            return min(self.failed, 250)
        return 0

    def __str__(self) -> str:
        """Concise string representation: total/passed/failed/skipped[/other]."""
        base = f"{self.total}/{self.passed}/{self.failed}/{self.skipped}"
        if self.other > 0:
            return f"{base}/{self.other}"
        return base


@dataclass
class PyATSResults:
    """Results from PyATS test execution.

    Groups API and D2D test results from a single PyATS run.
    Robot Framework doesn't need this as it returns a single TestResults
    (Robot doesn't distinguish between API and D2D test types).

    Attributes:
        api: Results from PyATS API tests (controller API validation)
        d2d: Results from PyATS D2D tests (device-to-device validation)
    """

    api: TestResults | None = None
    d2d: TestResults | None = None

    def __str__(self) -> str:
        """Concise string: PyATSResults(API: t/p/f/s, D2D: t/p/f/s)."""
        parts = []
        if self.api is not None:
            parts.append(f"API: {self.api}")
        if self.d2d is not None:
            parts.append(f"D2D: {self.d2d}")
        return f"PyATSResults({', '.join(parts) if parts else 'empty'})"


@dataclass
class CombinedResults:
    """Combined test results from all frameworks.

    Container for test results across PyATS (API/D2D) and Robot Framework.
    Uses explicit attributes for type safety and clear ownership.

    Attributes:
        api: Results from PyATS API tests (controller API validation)
        d2d: Results from PyATS D2D tests (device-to-device validation)
        robot: Results from Robot Framework tests
    """

    api: TestResults | None = None
    d2d: TestResults | None = None
    robot: TestResults | None = None

    def __str__(self) -> str:
        """Concise string: CombinedResults(API: t/p/f/s, D2D: t/p/f/s, Robot: t/p/f/s)."""
        parts = []
        if self.api is not None:
            parts.append(f"API: {self.api}")
        if self.d2d is not None:
            parts.append(f"D2D: {self.d2d}")
        if self.robot is not None:
            parts.append(f"Robot: {self.robot}")
        return f"CombinedResults({', '.join(parts) if parts else 'empty'})"

    def _iter_results(self) -> list[TestResults]:
        """Get list of non-None results for aggregation."""
        return [r for r in (self.api, self.d2d, self.robot) if r is not None]

    @property
    def total(self) -> int:
        """Total tests across all frameworks."""
        return sum(r.total for r in self._iter_results())

    @property
    def passed(self) -> int:
        """Total passed tests across all frameworks."""
        return sum(r.passed for r in self._iter_results())

    @property
    def failed(self) -> int:
        """Total failed tests across all frameworks."""
        return sum(r.failed for r in self._iter_results())

    @property
    def skipped(self) -> int:
        """Total skipped tests across all frameworks."""
        return sum(r.skipped for r in self._iter_results())

    @property
    def other(self) -> int:
        """Total tests with other statuses across all frameworks."""
        return sum(r.other for r in self._iter_results())

    @property
    def errors(self) -> list[str]:
        """All execution errors/reasons across all frameworks."""
        return [r.reason for r in self._iter_results() if r.reason is not None]

    @property
    def success_rate(self) -> float:
        """Combined success rate excluding skipped tests (0.0-100.0)."""
        tests_with_results = self.total - self.skipped
        if tests_with_results > 0:
            return (self.passed / tests_with_results) * 100
        return 0.0

    @property
    def has_failures(self) -> bool:
        """Check if any tests failed across all frameworks."""
        return self.failed > 0

    @property
    def has_errors(self) -> bool:
        """Check if any execution errors occurred across all frameworks."""
        return any(r.state == ExecutionState.ERROR for r in self._iter_results())

    @property
    def is_empty(self) -> bool:
        """Check if no tests were executed across all frameworks."""
        return self.total == 0

    @property
    def exit_code(self) -> int:
        """Calculate appropriate exit code per Robot Framework convention.

        Exit codes:
            0: All tests passed, no errors
            1-250: Number of test failures (capped at 250)
            255: Execution errors occurred (has_errors is True)

        This is not yet used, will be refined with #469
        """
        if self.has_errors:
            return 255
        if self.has_failures:
            return min(self.failed, 250)
        return 0
