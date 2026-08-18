# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Unit tests for error classification utilities."""

from nac_test.core.controller_auth import AuthOutcome, classify_auth_error
from nac_test.core.error_classification import extract_http_status_code


class TestExtractHttpStatusCode:
    """Tests for extract_http_status_code utility function."""

    def test_extracts_401(self) -> None:
        """Extracts 401 from an HTTP error message."""
        assert extract_http_status_code(Exception("HTTP 401: Unauthorized")) == 401

    def test_extracts_403(self) -> None:
        """Extracts 403 from an HTTP error message."""
        assert extract_http_status_code(Exception("HTTP 403: Forbidden")) == 403

    def test_extracts_500(self) -> None:
        """Extracts 500 from a server error message."""
        assert (
            extract_http_status_code(Exception("HTTP 500: Internal Server Error"))
            == 500
        )

    def test_returns_none_for_no_status_code(self) -> None:
        """Returns None when no HTTP status code is present."""
        assert extract_http_status_code(Exception("Connection timed out")) is None

    def test_returns_none_for_non_http_message(self) -> None:
        """Returns None for generic error messages."""
        assert extract_http_status_code(Exception("Something went wrong")) is None


class TestClassifyAuthError:
    """Tests for classify_auth_error helper function."""

    def test_classifies_401_as_bad_credentials(self) -> None:
        """HTTP 401 errors are classified as bad credentials."""
        error = Exception("HTTP 401: Unauthorized")

        reason, detail = classify_auth_error(error)

        assert reason == AuthOutcome.BAD_CREDENTIALS
        assert detail == "HTTP 401: Unauthorized"

    def test_classifies_403_as_bad_credentials(self) -> None:
        """HTTP 403 errors are classified as bad credentials."""
        error = Exception("HTTP 403: Forbidden - insufficient privileges")

        reason, detail = classify_auth_error(error)

        assert reason == AuthOutcome.BAD_CREDENTIALS
        assert detail == "HTTP 403: Forbidden"

    def test_classifies_timeout_as_unreachable(self) -> None:
        """Timeout errors are classified as unreachable."""
        error = Exception("Connection timed out after 30 seconds")

        reason, detail = classify_auth_error(error)

        assert reason == AuthOutcome.UNREACHABLE
        assert "timed out" in detail.lower()

    def test_classifies_connection_refused_as_unreachable(self) -> None:
        """Connection refused errors are classified as unreachable."""
        error = Exception("Connection refused on port 443")

        reason, detail = classify_auth_error(error)

        assert reason == AuthOutcome.UNREACHABLE

    def test_classifies_dns_failure_as_unreachable(self) -> None:
        """DNS resolution failures are classified as unreachable."""
        error = Exception("Name or service not known: apic.example.com")

        reason, detail = classify_auth_error(error)

        assert reason == AuthOutcome.UNREACHABLE

    def test_classifies_unknown_as_unexpected_error(self) -> None:
        """Unknown errors are classified as unexpected."""
        error = Exception("Something completely unexpected happened")

        reason, detail = classify_auth_error(error)

        assert reason == AuthOutcome.UNEXPECTED_ERROR
        assert "unexpected" in detail.lower()

    def test_classifies_503_as_unreachable(self) -> None:
        """HTTP 503 Service Unavailable is classified as unreachable."""
        error = Exception("HTTP 503: Service Unavailable")

        reason, detail = classify_auth_error(error)

        assert reason == AuthOutcome.UNREACHABLE
        assert "503" in detail

    def test_classifies_429_as_unreachable(self) -> None:
        """HTTP 429 Too Many Requests is classified as unreachable."""
        error = Exception("HTTP 429: Too Many Requests")

        reason, detail = classify_auth_error(error)

        assert reason == AuthOutcome.UNREACHABLE
        assert "429" in detail

    def test_classifies_500_as_unexpected_error(self) -> None:
        """HTTP 500 Server Error is classified as unexpected error."""
        error = Exception("HTTP 500: Internal Server Error")

        reason, detail = classify_auth_error(error)

        assert reason == AuthOutcome.UNEXPECTED_ERROR
        assert "500" in detail

    def test_classifies_404_as_unexpected_error(self) -> None:
        """HTTP 404 Not Found is classified as unexpected error (not auth failure)."""
        error = Exception("HTTP 404: Not Found - endpoint does not exist")

        reason, detail = classify_auth_error(error)

        assert reason == AuthOutcome.UNEXPECTED_ERROR
        assert "404" in detail

    def test_network_indicators_take_precedence_over_port_numbers(self) -> None:
        """Network errors with port numbers don't get misclassified as HTTP errors."""
        # Port 443 should not be matched as HTTP 443 status code
        error = Exception("Connection refused on port 443")

        reason, detail = classify_auth_error(error)

        assert reason == AuthOutcome.UNREACHABLE
        assert "Connection refused" in detail
