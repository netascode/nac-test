# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# -*- coding: utf-8 -*-

"""PyATS-specific constants and configuration."""

from nac_test.core.constants import (
    CONNECTION_CLOSE_DELAY,
    # Concurrency
    DEFAULT_API_CONCURRENCY,
    DEFAULT_SSH_CONCURRENCY,
    # Timeouts
    DEFAULT_TEST_TIMEOUT,
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
MEMORY_PER_WORKER_GB = 2
DEFAULT_CPU_MULTIPLIER = 2
LOAD_AVERAGE_THRESHOLD = 0.8

# PyATS-specific file paths
AUTH_CACHE_DIR = "/tmp/nac-test-auth-cache"

# Multi-job execution configuration (to avoid reporter crashes)
TESTS_PER_JOB = 15  # Reduced from 20 for safety margin - each test ~1500 steps
MAX_PARALLEL_JOBS = 2  # Conservative parallelism to avoid resource exhaustion
JOB_RETRY_ATTEMPTS = 1  # Retry failed jobs once

# PyATS subprocess output handling
DEFAULT_BUFFER_LIMIT = 10 * 1024 * 1024  # 10MB - handles large PyATS output lines

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
    # Multi-job execution
    "TESTS_PER_JOB",
    "MAX_PARALLEL_JOBS",
    "JOB_RETRY_ATTEMPTS",
    # Subprocess handling
    "DEFAULT_BUFFER_LIMIT",
]
