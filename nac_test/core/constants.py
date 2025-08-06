# -*- coding: utf-8 -*-

"""Core constants shared across the nac-test framework."""

# Retry configuration - Generic retry logic used by multiple components
RETRY_MAX_ATTEMPTS = 3
RETRY_INITIAL_DELAY = 1.0
RETRY_MAX_DELAY = 60.0
RETRY_EXPONENTIAL_BASE = 2.0

# General timeouts
DEFAULT_TEST_TIMEOUT = 21600  # 6 hours per test
CONNECTION_CLOSE_DELAY = 0.25  # seconds

# Concurrency limits - Can be used by both PyATS and Robot
DEFAULT_API_CONCURRENCY = 70
DEFAULT_SSH_CONCURRENCY = 50

# Progress reporting
PROGRESS_UPDATE_INTERVAL = 0.5  # seconds
