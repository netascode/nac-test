# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Logging configuration utilities for nac-test framework."""

import logging
import sys
from enum import Enum
from typing import TextIO, cast


class CurrentStreamHandler(logging.StreamHandler[TextIO]):
    """StreamHandler that always uses the current sys.stdout/stderr.

    This prevents 'I/O operation on closed file' errors when sys.stdout
    is replaced (e.g., by pytest's output capturing) after the handler
    is created.
    """

    def __init__(self, stream_name: str = "stdout") -> None:
        self.stream_name = stream_name  # MUST come BEFORE super().__init__()
        super().__init__()

    @property  # type: ignore[override]
    def stream(self) -> TextIO:
        """Get the current stream from sys module."""
        return cast(TextIO, getattr(sys, self.stream_name))

    @stream.setter
    def stream(self, value: TextIO) -> None:
        """Ignore attempts to set stream - we always use current sys.stdout/stderr."""
        pass


class VerbosityLevel(str, Enum):
    """Supported logging verbosity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def configure_logging(level: str | VerbosityLevel) -> None:
    """Configure logging for nac-test framework.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Map string levels to logging constants
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    # Convert to logging level, defaulting to CRITICAL for unknown levels
    # Handle both enum values and string inputs
    if isinstance(level, VerbosityLevel):
        level_str = level.value.upper()
    else:
        level_str = str(level).upper()

    log_level = level_map.get(level_str, logging.CRITICAL)

    # Configure root logger
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
