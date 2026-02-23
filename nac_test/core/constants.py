# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Core constants shared across the nac-test framework."""

import os
import platform
import sys

# Retry configuration - Generic retry logic used by multiple components
RETRY_MAX_ATTEMPTS = 3
RETRY_INITIAL_DELAY = 1.0
RETRY_MAX_DELAY = 60.0
RETRY_EXPONENTIAL_BASE = 2.0

# General timeouts
DEFAULT_TEST_TIMEOUT = 21600  # 6 hours per test
CONNECTION_CLOSE_DELAY = 0.25  # seconds

# Concurrency limits - Can be used by both PyATS and Robot
# Can be overridden via NAC_API_CONCURRENCY environment variable
DEFAULT_API_CONCURRENCY = int(os.environ.get("NAC_API_CONCURRENCY", "55"))
DEFAULT_SSH_CONCURRENCY = int(os.environ.get("NAC_SSH_CONCURRENCY", "20"))

# Progress reporting
PROGRESS_UPDATE_INTERVAL = 0.5  # seconds

# Debug mode - enables progressive disclosure of error details
# Set NAC_TEST_DEBUG=true for developer-level error context
DEBUG_MODE = os.environ.get("NAC_TEST_DEBUG", "").lower() == "true"

# Output directory structure - single source of truth for directory layout
# These define the standardized paths for test results and reports
PYATS_RESULTS_DIRNAME = "pyats_results"
ROBOT_RESULTS_DIRNAME = "robot_results"
HTML_REPORTS_DIRNAME = "html_reports"
SUMMARY_REPORT_FILENAME = "summary_report.html"
COMBINED_SUMMARY_FILENAME = "combined_summary.html"

# Platform detection
IS_MACOS: bool = platform.system() == "Darwin"

# macOS requires Python 3.12+.
IS_UNSUPPORTED_MACOS_PYTHON: bool = IS_MACOS and sys.version_info < (3, 12)
