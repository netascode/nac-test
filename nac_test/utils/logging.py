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

    @property
    def _int(self) -> int:
        """Return Python logging integer value (e.g., 10 for DEBUG, 20 for INFO)."""
        return logging._nameToLevel[self.value]

    def __le__(self, other: "LogLevel") -> bool:  # type: ignore[override]
        """Compare log levels: DEBUG < INFO < WARNING < ERROR < CRITICAL."""
        return self._int <= other._int

    def __lt__(self, other: "LogLevel") -> bool:  # type: ignore[override]
        """Compare log levels: DEBUG < INFO < WARNING < ERROR < CRITICAL."""
        return self._int < other._int

    def __ge__(self, other: "LogLevel") -> bool:  # type: ignore[override]
        """Compare log levels: DEBUG < INFO < WARNING < ERROR < CRITICAL."""
        return self._int >= other._int

    def __gt__(self, other: "LogLevel") -> bool:  # type: ignore[override]
        """Compare log levels: DEBUG < INFO < WARNING < ERROR < CRITICAL."""
        return self._int > other._int


# Backwards compatibility alias (deprecated)
VerbosityLevel = LogLevel

# Default log level for CLI and orchestrators
DEFAULT_LOGLEVEL = LogLevel.WARNING


def configure_logging(level: str | LogLevel) -> None:
    """Configure logging for nac-test framework.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    if isinstance(level, LogLevel):
        log_level = level._int
        level_str = level.value
    else:
        level_str = str(level).upper()
        try:
            log_level = LogLevel(level_str)._int
        except ValueError:
            log_level = logging.CRITICAL

    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(log_level)

    logger.debug(
        "Logging configured with level: %s (numeric: %s)", level_str, log_level
    )
