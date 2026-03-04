# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Logging configuration utilities for nac-test framework."""

import logging
import sys
from enum import Enum


class LogLevel(str, Enum):
    """Supported logging levels for nac-test framework.

    This enum provides standard Python logging levels with comparison operators.

    Inheriting from (str, Enum) ensures Typer shows the level names in --help
    and accepts string values from CLI.
    """

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    def __int__(self) -> int:
        """Return Python logging integer value (e.g., 10 for DEBUG, 20 for INFO)."""
        level: int = logging.getLevelName(self.value)
        return level

    def __le__(self, other: "LogLevel") -> bool:  # type: ignore[override]
        """Compare log levels: DEBUG < INFO < WARNING < ERROR < CRITICAL."""
        return int(self) <= int(other)

    def __lt__(self, other: "LogLevel") -> bool:  # type: ignore[override]
        """Compare log levels: DEBUG < INFO < WARNING < ERROR < CRITICAL."""
        return int(self) < int(other)

    def __ge__(self, other: "LogLevel") -> bool:  # type: ignore[override]
        """Compare log levels: DEBUG < INFO < WARNING < ERROR < CRITICAL."""
        return int(self) >= int(other)

    def __gt__(self, other: "LogLevel") -> bool:  # type: ignore[override]
        """Compare log levels: DEBUG < INFO < WARNING < ERROR < CRITICAL."""
        return int(self) > int(other)


# Default log level for CLI and orchestrators
DEFAULT_LOGLEVEL = LogLevel.WARNING


def configure_logging(level: str | LogLevel) -> None:
    """Configure logging for nac-test framework.

    Args:
        level: LogLevel enum member or string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    if isinstance(level, LogLevel):
        log_level = int(level)
        level_str = level.value
    else:
        # String path: defensive programming, not used in nac-test codebase.
        # Invalid strings fall back to DEFAULT_LOGLEVEL.
        level_str = str(level).upper()
        try:
            log_level = int(LogLevel(level_str))
        except ValueError:
            log_level = int(DEFAULT_LOGLEVEL)
            level_str = DEFAULT_LOGLEVEL.value

    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(log_level)

    logger.debug(
        "Logging configured with level: %s (numeric: %s)", level_str, log_level
    )
