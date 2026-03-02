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
    # Env var helper
    _get_positive_numeric,
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


# NOTE: The following environment variables remain as undocumented internal tuning
# knobs, not exposed as CLI flags or documented in README. Consider converting to
# proper constants with CLI flags in a future release if user demand warrants it:
# - NAC_TEST_PYATS_OUTPUT_BUFFER_LIMIT
# - NAC_TEST_PYATS_SENTINEL_TIMEOUT
# - NAC_TEST_PYATS_PIPE_DRAIN_DELAY
# - NAC_TEST_PYATS_PIPE_DRAIN_TIMEOUT
# - NAC_TEST_PYATS_BATCH_SIZE
# - NAC_TEST_PYATS_BATCH_TIMEOUT
# - NAC_TEST_PYATS_QUEUE_SIZE
# - NAC_TEST_PYATS_MEMORY_LIMIT_MB

# PyATS subprocess output buffer limit
# PyATS tests can generate extremely large output lines (100KB+ JSON responses from API calls).
# asyncio's default 64KB buffer would trigger `LimitOverrunError` and cause nac-test to hang.
# Default: 10MB - configurable via NAC_TEST_PYATS_OUTPUT_BUFFER_LIMIT environment variable
PYATS_OUTPUT_BUFFER_LIMIT: int = _get_positive_numeric(
    "NAC_TEST_PYATS_OUTPUT_BUFFER_LIMIT", 10 * 1024 * 1024, int
)

# Sentinel-based IPC synchronization timeout (seconds)
# Expected sync time: <100ms under normal conditions
# This timeout protects against deadlock if sentinel mechanism fails
# Default: 5.0 seconds (50x expected latency, should never be hit under normal operation)
SENTINEL_TIMEOUT_SECONDS: float = _get_positive_numeric(
    "NAC_TEST_PYATS_SENTINEL_TIMEOUT", 5.0, float
)

# macOS subprocess pipe drain configuration (secondary fallback for backward compatibility)
# Used as fallback when sentinel-based synchronization is unavailable (e.g., old plugins
# that don't emit sentinels). Prefer sentinel-based sync when possible.
# macOS has different pipe buffering behavior that requires extra time for kernel flush
# Default: 100ms on macOS (balances reliability vs performance), 1ms on Linux
# These values can be overridden via environment variables for CI tuning
_pipe_drain_default = 0.1 if IS_MACOS else 0.001
PIPE_DRAIN_DELAY_SECONDS: float = _get_positive_numeric(
    "NAC_TEST_PYATS_PIPE_DRAIN_DELAY", _pipe_drain_default, float
)
PIPE_DRAIN_TIMEOUT_SECONDS: float = _get_positive_numeric(
    "NAC_TEST_PYATS_PIPE_DRAIN_TIMEOUT", 2.0, float
)

# Batching reporter configuration
# Controls how PyATS reporter messages are batched for efficient transmission
# Batch size: number of messages accumulated before flush (default: 200)
BATCH_SIZE: int = _get_positive_numeric("NAC_TEST_PYATS_BATCH_SIZE", 200, int)

# Batch timeout: seconds before auto-flush even if batch incomplete (default: 0.5s)
BATCH_TIMEOUT_SECONDS: float = _get_positive_numeric(
    "NAC_TEST_PYATS_BATCH_TIMEOUT", 0.5, float
)

# Overflow queue size: maximum overflow queue size for burst handling (default: 5000)
OVERFLOW_QUEUE_SIZE: int = _get_positive_numeric("NAC_TEST_PYATS_QUEUE_SIZE", 5000, int)

# Overflow memory limit: maximum memory for overflow queue in MB (default: 500MB)
OVERFLOW_MEMORY_LIMIT_MB: int = _get_positive_numeric(
    "NAC_TEST_PYATS_MEMORY_LIMIT_MB", 500, int
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
    "PYATS_OUTPUT_BUFFER_LIMIT",
    # Platform detection, sentinel sync, and pipe drain configuration
    "IS_MACOS",
    "IS_UNSUPPORTED_MACOS_PYTHON",
    "SENTINEL_TIMEOUT_SECONDS",
    "PIPE_DRAIN_DELAY_SECONDS",
    "PIPE_DRAIN_TIMEOUT_SECONDS",
    # Batching reporter
    "BATCH_SIZE",
    "BATCH_TIMEOUT_SECONDS",
    "OVERFLOW_QUEUE_SIZE",
    "OVERFLOW_MEMORY_LIMIT_MB",
]
