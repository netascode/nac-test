# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Error classification utilities for HTTP and network errors.

This module provides classification logic for categorizing errors during
controller authentication and other HTTP operations. It converts raw
exceptions into structured outcome classifications.
"""

import re
from enum import Enum

from nac_test.core.http_constants import (
    HTTP_AUTH_FAILURE_CODES,
    HTTP_SERVICE_UNAVAILABLE_CODES,
    HTTP_STATUS_CLIENT_ERROR_MAX,
    HTTP_STATUS_CLIENT_ERROR_MIN,
    HTTP_STATUS_SERVER_ERROR_MAX,
    HTTP_STATUS_SERVER_ERROR_MIN,
)


class AuthOutcome(Enum):
    """Outcome classification for a pre-flight controller authentication check."""

    SUCCESS = "success"
    BAD_CREDENTIALS = "bad_credentials"
    UNREACHABLE = "unreachable"
    UNEXPECTED_ERROR = "unexpected_error"


# HTTP status code pattern for reliable extraction
# Matches 3-digit HTTP status codes (100-599) with word boundaries
_HTTP_STATUS_CODE_PATTERN: re.Pattern[str] = re.compile(r"\b([1-5]\d{2})\b")

# Network-level error indicators for unreachable classification
_UNREACHABLE_INDICATORS: tuple[str, ...] = (
    "timed out",
    "timeout",
    "connection refused",
    "unreachable",
    "connect error",
    "could not connect",
    "network is unreachable",
    "no route to host",
    "name or service not known",
    "getaddrinfo failed",
    "temporary failure in name resolution",
)


def _classify_http_status(status_code: int) -> tuple[AuthOutcome, str]:
    """Classify an HTTP status code into an authentication outcome.

    Args:
        status_code: The HTTP status code to classify.

    Returns:
        A tuple of (AuthOutcome, detail_string).
    """
    # Authentication/authorization failures
    if status_code in HTTP_AUTH_FAILURE_CODES:
        status_text = "Unauthorized" if status_code == 401 else "Forbidden"
        return AuthOutcome.BAD_CREDENTIALS, f"HTTP {status_code}: {status_text}"

    # Rate limiting or service unavailable - treat as unreachable
    if status_code in HTTP_SERVICE_UNAVAILABLE_CODES:
        return (
            AuthOutcome.UNREACHABLE,
            f"HTTP {status_code}: Service temporarily unavailable",
        )

    # Other 4xx errors - client errors, not necessarily auth
    if HTTP_STATUS_CLIENT_ERROR_MIN <= status_code <= HTTP_STATUS_CLIENT_ERROR_MAX:
        return AuthOutcome.UNEXPECTED_ERROR, f"HTTP {status_code}: Client error"

    # Server errors
    if HTTP_STATUS_SERVER_ERROR_MIN <= status_code <= HTTP_STATUS_SERVER_ERROR_MAX:
        return AuthOutcome.UNEXPECTED_ERROR, f"HTTP {status_code}: Server error"

    # Unknown HTTP status code
    return AuthOutcome.UNEXPECTED_ERROR, f"HTTP {status_code}: Unknown status"


def _classify_auth_error(error: Exception) -> tuple[AuthOutcome, str]:
    """Classify an authentication error into an outcome.

    Uses a two-tier strategy:
    1. Check for network-level failures first (timeouts, connection refused, DNS)
    2. Then extract HTTP status codes for HTTP-level failures

    Network indicators are checked first to avoid false positives from port
    numbers being matched as status codes (e.g., "port 443" matching as HTTP 443).

    Args:
        error: The exception raised during authentication.

    Returns:
        A tuple of (AuthOutcome, detail_string).
    """
    error_msg = str(error)
    error_msg_lower = error_msg.lower()

    # Tier 1: Check for network-level unreachable indicators first
    if any(indicator in error_msg_lower for indicator in _UNREACHABLE_INDICATORS):
        return AuthOutcome.UNREACHABLE, error_msg

    # Tier 2: Check for HTTP status codes (reliable for HTTP-level errors)
    status_match = _HTTP_STATUS_CODE_PATTERN.search(error_msg)
    if status_match:
        status_code = int(status_match.group(1))
        return _classify_http_status(status_code)

    # Unknown error pattern
    return AuthOutcome.UNEXPECTED_ERROR, error_msg
