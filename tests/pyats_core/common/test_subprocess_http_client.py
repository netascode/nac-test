# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for SubprocessResponse and SubprocessHttpClient.

This module tests the fork-safe HTTP client implementation used on macOS
to avoid OpenSSL threading crashes after fork(). The tests cover:

1. SubprocessResponse convenience properties (is_success, is_error, etc.)
2. SubprocessResponse.raise_for_status() behavior
3. SubprocessHttpClient URL resolution
4. SubprocessHttpClient header merging
5. SubprocessHttpClient timeout extraction
6. ConnectionPool platform-specific client selection
"""

from typing import TYPE_CHECKING

import httpx
import pytest

from nac_test.pyats_core.common.connection_pool import (
    HTTP_STATUS_CLIENT_ERROR_MAX,
    HTTP_STATUS_CLIENT_ERROR_MIN,
    HTTP_STATUS_REDIRECT_MAX,
    HTTP_STATUS_REDIRECT_MIN,
    HTTP_STATUS_SERVER_ERROR_MAX,
    HTTP_STATUS_SERVER_ERROR_MIN,
    HTTP_STATUS_SUCCESS_MAX,
    HTTP_STATUS_SUCCESS_MIN,
    ConnectionPool,
    SubprocessHttpClient,
    SubprocessResponse,
)

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


# =============================================================================
# SubprocessResponse Property Tests
# =============================================================================


class TestSubprocessResponseIsSuccess:
    """Tests for SubprocessResponse.is_success property."""

    @pytest.mark.parametrize(
        "status_code",
        [
            HTTP_STATUS_SUCCESS_MIN,  # 200
            201,  # Created
            204,  # No Content
            HTTP_STATUS_SUCCESS_MAX,  # 299
        ],
    )
    def test_returns_true_for_2xx_status_codes(self, status_code: int) -> None:
        """Verify is_success returns True for 2xx status codes."""
        response = SubprocessResponse(
            status_code=status_code,
            _content=b"",
            _headers_dict={},
            url="https://example.com",
        )
        assert response.is_success is True

    @pytest.mark.parametrize(
        "status_code",
        [
            199,  # Below 2xx
            300,  # Redirect
            400,  # Client error
            500,  # Server error
        ],
    )
    def test_returns_false_for_non_2xx_status_codes(self, status_code: int) -> None:
        """Verify is_success returns False for non-2xx status codes."""
        response = SubprocessResponse(
            status_code=status_code,
            _content=b"",
            _headers_dict={},
            url="https://example.com",
        )
        assert response.is_success is False


class TestSubprocessResponseIsRedirect:
    """Tests for SubprocessResponse.is_redirect property."""

    @pytest.mark.parametrize(
        "status_code",
        [
            HTTP_STATUS_REDIRECT_MIN,  # 300
            301,  # Moved Permanently
            302,  # Found
            307,  # Temporary Redirect
            HTTP_STATUS_REDIRECT_MAX,  # 399
        ],
    )
    def test_returns_true_for_3xx_status_codes(self, status_code: int) -> None:
        """Verify is_redirect returns True for 3xx status codes."""
        response = SubprocessResponse(
            status_code=status_code,
            _content=b"",
            _headers_dict={},
            url="https://example.com",
        )
        assert response.is_redirect is True

    @pytest.mark.parametrize(
        "status_code",
        [
            200,  # Success
            299,  # End of 2xx
            400,  # Client error
        ],
    )
    def test_returns_false_for_non_3xx_status_codes(self, status_code: int) -> None:
        """Verify is_redirect returns False for non-3xx status codes."""
        response = SubprocessResponse(
            status_code=status_code,
            _content=b"",
            _headers_dict={},
            url="https://example.com",
        )
        assert response.is_redirect is False


class TestSubprocessResponseIsClientError:
    """Tests for SubprocessResponse.is_client_error property."""

    @pytest.mark.parametrize(
        "status_code",
        [
            HTTP_STATUS_CLIENT_ERROR_MIN,  # 400
            401,  # Unauthorized
            403,  # Forbidden
            404,  # Not Found
            HTTP_STATUS_CLIENT_ERROR_MAX,  # 499
        ],
    )
    def test_returns_true_for_4xx_status_codes(self, status_code: int) -> None:
        """Verify is_client_error returns True for 4xx status codes."""
        response = SubprocessResponse(
            status_code=status_code,
            _content=b"",
            _headers_dict={},
            url="https://example.com",
        )
        assert response.is_client_error is True

    @pytest.mark.parametrize(
        "status_code",
        [
            200,  # Success
            399,  # End of 3xx
            500,  # Server error
        ],
    )
    def test_returns_false_for_non_4xx_status_codes(self, status_code: int) -> None:
        """Verify is_client_error returns False for non-4xx status codes."""
        response = SubprocessResponse(
            status_code=status_code,
            _content=b"",
            _headers_dict={},
            url="https://example.com",
        )
        assert response.is_client_error is False


class TestSubprocessResponseIsServerError:
    """Tests for SubprocessResponse.is_server_error property."""

    @pytest.mark.parametrize(
        "status_code",
        [
            HTTP_STATUS_SERVER_ERROR_MIN,  # 500
            501,  # Not Implemented
            502,  # Bad Gateway
            503,  # Service Unavailable
            HTTP_STATUS_SERVER_ERROR_MAX,  # 599
        ],
    )
    def test_returns_true_for_5xx_status_codes(self, status_code: int) -> None:
        """Verify is_server_error returns True for 5xx status codes."""
        response = SubprocessResponse(
            status_code=status_code,
            _content=b"",
            _headers_dict={},
            url="https://example.com",
        )
        assert response.is_server_error is True

    @pytest.mark.parametrize(
        "status_code",
        [
            200,  # Success
            499,  # End of 4xx
            600,  # Above 5xx
        ],
    )
    def test_returns_false_for_non_5xx_status_codes(self, status_code: int) -> None:
        """Verify is_server_error returns False for non-5xx status codes."""
        response = SubprocessResponse(
            status_code=status_code,
            _content=b"",
            _headers_dict={},
            url="https://example.com",
        )
        assert response.is_server_error is False


class TestSubprocessResponseIsError:
    """Tests for SubprocessResponse.is_error property."""

    @pytest.mark.parametrize(
        "status_code",
        [
            HTTP_STATUS_CLIENT_ERROR_MIN,  # 400
            404,  # Not Found
            HTTP_STATUS_CLIENT_ERROR_MAX,  # 499
            HTTP_STATUS_SERVER_ERROR_MIN,  # 500
            503,  # Service Unavailable
            HTTP_STATUS_SERVER_ERROR_MAX,  # 599
        ],
    )
    def test_returns_true_for_4xx_and_5xx_status_codes(self, status_code: int) -> None:
        """Verify is_error returns True for 4xx and 5xx status codes."""
        response = SubprocessResponse(
            status_code=status_code,
            _content=b"",
            _headers_dict={},
            url="https://example.com",
        )
        assert response.is_error is True

    @pytest.mark.parametrize(
        "status_code",
        [
            200,  # Success
            301,  # Redirect
            399,  # End of 3xx
        ],
    )
    def test_returns_false_for_non_error_status_codes(self, status_code: int) -> None:
        """Verify is_error returns False for non-error status codes."""
        response = SubprocessResponse(
            status_code=status_code,
            _content=b"",
            _headers_dict={},
            url="https://example.com",
        )
        assert response.is_error is False


class TestSubprocessResponseRaiseForStatus:
    """Tests for SubprocessResponse.raise_for_status() method."""

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


class TestSubprocessResponseContentMethods:
    """Tests for SubprocessResponse content access methods."""

    def test_text_decodes_utf8_content(self) -> None:
        """Verify text property decodes UTF-8 content correctly."""
        content = "Hello, World!"
        response = SubprocessResponse(
            status_code=200,
            _content=content.encode("utf-8"),
            _headers_dict={},
            url="https://example.com",
        )
        assert response.text == content

    def test_content_returns_raw_bytes(self) -> None:
        """Verify content property returns raw bytes."""
        raw_bytes = b"\x00\x01\x02\x03"
        response = SubprocessResponse(
            status_code=200,
            _content=raw_bytes,
            _headers_dict={},
            url="https://example.com",
        )
        assert response.content == raw_bytes

    def test_json_parses_json_content(self) -> None:
        """Verify json() method parses JSON content correctly."""
        data = {"key": "value", "number": 42}
        response = SubprocessResponse(
            status_code=200,
            _content=b'{"key": "value", "number": 42}',
            _headers_dict={},
            url="https://example.com",
        )
        assert response.json() == data

    def test_headers_returns_httpx_headers_object(self) -> None:
        """Verify headers property returns httpx.Headers object."""
        headers_dict = {"Content-Type": "application/json", "X-Custom": "value"}
        response = SubprocessResponse(
            status_code=200,
            _content=b"",
            _headers_dict=headers_dict,
            url="https://example.com",
        )
        headers = response.headers
        assert isinstance(headers, httpx.Headers)
        assert headers["content-type"] == "application/json"


# =============================================================================
# SubprocessHttpClient Tests
# =============================================================================


class TestSubprocessHttpClientUrlResolution:
    """Tests for SubprocessHttpClient URL resolution."""

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


class TestSubprocessHttpClientInitialization:
    """Tests for SubprocessHttpClient initialization."""

    def test_headers_default_to_empty_dict(self) -> None:
        """Verify headers default to empty dict when not provided."""
        client = SubprocessHttpClient()
        assert client._headers == {}

    def test_headers_stored_correctly(self) -> None:
        """Verify provided headers are stored correctly."""
        headers = {"Authorization": "Bearer token", "Content-Type": "application/json"}
        client = SubprocessHttpClient(headers=headers)
        assert client._headers == headers

    def test_verify_defaults_to_true(self) -> None:
        """Verify SSL verification defaults to True."""
        client = SubprocessHttpClient()
        assert client._verify is True

    def test_verify_can_be_disabled(self) -> None:
        """Verify SSL verification can be disabled."""
        client = SubprocessHttpClient(verify=False)
        assert client._verify is False


class TestSubprocessHttpClientTimeoutExtraction:
    """Tests for SubprocessHttpClient timeout handling."""

    def test_timeout_extracted_from_connect_timeout(self) -> None:
        """Verify timeout is extracted from httpx.Timeout.connect."""
        # httpx.Timeout(default, connect=...) - first arg is default for all
        timeout = httpx.Timeout(30.0, connect=15.0)
        client = SubprocessHttpClient(timeout=timeout)
        assert client._timeout == 15.0

    def test_timeout_falls_back_to_read_timeout(self) -> None:
        """Verify timeout falls back to read if connect is None."""
        # Create timeout with only read specified, connect will be None
        timeout = httpx.Timeout(timeout=None, read=45.0)
        client = SubprocessHttpClient(timeout=timeout)
        assert client._timeout == 45.0

    def test_timeout_defaults_when_none(self) -> None:
        """Verify default timeout is used when None provided."""
        from nac_test.pyats_core.common.connection_pool import (
            SUBPROCESS_HTTP_TIMEOUT_SECONDS,
        )

        client = SubprocessHttpClient(timeout=None)
        assert client._timeout == SUBPROCESS_HTTP_TIMEOUT_SECONDS


class TestSubprocessHttpClientAsyncContextManager:
    """Tests for SubprocessHttpClient async context manager protocol."""

    def test_aenter_returns_self(self) -> None:
        """Verify __aenter__ returns the client instance."""
        import asyncio

        async def run_test() -> None:
            client = SubprocessHttpClient()
            async with client as ctx:
                assert ctx is client

        asyncio.run(run_test())

    def test_aexit_handles_exceptions(self) -> None:
        """Verify __aexit__ handles exceptions gracefully."""
        import asyncio

        async def run_test() -> None:
            client = SubprocessHttpClient()
            # Should not raise
            await client.__aexit__(None, None, None)
            await client.__aexit__(ValueError, ValueError("test"), None)

        asyncio.run(run_test())

    def test_aclose_is_noop(self) -> None:
        """Verify aclose() is a no-op (for httpx compatibility)."""
        import asyncio

        async def run_test() -> None:
            client = SubprocessHttpClient()
            # Should not raise
            await client.aclose()

        asyncio.run(run_test())


# =============================================================================
# ConnectionPool Platform Selection Tests
# =============================================================================


class TestConnectionPoolPlatformSelection:
    """Tests for ConnectionPool client selection based on platform."""

    def test_returns_subprocess_client_on_darwin(self, mocker: "MockerFixture") -> None:
        """Verify SubprocessHttpClient is returned on macOS."""
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

    def test_passes_parameters_to_subprocess_client(
        self, mocker: "MockerFixture"
    ) -> None:
        """Verify parameters are passed correctly to SubprocessHttpClient."""
        mocker.patch(
            "nac_test.pyats_core.common.connection_pool.platform.system",
            return_value="Darwin",
        )
        ConnectionPool._instance = None
        ConnectionPool._creation_pid = None

        pool = ConnectionPool()
        headers = {"Authorization": "Bearer test"}
        timeout = httpx.Timeout(60.0)

        client = pool.get_client(
            base_url="https://api.example.com",
            headers=headers,
            timeout=timeout,
            verify=False,
        )

        assert isinstance(client, SubprocessHttpClient)
        assert client._base_url == "https://api.example.com"
        assert client._headers == headers
        assert client._verify is False
        assert client._timeout == 60.0
