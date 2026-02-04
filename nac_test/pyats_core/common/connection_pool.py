# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Generic connection pooling for HTTP connections.

Note on Fork Safety:
    PyATS uses fork() to create task subprocesses. After fork(), the child
    process inherits class variables from the parent, but threading.Lock
    and other threading primitives are NOT fork-safe on macOS.

    This module detects fork by tracking the PID at instance creation time.
    If the current PID differs from the creation PID, we're in a forked
    child process and must reset the singleton to avoid corrupted state.

    On macOS after fork(), this class returns a SubprocessHttpClient instead
    of httpx.AsyncClient to avoid silent crashes caused by OpenSSL threading
    issues that are not fork-safe.
"""

import logging
import os
import platform
from typing import Any

import httpx

from nac_test.pyats_core.http import SubprocessHttpClient

logger = logging.getLogger(__name__)


class ConnectionPool:
    """Shared connection pool for all API tests in a process.

    Generic pool that can be used by any architecture for HTTP connections.

    Fork Safety:
        This class is fork-safe. After fork(), child processes automatically
        get a fresh instance with fresh httpx.Limits objects. This prevents
        issues with corrupted threading state or stale connections from the
        parent process.

        On macOS, when running in a forked child process, this class returns
        a SubprocessHttpClient instead of httpx.AsyncClient. This avoids
        silent crashes caused by OpenSSL threading issues after fork().
    """

    _instance: "ConnectionPool | None" = None
    _creation_pid: int | None = None

    def __new__(cls) -> "ConnectionPool":
        current_pid = os.getpid()

        # Detect fork: if PID changed, we're in a child process - reset singleton
        if cls._instance is not None and cls._creation_pid != current_pid:
            cls._instance = None
            cls._creation_pid = None

        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._creation_pid = current_pid
            # Initialize limits in __new__ to ensure it's set before __init__
            cls._instance._limits_initialized = False

        return cls._instance

    def __init__(self) -> None:
        # Use flag instead of hasattr for fork-safety
        if not getattr(self, "_limits_initialized", False):
            self.limits = httpx.Limits(
                max_connections=200, max_keepalive_connections=50, keepalive_expiry=300
            )
            self._limits_initialized = True

    def get_client(
        self,
        base_url: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        verify: bool = True,
    ) -> httpx.AsyncClient | SubprocessHttpClient:
        """Get an async HTTP client with custom headers and timeout.

        On macOS after fork(), this returns a SubprocessHttpClient to avoid
        silent crashes caused by OpenSSL threading issues. On other platforms
        or when not in a forked process, returns a standard httpx.AsyncClient.

        Args:
            base_url: Optional base URL for resolving relative URLs.
            headers: Optional headers dict (architecture-specific).
            timeout: Optional timeout settings.
            verify: SSL verification flag.

        Returns:
            Configured HTTP client instance (either httpx.AsyncClient or
            SubprocessHttpClient depending on platform and fork state).
        """
        if timeout is None:
            timeout = httpx.Timeout(30.0)

        # On macOS, httpx.AsyncClient crashes after fork() due to OpenSSL threading
        # issues that are not fork-safe. PyATS uses fork() for test parallelization,
        # and we cannot reliably detect if we're in a forked child because the nac_test
        # module is imported AFTER the fork happens.
        #
        # Solution: ALWAYS use SubprocessHttpClient on macOS for fork-safety.
        # The performance overhead is acceptable compared to silent crashes.
        if platform.system() == "Darwin":
            logger.debug("macOS detected, using SubprocessHttpClient for fork-safety")
            return SubprocessHttpClient(
                base_url=base_url,
                headers=headers,
                timeout=timeout,
                verify=verify,
            )

        # Non-macOS platforms: use standard httpx.AsyncClient for best performance
        client_kwargs: dict[str, Any] = {
            "limits": self.limits,
            "headers": headers or {},
            "timeout": timeout,
            "verify": verify,
        }

        # Only add base_url if it's not None (httpx fails with base_url=None)
        if base_url is not None:
            client_kwargs["base_url"] = base_url

        return httpx.AsyncClient(**client_kwargs)
