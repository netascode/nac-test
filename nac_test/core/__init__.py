# -*- coding: utf-8 -*-

"""Core components shared across the nac-test framework."""

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

from nac_test.core.models import TestStatus, TestResult

__all__ = [
    # Constants
    "RETRY_MAX_ATTEMPTS",
    "RETRY_INITIAL_DELAY",
    "RETRY_MAX_DELAY",
    "RETRY_EXPONENTIAL_BASE",
    "DEFAULT_TEST_TIMEOUT",
    "CONNECTION_CLOSE_DELAY",
    "DEFAULT_API_CONCURRENCY",
    "DEFAULT_SSH_CONCURRENCY",
    "PROGRESS_UPDATE_INTERVAL",
    # Models
    "TestStatus",
    "TestResult",
]
