# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Core constants shared across the nac-test framework."""

import platform
import sys

from nac_test._env import get_bool_env, get_positive_numeric_env

# Retry configuration - Generic retry logic used by multiple components
RETRY_MAX_ATTEMPTS: int = 3
RETRY_INITIAL_DELAY: float = 1.0
RETRY_MAX_DELAY: float = 60.0
RETRY_EXPONENTIAL_BASE: float = 2.0

# General timeouts
DEFAULT_TEST_TIMEOUT: int = 21600  # 6 hours per test
CONNECTION_CLOSE_DELAY: float = 0.25  # seconds

# Concurrency limits - Can be used by both PyATS and Robot
# Can be overridden via environment variables
DEFAULT_API_CONCURRENCY: int = get_positive_numeric_env(
    "NAC_TEST_PYATS_API_CONCURRENCY", 55, int
)
DEFAULT_SSH_CONCURRENCY: int = get_positive_numeric_env(
    "NAC_TEST_PYATS_SSH_CONCURRENCY", 20, int
)
# Progress reporting
PROGRESS_UPDATE_INTERVAL: float = 0.5  # seconds

# Debug mode - enables progressive disclosure of error details
# Set NAC_TEST_DEBUG=true for developer-level error context
DEBUG_MODE: bool = get_bool_env("NAC_TEST_DEBUG")


# Test-level parallelization control for Robot Framework
# Set NAC_TEST_DISABLE_TESTLEVELSPLIT=true to disable test-level parallelization
DISABLE_TESTLEVELSPLIT: bool = get_bool_env("NAC_TEST_DISABLE_TESTLEVELSPLIT")


# Exit codes
# Note: EXIT_SUCCESS (0) is intentionally not defined here - zero is a universal
# POSIX convention that never changes, so a named constant adds no clarity.
EXIT_INVALID_ARGS: int = (
    2  # Invalid nac-test arguments (aligns with POSIX/Typer convention)
)
EXIT_FAILURE_CAP: int = 250  # Maximum failure count reported (1-250)
EXIT_DATA_ERROR: int = 252  # Invalid Robot Framework arguments OR no tests found (matches Robot Framework naming)
EXIT_INTERRUPTED: int = 253  # Execution was interrupted (Ctrl+C, etc.)
EXIT_ERROR: int = 255  # Infrastructure/execution errors occurred

# Reason string used in TestResults.not_run() for dry-run
DRY_RUN_REASON = "dry-run mode"

# Output directory structure - single source of truth for directory layout
# These define the standardized paths for test results and reports
PYATS_RESULTS_DIRNAME: str = "pyats_results"
ROBOT_RESULTS_DIRNAME: str = "robot_results"
HTML_REPORTS_DIRNAME: str = "html_reports"
SUMMARY_REPORT_FILENAME: str = "summary_report.html"
COMBINED_SUMMARY_FILENAME: str = "combined_summary.html"
OUTPUT_XML: str = "output.xml"
LOG_HTML: str = "log.html"
REPORT_HTML: str = "report.html"
XUNIT_XML: str = "xunit.xml"

# Platform detection
IS_MACOS: bool = platform.system() == "Darwin"

# macOS requires Python 3.12+.
IS_UNSUPPORTED_MACOS_PYTHON: bool = IS_MACOS and sys.version_info < (3, 12)
