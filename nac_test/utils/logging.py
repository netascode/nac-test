# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Logging configuration utilities for nac-test framework."""

import logging
import sys
from enum import Enum
from typing import Literal, TextIO, cast

_VALID_STREAMS = ("stdout", "stderr")
StreamName = Literal["stdout", "stderr"]


class CurrentStreamHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """StreamHandler that always uses the current sys.stdout/stderr.

    This prevents 'I/O operation on closed file' errors when sys.stdout
    is replaced (e.g., by pytest's output capturing) after the handler
    is created.
    """

    def __init__(self, stream_name: StreamName = "stdout") -> None:
        if stream_name not in _VALID_STREAMS:
            raise ValueError(
                f"stream_name must be 'stdout' or 'stderr', got {stream_name!r}"
            )
        # Set before property access; setter is no-op so order is for clarity
        self.stream_name = stream_name
        super().__init__()

    @property  # type: ignore[override]
    def stream(self) -> TextIO:
        """Get the current stream from sys module."""
        return cast(TextIO, getattr(sys, self.stream_name))

    @stream.setter
    def stream(self, value: TextIO) -> None:
        """Ignore attempts to set stream - we always use current sys.stdout/stderr."""
        pass


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

    # Only remove StreamHandlers pointing to stdout/stderr
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and handler.stream in (
            sys.stdout,
            sys.stderr,
        ):
            logger.removeHandler(handler)

    # Use CurrentStreamHandler to always reference the current sys.stdout
    # This prevents "I/O operation on closed file" errors in test environments
    handler = CurrentStreamHandler("stdout")
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(log_level)

    logger.debug(
        "Logging configured with level: %s (numeric: %s)", level_str, log_level
    )
