# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""PyATS-specific constants and configuration."""

import os
import tempfile

from nac_test.core.constants import (
    CONNECTION_CLOSE_DELAY,
    # Concurrency
    DEFAULT_API_CONCURRENCY,
    DEFAULT_SSH_CONCURRENCY,
    # Timeouts
    DEFAULT_TEST_TIMEOUT,
    # Platform detection
    IS_MACOS,
    IS_UNSUPPORTED_MACOS_PYTHON,
    # Progress
    PROGRESS_UPDATE_INTERVAL,
    RETRY_EXPONENTIAL_BASE,
    RETRY_INITIAL_DELAY,
    # Retry configuration
    RETRY_MAX_ATTEMPTS,
    RETRY_MAX_DELAY,
)

# PyATS-specific worker calculation constants
MIN_WORKERS = 2
MAX_WORKERS = 32
MAX_WORKERS_HARD_LIMIT = 50
MEMORY_PER_WORKER_GB = 0.35
DEFAULT_CPU_MULTIPLIER = 2
LOAD_AVERAGE_THRESHOLD = 0.8

# PyATS-specific file paths
AUTH_CACHE_DIR = os.path.join(tempfile.gettempdir(), "nac-test-auth-cache")

# pushed to pyats device connection settings to speed up disconnects (default is 10s/1s)
PYATS_POST_DISCONNECT_WAIT_SECONDS: int = 0
PYATS_GRACEFUL_DISCONNECT_WAIT_SECONDS: int = 0

# Multi-job execution configuration (to avoid reporter crashes)
TESTS_PER_JOB = 15  # Reduced from 20 for safety margin - each test ~1500 steps
MAX_PARALLEL_JOBS = 2  # Conservative parallelism to avoid resource exhaustion
JOB_RETRY_ATTEMPTS = 1  # Retry failed jobs once

# PyATS subprocess output handling
DEFAULT_BUFFER_LIMIT = 10 * 1024 * 1024  # 10MB - handles large PyATS output lines

# Sentinel-based IPC synchronization timeout (seconds)
# Expected sync time: <100ms under normal conditions
# This timeout protects against deadlock if sentinel mechanism fails
# Default: 5.0 seconds (50x expected latency, should never be hit under normal operation)
_sentinel_timeout_env = os.getenv("NAC_TEST_SENTINEL_TIMEOUT", "5.0")
try:
    SENTINEL_TIMEOUT_SECONDS: float = float(_sentinel_timeout_env)
    if SENTINEL_TIMEOUT_SECONDS <= 0:
        raise ValueError("Timeout must be positive")
except ValueError:
    SENTINEL_TIMEOUT_SECONDS = 5.0  # Fallback to safe default

# macOS subprocess pipe drain configuration (secondary fallback for backward compatibility)
# Used as fallback when sentinel-based synchronization is unavailable (e.g., old plugins
# that don't emit sentinels). Prefer sentinel-based sync when possible.
# macOS has different pipe buffering behavior that requires extra time for kernel flush
# Default: 100ms on macOS (balances reliability vs performance), 1ms on Linux
# These values can be overridden via environment variables for CI tuning
PIPE_DRAIN_DELAY_SECONDS: float = float(
    os.getenv("NAC_TEST_PIPE_DRAIN_DELAY", "0.1" if IS_MACOS else "0.001")
)
PIPE_DRAIN_TIMEOUT_SECONDS: float = float(
    os.getenv("NAC_TEST_PIPE_DRAIN_TIMEOUT", "2.0")
)

# Re-export all constants for backward compatibility
__all__ = [
    # From core
    "RETRY_MAX_ATTEMPTS",
    "RETRY_INITIAL_DELAY",
    "RETRY_MAX_DELAY",
    "RETRY_EXPONENTIAL_BASE",
    "DEFAULT_TEST_TIMEOUT",
    "CONNECTION_CLOSE_DELAY",
    "DEFAULT_API_CONCURRENCY",
    "DEFAULT_SSH_CONCURRENCY",
    "PROGRESS_UPDATE_INTERVAL",
    # PyATS-specific
    "MIN_WORKERS",
    "MAX_WORKERS",
    "MAX_WORKERS_HARD_LIMIT",
    "MEMORY_PER_WORKER_GB",
    "DEFAULT_CPU_MULTIPLIER",
    "LOAD_AVERAGE_THRESHOLD",
    "AUTH_CACHE_DIR",
    "PYATS_POST_DISCONNECT_WAIT_SECONDS",
    "PYATS_GRACEFUL_DISCONNECT_WAIT_SECONDS",
    # Multi-job execution
    "TESTS_PER_JOB",
    "MAX_PARALLEL_JOBS",
    "JOB_RETRY_ATTEMPTS",
    # Subprocess handling
    "DEFAULT_BUFFER_LIMIT",
    # Platform detection, sentinel sync, and pipe drain configuration
    "IS_MACOS",
    "IS_UNSUPPORTED_MACOS_PYTHON",
    "SENTINEL_TIMEOUT_SECONDS",
    "PIPE_DRAIN_DELAY_SECONDS",
    "PIPE_DRAIN_TIMEOUT_SECONDS",
]
