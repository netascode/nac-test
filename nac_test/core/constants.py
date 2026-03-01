# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Core constants shared across the nac-test framework."""

import os
import platform
import sys
from typing import TypeVar

T = TypeVar("T", int, float)


# Helper function for parsing environment variables with positive value validation.
# Defined here (not in utils/) to avoid circular imports: utils/environment.py imports
# from core/constants.py, so we can't import back from utils/ at module load time.
def _get_positive_numeric(env_var: str, default: T, value_type: type[T]) -> T:
    """Get a positive numeric value from environment variable with fallback.

    Args:
        env_var: Environment variable name
        default: Default value if env var is not set or invalid
        value_type: Type to convert to (int or float)

    Returns:
        The parsed value from environment or default if invalid/missing/non-positive
    """
    env_value = os.getenv(env_var, str(default))
    try:
        value = value_type(env_value)
        return value if value > 0 else default
    except (ValueError, TypeError):
        return default


# Retry configuration - Generic retry logic used by multiple components
RETRY_MAX_ATTEMPTS = 3
RETRY_INITIAL_DELAY = 1.0
RETRY_MAX_DELAY = 60.0
RETRY_EXPONENTIAL_BASE = 2.0

# General timeouts
DEFAULT_TEST_TIMEOUT = 21600  # 6 hours per test
CONNECTION_CLOSE_DELAY = 0.25  # seconds

# Concurrency limits - Can be used by both PyATS and Robot
# Can be overridden via environment variables
DEFAULT_API_CONCURRENCY = _get_positive_numeric(
    "NAC_TEST_PYATS_API_CONCURRENCY", 55, int
)
DEFAULT_SSH_CONCURRENCY = _get_positive_numeric(
    "NAC_TEST_PYATS_SSH_CONCURRENCY", 20, int
)
# Progress reporting
PROGRESS_UPDATE_INTERVAL = 0.5  # seconds

# Debug mode - enables progressive disclosure of error details
# Set NAC_TEST_DEBUG=true for developer-level error context
DEBUG_MODE = os.environ.get("NAC_TEST_DEBUG", "").lower() == "true"

# Exit codes
# Note: EXIT_SUCCESS (0) is intentionally not defined here - zero is a universal
# POSIX convention that never changes, so a named constant adds no clarity.
EXIT_INVALID_ARGS = 2  # Invalid nac-test arguments (aligns with POSIX/Typer convention)
EXIT_FAILURE_CAP = 250  # Maximum failure count reported (1-250)
EXIT_DATA_ERROR = 252  # Invalid Robot Framework arguments OR no tests found (matches Robot Framework naming)
EXIT_INTERRUPTED = 253  # Execution was interrupted (Ctrl+C, etc.)
EXIT_ERROR = 255  # Infrastructure/execution errors occurred

# Output directory structure - single source of truth for directory layout
# These define the standardized paths for test results and reports
PYATS_RESULTS_DIRNAME = "pyats_results"
ROBOT_RESULTS_DIRNAME = "robot_results"
HTML_REPORTS_DIRNAME = "html_reports"
SUMMARY_REPORT_FILENAME = "summary_report.html"
COMBINED_SUMMARY_FILENAME = "combined_summary.html"
OUTPUT_XML = "output.xml"
LOG_HTML = "log.html"
REPORT_HTML = "report.html"
XUNIT_XML = "xunit.xml"

# Platform detection
IS_MACOS: bool = platform.system() == "Darwin"

# macOS requires Python 3.12+.
IS_UNSUPPORTED_MACOS_PYTHON: bool = IS_MACOS and sys.version_info < (3, 12)
