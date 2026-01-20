# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# -*- coding: utf-8 -*-

"""Logging configuration utilities for nac-test framework."""

import logging
import sys
from enum import Enum

import errorhandler


class VerbosityLevel(str, Enum):
    """Supported logging verbosity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def configure_logging(
    level: str | VerbosityLevel, error_handler: errorhandler.ErrorHandler
) -> None:
    """Configure logging for nac-test framework.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        error_handler: Error handler instance to reset
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
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(log_level)

    # Reset error handler
    error_handler.reset()

    logger.debug(
        "Logging configured with level: %s (numeric: %s)", level_str, log_level
    )
