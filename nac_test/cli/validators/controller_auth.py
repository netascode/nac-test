# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Pre-flight controller authentication validator.

This module provides a pre-flight authentication check that validates controller
credentials before any test execution begins. It uses the same auth implementations
from nac-test-pyats-common that PyATS tests use, ensuring consistent behavior.

Benefits:
- Fails fast with clear error message instead of N identical auth failures
- Populates the AuthCache, so first real test gets a cache hit
- Works for both PyATS and Robot Framework execution modes

The pre-flight check happens at the CLI layer before either test framework is
invoked, providing immediate feedback for credential and connectivity issues.
"""

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class AuthOutcome(Enum):
    """Outcome classification for a pre-flight controller authentication check."""

    SUCCESS = "success"
    BAD_CREDENTIALS = "bad_credentials"
    UNREACHABLE = "unreachable"
    UNEXPECTED_ERROR = "unexpected_error"


@dataclass(frozen=True)
class AuthCheckResult:
    """Result of a pre-flight controller authentication check.

    Attributes:
        success: Whether the authentication succeeded.
        reason: Classification of the failure (or SUCCESS if successful).
        controller_type: The detected controller type (e.g., "ACI", "SDWAN", "CC").
        controller_url: The URL of the controller that was checked.
        detail: Human-readable detail about the result (e.g., "HTTP 401: Unauthorized").
    """

    success: bool
    reason: AuthOutcome
    controller_type: str
    controller_url: str
    detail: str


@dataclass(frozen=True)
class ControllerConfig:
    """Configuration metadata for a supported controller type.

    Attributes:
        display_name: User-facing name (e.g., "APIC", "Catalyst Center").
        url_env_var: Environment variable name for the controller URL.
        env_var_prefix: Prefix for credential env vars (e.g., "ACI" → ACI_USERNAME).
    """

    display_name: str
    url_env_var: str
    env_var_prefix: str


CONTROLLER_REGISTRY: dict[str, ControllerConfig] = {
    "ACI": ControllerConfig(
        display_name="APIC", url_env_var="ACI_URL", env_var_prefix="ACI"
    ),
    "SDWAN": ControllerConfig(
        display_name="SDWAN Manager", url_env_var="SDWAN_URL", env_var_prefix="SDWAN"
    ),
    "CC": ControllerConfig(
        display_name="Catalyst Center", url_env_var="CC_URL", env_var_prefix="CC"
    ),
}


def extract_host(url: str) -> str:
    """Extract the host (and optional port) from a URL.

    Uses Python's standard library urlparse for robust parsing.
    Handles URLs with or without scheme prefixes.

    Args:
        url: A URL string (e.g., "https://apic.example.com:443/path").

    Returns:
        The host portion of the URL (e.g., "apic.example.com:443").
        Returns empty string for empty input.

    Examples:
        >>> extract_host("https://apic.example.com:443/api/v1")
        'apic.example.com:443'
        >>> extract_host("http://10.1.2.3")
        '10.1.2.3'
        >>> extract_host("controller.local")
        'controller.local'
    """
    if not url:
        return ""

    parsed = urlparse(url)
    if parsed.netloc:
        return parsed.netloc

    # Handle URLs without scheme (urlparse puts them in path)
    # e.g., "apic.example.com/path" -> path="apic.example.com/path"
    return parsed.path.split("/")[0]


def _get_controller_url(controller_type: str) -> str:
    """Get the controller URL from environment variables.

    Args:
        controller_type: The detected controller type.

    Returns:
        The controller URL, or empty string if not found.
    """
    config = CONTROLLER_REGISTRY.get(controller_type)
    if config is None:
        return ""
    url = os.environ.get(config.url_env_var, "")
    return url.rstrip("/") if url else ""


def _get_auth_callable(controller_type: str) -> Callable[[], Any] | None:
    """Get the auth function for the given controller type.

    Uses conditional imports to avoid hard dependency on nac-test-pyats-common.
    Returns None if the adapters package is not installed or if the controller
    type doesn't have an auth adapter.

    Args:
        controller_type: The detected controller type (e.g., "ACI", "SDWAN", "CC").

    Returns:
        The get_auth() callable for the controller, or None if not available.
    """
    try:
        if controller_type == "ACI":
            from nac_test_pyats_common.aci import APICAuth

            return APICAuth.get_auth  # type: ignore[no-any-return]
        elif controller_type == "SDWAN":
            from nac_test_pyats_common.sdwan import SDWANManagerAuth

            return SDWANManagerAuth.get_auth  # type: ignore[no-any-return]
        elif controller_type == "CC":
            from nac_test_pyats_common.catc import CatalystCenterAuth

            return CatalystCenterAuth.get_auth  # type: ignore[no-any-return]
    except ImportError:
        logger.debug(
            "nac-test-pyats-common not installed, skipping pre-flight auth check"
        )
        return None
    return None


def _classify_auth_error(error: Exception) -> tuple[AuthOutcome, str]:
    """Classify an authentication error into a failure reason.

    Parses the error message to determine if the failure was due to bad credentials,
    unreachable controller, or an unexpected error.

    Args:
        error: The exception raised during authentication.

    Returns:
        A tuple of (AuthOutcome, detail_string).
    """
    error_msg = str(error).lower()

    # Check for bad credentials indicators
    bad_creds_indicators = [
        "401",
        "403",
        "unauthorized",
        "forbidden",
        "invalid credentials",
        "authentication failed",
        "login failed",
    ]
    if any(indicator in error_msg for indicator in bad_creds_indicators):
        # Extract the HTTP status code for the detail message
        if "401" in error_msg:
            return AuthOutcome.BAD_CREDENTIALS, "HTTP 401: Unauthorized"
        elif "403" in error_msg:
            return AuthOutcome.BAD_CREDENTIALS, "HTTP 403: Forbidden"
        else:
            return AuthOutcome.BAD_CREDENTIALS, str(error)

    # Check for unreachable indicators
    unreachable_indicators = [
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
    ]
    if any(indicator in error_msg for indicator in unreachable_indicators):
        return AuthOutcome.UNREACHABLE, str(error)

    # Unexpected error
    return AuthOutcome.UNEXPECTED_ERROR, str(error)


def preflight_auth_check(controller_type: str) -> AuthCheckResult:
    """Attempt authentication to the detected controller before tests run.

    Uses the same auth implementations from nac-test-pyats-common that
    the actual test execution uses. On success, the token/session is
    cached in AuthCache, so the first test gets a cache hit.

    This function is designed to fail gracefully:
    - If adapters package not installed: returns success (can't check)
    - If controller type has no auth adapter: returns success (nothing to check)
    - If environment variables missing: returns success (let the actual auth fail later)

    Args:
        controller_type: Detected controller type (e.g., "ACI", "SDWAN", "CC").

    Returns:
        AuthCheckResult with success/failure status and actionable detail.
    """
    controller_url = _get_controller_url(controller_type)
    config = CONTROLLER_REGISTRY.get(controller_type)
    display_name = config.display_name if config else controller_type

    # Get the auth callable for this controller type
    auth_callable = _get_auth_callable(controller_type)
    if auth_callable is None:
        # Either adapters not installed or controller type doesn't have auth
        # In both cases, skip the check and let the actual tests handle it
        logger.debug(
            "No auth adapter available for %s, skipping pre-flight check",
            controller_type,
        )
        return AuthCheckResult(
            success=True,
            reason=AuthOutcome.SUCCESS,
            controller_type=controller_type,
            controller_url=controller_url,
            detail="Pre-flight check skipped (no auth adapter available)",
        )

    # Attempt authentication
    logger.info(
        "Pre-flight auth check: authenticating to %s at %s",
        display_name,
        controller_url,
    )

    try:
        auth_callable()
        logger.info("Pre-flight auth check: %s authentication successful", display_name)
        return AuthCheckResult(
            success=True,
            reason=AuthOutcome.SUCCESS,
            controller_type=controller_type,
            controller_url=controller_url,
            detail="Authentication successful",
        )
    except ValueError as e:
        # Missing environment variables - let the actual auth fail later with proper error
        logger.debug("Pre-flight auth check skipped due to missing env vars: %s", e)
        return AuthCheckResult(
            success=True,
            reason=AuthOutcome.SUCCESS,
            controller_type=controller_type,
            controller_url=controller_url,
            detail=f"Pre-flight check skipped: {e}",
        )
    except Exception as e:
        # Authentication failed - classify the error
        reason, detail = _classify_auth_error(e)
        logger.warning(
            "Pre-flight auth check failed for %s: %s (%s)",
            display_name,
            detail,
            reason.value,
        )
        return AuthCheckResult(
            success=False,
            reason=reason,
            controller_type=controller_type,
            controller_url=controller_url,
            detail=detail,
        )
