# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Low-level environment variable parsing utilities."""

# Why _env.py lives here instead of utils/env.py:
#
# core/constants.py imports this at load time. Placing it in utils/ triggers
# utils/__init__.py, which imports terminal.py -> core/types.py -> core/constants.py
# (circular). The underscore prefix keeps it out of the public API.
#
# See #610 for discussion on utils/__init__.py re-export strategy.

import logging
import os
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T", int, float)


def get_bool_env(env_var: str, default: bool = False) -> bool:
    """Get a boolean value from environment variable.

    Args:
        env_var: Environment variable name
        default: Default value if env var is not set (default: False)

    Returns:
        True if env var value (lowercased) is in ("true", "yes", "1"),
        False if env var is not set or has any other value.
    """
    env_value = os.environ.get(env_var)
    if env_value is None:
        return default
    return env_value.lower() in ("true", "yes", "1")


def get_positive_numeric_env(
    env_var: str,
    default: T,
    value_type: type[T],
    *,
    warn_on_invalid: bool = True,
) -> T:
    """Get a positive numeric value from environment variable with fallback.

    Args:
        env_var: Environment variable name
        default: Default value if env var is not set or invalid
        value_type: Type to convert to (int or float)
        warn_on_invalid: Whether to log a warning when value is invalid (default: True)

    Returns:
        The parsed value from environment or default if invalid/missing/non-positive

    Examples:
        >>> get_positive_numeric_env("MY_TIMEOUT", 30, int)
        30  # Returns default if MY_TIMEOUT is not set

        >>> os.environ["MY_TIMEOUT"] = "60"
        >>> get_positive_numeric_env("MY_TIMEOUT", 30, int)
        60  # Returns parsed value

        >>> os.environ["MY_TIMEOUT"] = "invalid"
        >>> get_positive_numeric_env("MY_TIMEOUT", 30, int)
        30  # Returns default, logs warning
    """
    env_value = os.environ.get(env_var)

    # Not set - return default silently (this is normal/expected)
    if env_value is None:
        return default

    try:
        value = value_type(env_value)
        if value > 0:
            return value
        # Non-positive value
        if warn_on_invalid:
            logger.warning(
                "%s=%s is not positive, using default %s", env_var, env_value, default
            )
    except (ValueError, TypeError):
        # Invalid format
        if warn_on_invalid:
            logger.warning(
                "%s=%s is not a valid %s, using default %s",
                env_var,
                env_value,
                value_type.__name__,
                default,
            )

    return default
