# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Core types for nac-test orchestration."""

from dataclasses import dataclass, field


@dataclass
class TestResults:
    """Test execution results from a single test framework or test type.

    Represents discrete test outcomes from one source (e.g., PyATS API tests,
    PyATS D2D tests, or Robot Framework tests). Does not aggregate across
    frameworks - use CombinedResults for that.

    Attributes:
        total: Total number of tests executed
        passed: Number of tests that passed
        failed: Number of tests that failed
        skipped: Number of tests that were skipped
        errors: List of execution error messages (not test failures)
    """

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "TestResults":
        """Create empty results (all zeros, no errors)."""
        return cls()

    @classmethod
    def from_error(cls, error: str) -> "TestResults":
        """Create TestResults representing an execution error.

        Args:
            error: Error message describing what went wrong

        Returns:
            TestResults with zero counts and the error recorded
        """
        return cls(errors=[error])

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
    def has_errors(self) -> bool:
        """Check if any execution errors occurred (not test failures)."""
        return len(self.errors) > 0

    @property
    def is_empty(self) -> bool:
        """Check if no tests were executed."""
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

    def __str__(self) -> str:
        """Concise string representation: total/passed/failed/skipped."""
        return f"{self.total}/{self.passed}/{self.failed}/{self.skipped}"


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
    def errors(self) -> list[str]:
        """All execution errors across all frameworks."""
        all_errors: list[str] = []
        for r in self._iter_results():
            all_errors.extend(r.errors)
        return all_errors

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
        return len(self.errors) > 0

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
