"""Type definitions for NAC test framework verification results.

This module contains TypedDict definitions and type utilities that provide
better type safety and IDE support for verification result structures used
throughout the NAC test automation framework.
"""

import sys
from typing import (
    Any,
    Generic,
    Protocol,
    TypeVar,
    Union,
)

# Python 3.10 doesn't allow inheriting from both TypedDict and Generic.
# Use typing_extensions for 3.10 compatibility, standard typing for 3.11+.
if sys.version_info >= (3, 11):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict

from nac_test.pyats_core.reporting.types import ResultStatus


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
VerificationResult = Union[
    # Base structured results
    BaseVerificationResultOptional,
    # Generic extensible results
    GenericVerificationResult[Any, Any],
    ExtensibleVerificationResult,
    # Protocol-compatible results
    VerificationResultProtocol,
    # Fallback for maximum flexibility
    dict[str, Any],
]
