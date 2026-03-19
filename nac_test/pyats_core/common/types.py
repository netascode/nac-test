# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Type definitions for NAC test framework verification results.

This module contains TypedDict definitions and type utilities that provide
better type safety and IDE support for verification result structures used
throughout the NAC test automation framework.
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Generic,
    Protocol,
    TypeVar,
)

# Python 3.10 doesn't allow inheriting from both TypedDict and Generic.
# Use typing_extensions for 3.10 compatibility, standard typing for 3.11+.
if sys.version_info >= (3, 11):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict

# Python 3.10 doesn't allow inheriting from both TypedDict and Generic.
# Use typing_extensions for 3.10 compatibility, standard typing for 3.11+.
if sys.version_info >= (3, 11):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict

from nac_test.pyats_core.reporting.types import ResultStatus

DEFAULT_TEST_TYPE = "api"


@dataclass
class TestFileMetadata:
    """Metadata extracted from a PyATS test file.

    Attributes:
        path: Absolute path to the test file
        test_type: The test type ("api" or "d2d")
        groups: List of group tags from the test class's `groups` attribute.
                Empty list if no groups are defined.
    """

    path: Path
    test_type: str
    groups: list[str] = field(default_factory=list)


@dataclass
class TestExecutionPlan:
    """Complete test execution context from discovery through results analysis.

    This dataclass carries all information needed for test execution and
    post-execution analysis in a single pass, eliminating the need for:
    - Separate categorization calls after discovery
    - Re-instantiating TestMetadataResolver post-execution

    The pre-computed `test_type_by_path` dictionary enables O(1) lookups
    during post-execution result splitting, replacing the previous pattern
    of re-parsing test files to determine their types.

    Attributes:
        api_tests: List of API test metadata (controller/REST tests)
        d2d_tests: List of D2D test metadata (Direct-to-Device/SSH tests)
        skipped_files: List of (path, reason) tuples for files skipped during discovery
        filtered_by_tags: Count of tests filtered out by tag patterns
        test_type_by_path: Pre-computed mapping of resolved paths to test types
    """

    api_tests: list[TestFileMetadata]
    d2d_tests: list[TestFileMetadata]
    skipped_files: list[tuple[Path, str]]
    filtered_by_tags: int
    test_type_by_path: dict[Path, str] = field(default_factory=dict)

    @property
    def all_tests(self) -> list[TestFileMetadata]:
        """All discovered tests (API + D2D combined)."""
        return self.api_tests + self.d2d_tests

    @property
    def total_count(self) -> int:
        """Total number of discovered tests."""
        return len(self.api_tests) + len(self.d2d_tests)

    @property
    def api_paths(self) -> list[Path]:
        """API test paths for execution."""
        return [t.path for t in self.api_tests]

    @property
    def d2d_paths(self) -> list[Path]:
        """D2D test paths for execution."""
        return [t.path for t in self.d2d_tests]

    def get_test_type(self, test_file: Path | str | None) -> str:
        """Get test type for a file path. Used post-execution for status splitting."""
        if test_file is None:
            return DEFAULT_TEST_TYPE
        path = (
            Path(test_file).resolve()
            if isinstance(test_file, str)
            else test_file.resolve()
        )
        return self.test_type_by_path.get(path, DEFAULT_TEST_TYPE)


class ApiDetails(TypedDict, total=False):
    """API transaction details for debugging and monitoring."""

    url: str
    response_code: int
    response_time: float
    response_body: Any


class VerificationDetails(TypedDict, total=False):
    """Expected vs actual state comparison for operational verifications."""

    expected_state: str
    actual_state: str
    vrf: str | None  # For network-specific verifications


class BaseVerificationResult(TypedDict):
    """Base result structure used by format_verification_result() method."""

    status: ResultStatus
    context: dict[str, Any]
    reason: str
    api_duration: float
    timestamp: float


class BaseVerificationResultOptional(BaseVerificationResult, total=False):
    """Base result with optional fields."""

    api_details: ApiDetails


# Type variables for generic support
TContext = TypeVar("TContext", bound=dict[str, Any])
TDomainData = TypeVar("TDomainData", bound=dict[str, Any])


class VerificationResultProtocol(Protocol):
    """Protocol defining the minimal interface for verification results.

    This allows test implementations to create custom result types while
    maintaining compatibility with the base framework methods.
    """

    status: ResultStatus | str
    reason: str

    def get(self, key: str, default: Any = None) -> Any:
        """Allow dict-like access for backward compatibility."""
        ...


class GenericVerificationResult(
    BaseVerificationResultOptional, Generic[TContext, TDomainData]
):
    """Generic verification result that can be extended with custom context and domain data.

    This provides a flexible way for test implementations to define their own
    result structures while maintaining type safety and compatibility with the
    base framework.

    Example usage:
        # Define custom context and domain data
        class CustomContext(TypedDict):
            service_name: str
            endpoint_url: str

        class CustomDomainData(TypedDict):
            response_data: Dict[str, Any]
            metadata: Optional[Dict[str, str]]

        # Use the generic result type
        CustomResult = GenericVerificationResult[CustomContext, CustomDomainData]
    """

    domain_data: TDomainData


class ExtensibleVerificationResult(BaseVerificationResultOptional):
    """Extensible result type that allows arbitrary additional fields.

    This is useful for test implementations that need to add custom fields
    without defining a complete TypedDict structure. It maintains backward
    compatibility while providing type hints for the core fields.
    """

    # Allow arbitrary additional fields through inheritance
    pass


# Comprehensive Union type for all verification results
VerificationResult = (
    # Base structured results
    BaseVerificationResultOptional
    # Generic extensible results
    | GenericVerificationResult[Any, Any]
    | ExtensibleVerificationResult
    # Protocol-compatible results
    | VerificationResultProtocol
    # Fallback for maximum flexibility
    | dict[str, Any]
)
