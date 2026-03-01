# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Logging configuration utilities for nac-test framework."""

import logging
import sys
from enum import Enum


class VerbosityLevel(str, Enum):
    """Supported logging verbosity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# Mapping from level name strings to Python logging level values
LOGLEVEL_NAME_TO_VALUE: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# Mapping from nac-test VerbosityLevel to Python logging level
VERBOSITY_TO_LOGLEVEL: dict[VerbosityLevel, int] = {
    VerbosityLevel.DEBUG: logging.DEBUG,
    VerbosityLevel.INFO: logging.INFO,
    VerbosityLevel.WARNING: logging.WARNING,
    VerbosityLevel.ERROR: logging.ERROR,
    VerbosityLevel.CRITICAL: logging.CRITICAL,
}


def configure_logging(level: str | VerbosityLevel) -> None:
    """Configure logging for nac-test framework.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Convert to logging level, defaulting to CRITICAL for unknown levels
    # Handle both enum values and string inputs
    if isinstance(level, VerbosityLevel):
        level_str = level.value.upper()
    else:
        level_str = str(level).upper()

    log_level = LOGLEVEL_NAME_TO_VALUE.get(level_str, logging.CRITICAL)

    # Configure root logger
    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(log_level)

    logger.debug(
        "Logging configured with level: %s (numeric: %s)", level_str, log_level
    )
