# -*- coding: utf-8 -*-

"""PyATS-specific constants and configuration."""

from nac_test.core.constants import (
    # Retry configuration
    RETRY_MAX_ATTEMPTS,
    RETRY_INITIAL_DELAY,
    RETRY_MAX_DELAY,
    RETRY_EXPONENTIAL_BASE,
    # Timeouts
    DEFAULT_TEST_TIMEOUT,
    CONNECTION_CLOSE_DELAY,
    # Concurrency
    DEFAULT_API_CONCURRENCY,
    DEFAULT_SSH_CONCURRENCY,
    # Progress
    PROGRESS_UPDATE_INTERVAL,
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
]
