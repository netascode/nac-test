# -*- coding: utf-8 -*-

"""Type definitions for PyATS HTML reporting."""

from enum import Enum
from typing import Any, TypedDict


class ResultStatus(str, Enum):
    """Status values for test results."""

    PASSED = "passed"
    FAILED = "failed"
    PASSX = "passx"
    ABORTED = "aborted"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    ERRORED = "errored"
    INFO = "info"


class Result(TypedDict):
    """Represents a test result."""

    status: ResultStatus
    message: str


class CommandExecution(TypedDict):
    """Represents a command/API execution record."""

    device_name: str  # Device name (router, switch, APIC, SDWAN Manager, etc.)
    command: str  # Command or API endpoint
    output: str  # Raw output/response
    data: dict[str, Any]  # Parsed data (if applicable)


ParameterData = dict[str, Any]
