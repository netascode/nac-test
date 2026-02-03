# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Core types for nac-test orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TestResults:
    """Test execution results for orchestrators.

    Tracks test outcome counts with support for aggregation via + operator.
    Can also carry execution errors for proper exit code handling.

    Attributes:
        total: Total number of tests executed
        passed: Number of tests that passed
        failed: Number of tests that failed
        skipped: Number of tests that were skipped
        by_framework: Per-framework breakdown (keys: "API", "D2D", "ROBOT")
        errors: List of execution error messages (not test failures)
    """

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    by_framework: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def __add__(self, other: object) -> TestResults:
        """Aggregate two TestResults together."""
        if not isinstance(other, TestResults):
            return NotImplemented

        return TestResults(
            total=self.total + other.total,
            passed=self.passed + other.passed,
            failed=self.failed + other.failed,
            skipped=self.skipped + other.skipped,
            by_framework={**self.by_framework, **other.by_framework},
            errors=self.errors + other.errors,
        )

    def __iadd__(self, other: object) -> TestResults:
        """In-place aggregation."""
        if not isinstance(other, TestResults):
            return NotImplemented

        self.total += other.total
        self.passed += other.passed
        self.failed += other.failed
        self.skipped += other.skipped
        self.by_framework.update(other.by_framework)
        self.errors.extend(other.errors)
        return self

    @classmethod
    def empty(cls) -> TestResults:
        """Create empty results (all zeros, no errors)."""
        return cls()

    @classmethod
    def from_error(cls, error: str, framework: str | None = None) -> TestResults:
        """Create TestResults representing an execution error.

        Args:
            error: Error message describing what went wrong
            framework: Optional framework identifier (e.g., "robot", "pyats")

        Returns:
            TestResults with the error recorded
        """
        prefix = f"[{framework}] " if framework else ""
        return cls(errors=[f"{prefix}{error}"])

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
        if self.is_empty:
            return 0
        return 0
