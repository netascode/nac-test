"""Generic connection pooling for HTTP connections."""

import threading
from typing import Any

import httpx


class ConnectionPool:
    """Shared connection pool for all API tests in a process

    Generic pool that can be used by any architecture for HTTP connections
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls) -> "ConnectionPool":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "limits"):
            self.limits = httpx.Limits(
                max_connections=200, max_keepalive_connections=50, keepalive_expiry=300
            )

    def get_client(
        self,
        base_url: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        verify: bool = True,
    ) -> httpx.AsyncClient:
        """Get an async HTTP client with custom headers and timeout

        Args:
            base_url: Optional base URL for resolving relative URLs
            headers: Optional headers dict (architecture-specific)
            timeout: Optional timeout settings
            verify: SSL verification flag

        Returns:
            Configured httpx.AsyncClient instance
        """
        if timeout is None:
            timeout = httpx.Timeout(30.0)

        # Build kwargs dict, only including base_url if it's not None
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
