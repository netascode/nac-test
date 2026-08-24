# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Pre-flight controller authentication check.

Validates controller credentials before test execution by attempting the same
authentication that PyATS tests use.  On success the token/session is cached in
AuthCache so the first real test gets a cache hit.

This module lives in ``core/`` because authentication reachability is part of
the controller resolution domain, not a CLI concern.
"""

import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from nac_test.core.controller import (
    CONTROLLER_REGISTRY,
    get_controller_url,
    get_display_name,
)
from nac_test.core.error_classification import (
    AuthOutcome,
    classify_auth_error,
    extract_http_status_code,
)
from nac_test.core.types import ControllerContext, ControllerTypeKey
from nac_test.pyats_core.common.auth_cache import AuthCache

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthCheckResult:
    """Result of a pre-flight controller authentication check.

    Attributes:
        success: Whether the authentication succeeded.
        reason: Classification of the failure (or SUCCESS if successful).
        controller_type: The detected controller type (e.g., "ACI", "SDWAN", "CC").
        controller_url: The URL of the controller that was checked.
        detail: Human-readable detail about the result (e.g., "HTTP 401: Unauthorized").
        status_code: HTTP status code from the failed request, or None for
            non-HTTP failures (e.g., connection timeout, DNS failure) and successes.
    """

    success: bool
    reason: AuthOutcome
    controller_type: ControllerTypeKey
    controller_url: str
    detail: str
    status_code: int | None = None


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
    # PyATS configuration module parses sys.argv at import time looking for
    # --pyats-configuration. Our --pyats flag prefix-matches that argument,
    # causing argparse to error with "expected one argument". Strip it from
    # sys.argv during the import, same pattern as device_inventory.py.
    original_argv = sys.argv.copy()
    try:
        sys.argv = [arg for arg in sys.argv if arg != "--pyats"]

        if controller_type == "ACI":
            from nac_test_pyats_common.aci import APICAuth

            return APICAuth.get_auth  # type: ignore[attr-defined, no-any-return]  # External adapters return Any
        elif controller_type == "SDWAN":
            from nac_test_pyats_common.sdwan import SDWANManagerAuth

            return SDWANManagerAuth.get_auth  # type: ignore[attr-defined, no-any-return]  # External adapters return Any
        elif controller_type == "CC":
            from nac_test_pyats_common.catc import CatalystCenterAuth

            return CatalystCenterAuth.get_auth  # type: ignore[attr-defined, no-any-return]  # External adapters return Any
    except ImportError:
        logger.debug(
            "nac-test-pyats-common not installed, skipping pre-flight auth check"
        )
        return None
    finally:
        sys.argv = original_argv
    return None


def preflight_auth_check(ctx: ControllerContext) -> AuthCheckResult:
    """Attempt authentication to the detected controller before tests run.

    Uses the same auth implementations from nac-test-pyats-common that
    the actual test execution uses. On success, the token/session is
    cached in AuthCache, so the first test gets a cache hit.

    This function is designed to fail gracefully:
    - If adapters package not installed: returns success (can't check)
    - If controller type has no auth adapter: returns success (nothing to check)
    - If environment variables missing: returns success (let the actual auth fail later)

    Args:
        ctx: Resolved controller context from ``resolve_controller()``.

    Returns:
        AuthCheckResult with success/failure status and actionable detail.
    """
    controller_type = ctx.controller_type
    try:
        controller_url = get_controller_url(controller_type)
    except KeyError:
        controller_url = ""
    # Auth adapters strip trailing "/" before caching (cache key normalization).
    # Match that here so AuthCache.invalidate() finds the right entry.
    cache_url = controller_url.rstrip("/")
    display_name = get_display_name(controller_type)

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
            reason=AuthOutcome.SKIPPED,
            controller_type=controller_type,
            controller_url=controller_url,
            detail="Pre-flight check skipped (no auth adapter available)",
        )

    # Invalidate any stale cached token so we validate the current credentials.
    # Best-effort: a failure here must never block test execution.
    config = CONTROLLER_REGISTRY.get(controller_type)
    if config is not None and config.cache_key is not None and cache_url:
        try:
            logger.debug(
                "Invalidating auth cache for %s before pre-flight check",
                config.cache_key,
            )
            AuthCache.invalidate(config.cache_key, cache_url)
        except Exception as e:
            logger.debug("Cache invalidation failed (non-fatal): %s", e)

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
            reason=AuthOutcome.SKIPPED,
            controller_type=controller_type,
            controller_url=controller_url,
            detail=f"Pre-flight check skipped: {e}",
        )
    except Exception as e:
        # Authentication failed - classify the error
        reason, detail = classify_auth_error(e)
        status_code = extract_http_status_code(e)
        logger.debug(
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
            status_code=status_code,
        )
