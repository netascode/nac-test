# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Environment variable utilities for nac-test framework."""

import os
import sys
from collections.abc import Callable

from nac_test.core.constants import EXIT_ERROR
from nac_test.utils.terminal import terminal


def check_required_vars(
    required_vars: list[str],
    exit_on_missing: bool = True,
    custom_formatter: Callable[[list[str]], str] | None = None,
) -> list[str]:
    """Check for required environment variables.

    Args:
        required_vars: List of required environment variable names
        exit_on_missing: Whether to exit if variables are missing
        custom_formatter: Optional custom error formatter function

    Returns:
        List of missing variable names (empty if all present)

    Raises:
        SystemExit: If exit_on_missing is True and variables are missing
    """
    missing = [var for var in required_vars if not os.environ.get(var)]

    if missing and exit_on_missing:
        if custom_formatter:
            error_msg = custom_formatter(missing)
        else:
            error_msg = format_missing_vars_error(missing)

        print(error_msg)
        sys.exit(EXIT_ERROR)

    return missing


def format_missing_vars_error(missing_vars: list[str]) -> str:
    """Format a generic error message for missing environment variables.

    Args:
        missing_vars: List of missing environment variable names

    Returns:
        Formatted error message
    """
    lines = []
    lines.append(terminal.header("ERROR: Missing environment variable(s)"))
    lines.append("")

    for var in missing_vars:
        lines.append(f"  • {terminal.error(var)}")

    lines.append("")
    lines.append(
        terminal.info("Please set the required environment variables before running.")
    )

    return "\n".join(lines)
