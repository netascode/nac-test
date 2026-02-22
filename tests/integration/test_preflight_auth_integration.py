# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Real integration tests for pre-flight controller authentication.

These tests use pytest-httpserver to create REAL HTTP mock servers that simulate
APIC/SDWAN/CC controllers. This validates the full integration chain:
- CLI → preflight_auth_check → Auth adapter → subprocess → HTTP request → AuthCache

Unlike unit tests which mock everything, these tests exercise:
- Real HTTP requests (to mock servers)
- Real subprocess execution (via execute_auth_subprocess / os.system)
- Real AuthCache file operations
- Real error classification from actual HTTP responses
"""

import base64
import json

import pytest
from pytest_httpserver import HTTPServer

from nac_test.cli.validators.controller_auth import (
    AuthOutcome,
    preflight_auth_check,
)

pytestmark = pytest.mark.integration


class TestPreflightAuthIntegrationAPIC:
    """Integration tests for APIC pre-flight authentication with mock HTTP server."""

    def test_apic_auth_success_with_real_http_200(
        self,
        httpserver: HTTPServer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Success path: Real HTTP 200 from mock APIC returns success."""
        httpserver.expect_request(
            "/api/aaaLogin.json",
            method="POST",
        ).respond_with_json(
            {
                "imdata": [
                    {
                        "aaaLogin": {
                            "attributes": {
                                "token": "integration-test-token-abc123",
                                "refreshTimeoutSeconds": "600",
                            }
                        }
                    }
                ]
            },
            status=200,
        )

        monkeypatch.setenv("ACI_URL", httpserver.url_for(""))
        monkeypatch.setenv("ACI_USERNAME", "integration-test-user")
        monkeypatch.setenv("ACI_PASSWORD", "integration-test-password")

        result = preflight_auth_check("ACI")

        assert result.success is True
        assert result.reason == AuthOutcome.SUCCESS
        assert result.controller_type == "ACI"

        # Verify real HTTP request was made with correct credentials
        assert len(httpserver.log) >= 1, "No HTTP requests were made to mock server"
        request = httpserver.log[0][0]
        assert request.path == "/api/aaaLogin.json"
        assert request.method == "POST"

        request_body = json.loads(request.data)
        assert request_body["aaaUser"]["attributes"]["name"] == "integration-test-user"
        assert (
            request_body["aaaUser"]["attributes"]["pwd"] == "integration-test-password"
        )

    def test_apic_auth_bad_credentials_with_http_401(
        self,
        httpserver: HTTPServer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Failure path: HTTP 401 from mock APIC is classified as BAD_CREDENTIALS."""
        httpserver.expect_request(
            "/api/aaaLogin.json",
            method="POST",
        ).respond_with_json(
            {
                "imdata": [
                    {
                        "error": {
                            "attributes": {
                                "code": "401",
                                "text": "FAILED local authentication",
                            }
                        }
                    }
                ]
            },
            status=401,
        )

        monkeypatch.setenv("ACI_URL", httpserver.url_for(""))
        monkeypatch.setenv("ACI_USERNAME", "wrong-user")
        monkeypatch.setenv("ACI_PASSWORD", "wrong-password")

        result = preflight_auth_check("ACI")

        assert result.success is False
        assert result.reason == AuthOutcome.BAD_CREDENTIALS
        assert "401" in result.detail

    def test_apic_auth_forbidden_with_http_403(
        self,
        httpserver: HTTPServer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Failure path: HTTP 403 from mock APIC is classified as BAD_CREDENTIALS."""
        httpserver.expect_request(
            "/api/aaaLogin.json",
            method="POST",
        ).respond_with_json(
            {
                "imdata": [
                    {
                        "error": {
                            "attributes": {
                                "code": "403",
                                "text": "Forbidden",
                            }
                        }
                    }
                ]
            },
            status=403,
        )

        monkeypatch.setenv("ACI_URL", httpserver.url_for(""))
        monkeypatch.setenv("ACI_USERNAME", "readonly-user")
        monkeypatch.setenv("ACI_PASSWORD", "some-password")

        result = preflight_auth_check("ACI")

        assert result.success is False
        assert result.reason == AuthOutcome.BAD_CREDENTIALS
        assert "403" in result.detail

    @pytest.mark.slow  # Takes 30+ seconds due to real connection timeout
    def test_apic_auth_unreachable_with_connection_refused(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Failure path: Unreachable server is classified correctly.

        This test uses RFC 5737 TEST-NET-1 (192.0.2.0/24) which is guaranteed
        unreachable. The subprocess auth will wait for the full
        AUTH_REQUEST_TIMEOUT_SECONDS (30s) before failing.
        """
        unreachable_url = "https://192.0.2.1:9999"

        monkeypatch.setenv("ACI_URL", unreachable_url)
        monkeypatch.setenv("ACI_USERNAME", "testuser")
        monkeypatch.setenv("ACI_PASSWORD", "testpass")

        result = preflight_auth_check("ACI")

        assert result.success is False
        assert result.reason == AuthOutcome.UNREACHABLE
        assert any(
            indicator in result.detail.lower()
            for indicator in ["refused", "timeout", "unreachable", "timed out"]
        )


class TestPreflightAuthIntegrationSDWAN:
    """Integration tests for SDWAN Manager pre-flight authentication.

    SDWAN uses form-based login at /j_security_check, returning a JSESSIONID
    cookie, then optionally fetches an XSRF token from /dataservice/client/token.
    """

    def test_sdwan_auth_success_with_session_cookie(
        self,
        httpserver: HTTPServer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Success path: Mock SDWAN Manager returns JSESSIONID and XSRF token."""
        # Step 1: Form login returns JSESSIONID cookie
        httpserver.expect_request(
            "/j_security_check",
            method="POST",
        ).respond_with_data(
            "",
            status=200,
            headers={"Set-Cookie": "JSESSIONID=integration-test-session-123; Path=/"},
        )

        # Step 2: XSRF token endpoint
        httpserver.expect_request(
            "/dataservice/client/token",
            method="GET",
        ).respond_with_data(
            "integration-test-xsrf-token-456",
            status=200,
        )

        monkeypatch.setenv("SDWAN_URL", httpserver.url_for(""))
        monkeypatch.setenv("SDWAN_USERNAME", "integration-test-user")
        monkeypatch.setenv("SDWAN_PASSWORD", "integration-test-password")

        result = preflight_auth_check("SDWAN")

        assert result.success is True
        assert result.reason == AuthOutcome.SUCCESS
        assert result.controller_type == "SDWAN"

        # Verify both steps of SDWAN auth flow were executed
        assert len(httpserver.log) >= 2, (
            "SDWAN auth requires 2 HTTP requests (login + XSRF token)"
        )

        login_request = httpserver.log[0][0]
        assert login_request.path == "/j_security_check"
        assert login_request.method == "POST"

        token_request = httpserver.log[1][0]
        assert token_request.path == "/dataservice/client/token"
        assert token_request.method == "GET"

    def test_sdwan_auth_bad_credentials_with_http_401(
        self,
        httpserver: HTTPServer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Failure path: HTTP 401 from mock SDWAN Manager is classified as BAD_CREDENTIALS."""
        httpserver.expect_request(
            "/j_security_check",
            method="POST",
        ).respond_with_data(
            "Authentication failed",
            status=401,
        )

        monkeypatch.setenv("SDWAN_URL", httpserver.url_for(""))
        monkeypatch.setenv("SDWAN_USERNAME", "wrong-user")
        monkeypatch.setenv("SDWAN_PASSWORD", "wrong-password")

        result = preflight_auth_check("SDWAN")

        assert result.success is False
        assert result.reason == AuthOutcome.BAD_CREDENTIALS
        assert "401" in result.detail


class TestPreflightAuthIntegrationCC:
    """Integration tests for Catalyst Center pre-flight authentication.

    Catalyst Center uses Basic Auth POST to /api/system/v1/auth/token (modern)
    with fallback to /dna/system/api/v1/auth/token (legacy).
    """

    def test_cc_auth_success_with_token_response(
        self,
        httpserver: HTTPServer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Success path: Mock Catalyst Center returns auth token."""
        httpserver.expect_request(
            "/api/system/v1/auth/token",
            method="POST",
        ).respond_with_json(
            {"Token": "integration-test-cc-token-789"},
            status=200,
        )

        monkeypatch.setenv("CC_URL", httpserver.url_for(""))
        monkeypatch.setenv("CC_USERNAME", "integration-test-user")
        monkeypatch.setenv("CC_PASSWORD", "integration-test-password")

        result = preflight_auth_check("CC")

        assert result.success is True
        assert result.reason == AuthOutcome.SUCCESS
        assert result.controller_type == "CC"

        # Verify Basic Auth was used
        assert len(httpserver.log) >= 1, "No HTTP requests were made to mock server"
        auth_request = httpserver.log[0][0]
        assert auth_request.path == "/api/system/v1/auth/token"
        assert auth_request.method == "POST"

        # Verify Basic Auth header contains correct credentials
        auth_header = auth_request.headers.get("Authorization", "")
        assert auth_header.startswith("Basic ")
        decoded = base64.b64decode(auth_header.split(" ", 1)[1]).decode("utf-8")
        assert decoded == "integration-test-user:integration-test-password"

    def test_cc_auth_bad_credentials_with_http_401(
        self,
        httpserver: HTTPServer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Failure path: HTTP 401 from mock Catalyst Center is classified as BAD_CREDENTIALS.

        Catalyst Center tries two endpoints in order. Both must return 401
        for the auth to fail, since it falls back to the legacy endpoint.
        """
        # Both modern and legacy endpoints reject credentials
        httpserver.expect_request(
            "/api/system/v1/auth/token",
            method="POST",
        ).respond_with_json(
            {"error": "Unauthorized"},
            status=401,
        )
        httpserver.expect_request(
            "/dna/system/api/v1/auth/token",
            method="POST",
        ).respond_with_json(
            {"error": "Unauthorized"},
            status=401,
        )

        monkeypatch.setenv("CC_URL", httpserver.url_for(""))
        monkeypatch.setenv("CC_USERNAME", "wrong-user")
        monkeypatch.setenv("CC_PASSWORD", "wrong-password")

        result = preflight_auth_check("CC")

        assert result.success is False
        assert result.reason == AuthOutcome.BAD_CREDENTIALS
        assert "401" in result.detail
