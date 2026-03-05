# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Shared formatting utilities for timestamps and durations.

This module provides single-source-of-truth formatting functions used
across CLI output, progress reporting, HTML reports, and file naming.
"""

from datetime import datetime

from nac_test.core.constants import PROGRESS_TIMESTAMP_FORMAT

# Microsecond-to-millisecond slice — strftime %f yields 6 digits,
# slicing off the last 3 gives millisecond precision.
_MICROSECOND_TRIM: int = -3


def format_timestamp_ms(dt: datetime | None = None) -> str:
    """Format a datetime with millisecond precision.

    Args:
        dt: Datetime to format. Defaults to now.

    Returns:
        Timestamp string like ``"2025-06-27 18:26:16.834"``.
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime(PROGRESS_TIMESTAMP_FORMAT)[:_MICROSECOND_TRIM]


def format_duration(duration_seconds: float | int | None) -> str:
    """Format a duration in seconds to a human-readable string.

    Uses smart formatting to display durations in the most readable way:
    - Less than 1 second: ``"< 1s"``
    - 1–59 seconds: ``"X.XXs"`` (e.g., ``"2.50s"``, ``"45.20s"``)
    - 1–59 minutes: ``"Xm Xs"`` (e.g., ``"1m 23s"``, ``"15m 8s"``)
    - 1+ hours: ``"Xh Xm"`` (e.g., ``"1h 5m"``, ``"2h 45m"``)

    Args:
        duration_seconds: Duration in seconds, or None.

    Returns:
        Formatted duration string, or ``"N/A"`` if duration is None.
    """
    if duration_seconds is None:
        return "N/A"

    duration = float(duration_seconds)

    if duration < 1.0:
        return "< 1s"

    if duration < 60:
        return f"{duration:.2f}s"

    if duration < 3600:
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        return f"{minutes}m {seconds}s"

    hours = int(duration // 3600)
    minutes = int((duration % 3600) // 60)
    return f"{hours}h {minutes}m"
