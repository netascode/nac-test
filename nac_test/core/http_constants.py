# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""HTTP status code constants shared across the nac-test framework.

This module provides standardized HTTP status code range boundaries used
for response classification and error handling throughout the framework.
"""

# HTTP status code range boundaries - single source of truth
HTTP_STATUS_SUCCESS_MIN: int = 200
HTTP_STATUS_SUCCESS_MAX: int = 299
HTTP_STATUS_REDIRECT_MIN: int = 300
HTTP_STATUS_REDIRECT_MAX: int = 399
HTTP_STATUS_CLIENT_ERROR_MIN: int = 400
HTTP_STATUS_CLIENT_ERROR_MAX: int = 499
HTTP_STATUS_SERVER_ERROR_MIN: int = 500
HTTP_STATUS_SERVER_ERROR_MAX: int = 599

# Authentication failure status codes
HTTP_AUTH_FAILURE_CODES: tuple[int, ...] = (401, 403)

# Service unavailable status codes (treat as unreachable)
HTTP_SERVICE_UNAVAILABLE_CODES: tuple[int, ...] = (408, 429, 503, 504)
