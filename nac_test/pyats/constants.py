# -*- coding: utf-8 -*-

"""PyATS-specific constants and configuration."""

# Worker calculation constants
MIN_WORKERS = 2
MAX_WORKERS = 32
MAX_WORKERS_HARD_LIMIT = 50
MEMORY_PER_WORKER_GB = 2
DEFAULT_CPU_MULTIPLIER = 2
LOAD_AVERAGE_THRESHOLD = 0.8

# Concurrency limits
DEFAULT_API_CONCURRENCY = 40
DEFAULT_SSH_CONCURRENCY = 20

# Retry configuration
RETRY_MAX_ATTEMPTS = 3
RETRY_INITIAL_DELAY = 1.0
RETRY_MAX_DELAY = 60.0
RETRY_EXPONENTIAL_BASE = 2.0

# Timeouts
DEFAULT_TEST_TIMEOUT = 300  # 5 minutes per test
CONNECTION_CLOSE_DELAY = 0.25  # seconds

# Progress reporting constants
PROGRESS_UPDATE_INTERVAL = 0.5  # seconds

# File paths
AUTH_CACHE_DIR = "/tmp/nac-test-auth-cache"
