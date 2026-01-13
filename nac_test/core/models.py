
"""Core data models shared across the nac-test framework.

This module contains data structures that are used by multiple components
of the framework (PyATS, Robot, CLI, etc.).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TestStatus(str, Enum):
    """Generic test status values used across the framework."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERRORED = "errored"


@dataclass
class TestResult:
    """Generic test result structure used across the framework."""

    test_name: str
    status: TestStatus
    duration: float | None = None
    message: str | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None
