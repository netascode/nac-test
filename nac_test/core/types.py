# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Core types for nac-test orchestration."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TestCounts:
    """Test execution counts for orchestrators.

    Tracks test outcome counts with support for aggregation via + operator
    and dict-like access for backward compatibility.
    """

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    by_framework: dict[str, Any] = field(default_factory=dict)

    def __add__(self, other: object) -> "TestCounts":
        """Aggregate two TestCounts together."""
        if not isinstance(other, TestCounts):
            return NotImplemented

        return TestCounts(
            total=self.total + other.total,
            passed=self.passed + other.passed,
            failed=self.failed + other.failed,
            skipped=self.skipped + other.skipped,
            by_framework={**self.by_framework, **other.by_framework},
        )

    def __iadd__(self, other: object) -> "TestCounts":
        """In-place aggregation."""
        if not isinstance(other, TestCounts):
            return NotImplemented

        self.total += other.total
        self.passed += other.passed
        self.failed += other.failed
        self.skipped += other.skipped
        self.by_framework.update(other.by_framework)
        return self

    def __getitem__(self, key: str) -> Any:
        """Dict-like access for backward compatibility."""
        if key == "by_framework":
            return self.by_framework
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-like get() method."""
        try:
            return self[key]
        except (AttributeError, KeyError):
            return default

    @classmethod
    def empty(cls) -> "TestCounts":
        """Create empty counts (all zeros)."""
        return cls()

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
    def is_empty(self) -> bool:
        """Check if no tests were executed."""
        return self.total == 0
