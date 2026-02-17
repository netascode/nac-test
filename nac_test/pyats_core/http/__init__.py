# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Fork-safe HTTP client package for macOS compatibility.

This package provides HTTP client implementations that are safe to use
after fork() on macOS, where standard httpx/OpenSSL clients crash due to
threading primitive issues.
"""

from nac_test.core.http_constants import (
    HTTP_STATUS_CLIENT_ERROR_MAX,
    HTTP_STATUS_CLIENT_ERROR_MIN,
    HTTP_STATUS_REDIRECT_MAX,
    HTTP_STATUS_REDIRECT_MIN,
    HTTP_STATUS_SERVER_ERROR_MAX,
    HTTP_STATUS_SERVER_ERROR_MIN,
    HTTP_STATUS_SUCCESS_MAX,
    HTTP_STATUS_SUCCESS_MIN,
)
from nac_test.pyats_core.http.subprocess_client import (
    SUBPROCESS_BUFFER_TIMEOUT_SECONDS,
    SUBPROCESS_HTTP_TIMEOUT_SECONDS,
    SubprocessHttpClient,
    SubprocessResponse,
)

__all__ = [
    "SubprocessResponse",
    "SubprocessHttpClient",
    "HTTP_STATUS_SUCCESS_MIN",
    "HTTP_STATUS_SUCCESS_MAX",
    "HTTP_STATUS_REDIRECT_MIN",
    "HTTP_STATUS_REDIRECT_MAX",
    "HTTP_STATUS_CLIENT_ERROR_MIN",
    "HTTP_STATUS_CLIENT_ERROR_MAX",
    "HTTP_STATUS_SERVER_ERROR_MIN",
    "HTTP_STATUS_SERVER_ERROR_MAX",
    "SUBPROCESS_HTTP_TIMEOUT_SECONDS",
    "SUBPROCESS_BUFFER_TIMEOUT_SECONDS",
]
