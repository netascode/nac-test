# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for SubprocessResponse and SubprocessHttpClient.

This module tests actual business logic for the fork-safe HTTP client:
1. SubprocessResponse.raise_for_status() error handling behavior
2. SubprocessHttpClient URL resolution logic
3. ConnectionPool platform-specific client selection

NOTE: The following test classes were removed as they tested Python stdlib:
- TestSubprocessResponseIsSuccess (tests >= operator on integers)
- TestSubprocessResponseIsRedirect (tests >= operator on integers)
- TestSubprocessResponseIsClientError (tests >= operator on integers)
- TestSubprocessResponseIsServerError (tests >= operator on integers)
- TestSubprocessResponseIsError (tests >= operator on integers)
- TestSubprocessResponseContentMethods (tests bytes.decode() and json.loads())
- TestSubprocessHttpClientInitialization (tests dict assignment)
- TestSubprocessHttpClientTimeoutExtraction (tests attribute access)
- TestSubprocessHttpClientAsyncContextManager (tests __aenter__ returns self)
"""

from typing import TYPE_CHECKING

import httpx
import pytest

from nac_test.pyats_core.common.connection_pool import ConnectionPool
from nac_test.pyats_core.http import (
    SubprocessHttpClient,
    SubprocessResponse,
)

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


class TestSubprocessResponseRaiseForStatus:
    """Tests for SubprocessResponse.raise_for_status() method - actual error handling."""

    @pytest.mark.parametrize("status_code", [200, 201, 204, 301, 302])
    def test_does_not_raise_for_non_error_status(self, status_code: int) -> None:
        """Verify raise_for_status() does not raise for non-error status codes."""
        response = SubprocessResponse(
            status_code=status_code,
            _content=b"",
            _headers_dict={},
            url="https://example.com/test",
        )
        # Should not raise
        response.raise_for_status()

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 500, 502, 503])
    def test_raises_http_status_error_for_error_status(self, status_code: int) -> None:
        """Verify raise_for_status() raises HTTPStatusError for error status codes."""
        test_url = "https://example.com/test"
        response = SubprocessResponse(
            status_code=status_code,
            _content=b"Error response body",
            _headers_dict={"Content-Type": "text/plain"},
            url=test_url,
        )
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            response.raise_for_status()

        assert str(status_code) in str(exc_info.value)
        assert test_url in str(exc_info.value)


class TestSubprocessHttpClientUrlResolution:
    """Tests for SubprocessHttpClient URL resolution - actual business logic."""

    def test_absolute_url_returned_unchanged(self) -> None:
        """Verify absolute URLs are returned without modification."""
        client = SubprocessHttpClient(base_url="https://api.example.com")
        assert client._resolve_url("https://other.com/path") == "https://other.com/path"

    def test_relative_url_resolved_against_base_url(self) -> None:
        """Verify relative URLs are resolved against base_url."""
        client = SubprocessHttpClient(base_url="https://api.example.com")
        assert client._resolve_url("/endpoint") == "https://api.example.com/endpoint"

    def test_base_url_trailing_slash_stripped(self) -> None:
        """Verify trailing slash is stripped from base_url."""
        client = SubprocessHttpClient(base_url="https://api.example.com/")
        assert client._resolve_url("/endpoint") == "https://api.example.com/endpoint"

    def test_relative_url_without_base_url_returned_as_is(self) -> None:
        """Verify relative URLs without base_url are returned unchanged."""
        client = SubprocessHttpClient(base_url=None)
        assert client._resolve_url("/endpoint") == "/endpoint"


class TestConnectionPoolPlatformSelection:
    """Tests for ConnectionPool client selection based on platform - critical behavior."""

    def test_returns_subprocess_client_on_darwin(self, mocker: "MockerFixture") -> None:
        """Verify SubprocessHttpClient is returned on macOS (fork-safety)."""
        mocker.patch(
            "nac_test.pyats_core.common.connection_pool.platform.system",
            return_value="Darwin",
        )
        # Reset singleton to pick up new platform
        ConnectionPool._instance = None
        ConnectionPool._creation_pid = None

        pool = ConnectionPool()
        client = pool.get_client(base_url="https://example.com")

        assert isinstance(client, SubprocessHttpClient)

    def test_returns_httpx_client_on_linux(self, mocker: "MockerFixture") -> None:
        """Verify httpx.AsyncClient is returned on Linux."""
        mocker.patch(
            "nac_test.pyats_core.common.connection_pool.platform.system",
            return_value="Linux",
        )
        # Reset singleton to pick up new platform
        ConnectionPool._instance = None
        ConnectionPool._creation_pid = None

        pool = ConnectionPool()
        client = pool.get_client(base_url="https://example.com")

        assert isinstance(client, httpx.AsyncClient)

    def test_returns_httpx_client_on_windows(self, mocker: "MockerFixture") -> None:
        """Verify httpx.AsyncClient is returned on Windows."""
        mocker.patch(
            "nac_test.pyats_core.common.connection_pool.platform.system",
            return_value="Windows",
        )
        # Reset singleton to pick up new platform
        ConnectionPool._instance = None
        ConnectionPool._creation_pid = None

        pool = ConnectionPool()
        client = pool.get_client(base_url="https://example.com")

        assert isinstance(client, httpx.AsyncClient)
