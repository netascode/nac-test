# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Unit tests for auth failure report generation.

These tests verify that the auth failure HTML report is generated correctly
and includes the expected content for user guidance.
"""

from pathlib import Path

from nac_test.cli.reporting.auth_failure import (
    AUTH_FAILURE_REPORT_FILENAME,
    _get_curl_example,
    generate_auth_failure_report,
)
from nac_test.cli.validators.controller_auth import AuthCheckResult
from nac_test.core.error_classification import AuthOutcome
from nac_test.utils.url import extract_host


class TestExtractHost:
    """Tests for extract_host helper function."""

    def test_extracts_host_from_https_url(self) -> None:
        """Extracts host from HTTPS URL."""
        host = extract_host("https://apic.example.com")
        assert host == "apic.example.com"

    def test_extracts_host_from_http_url(self) -> None:
        """Extracts host from HTTP URL."""
        host = extract_host("http://apic.example.com")
        assert host == "apic.example.com"

    def test_extracts_host_with_port(self) -> None:
        """Extracts host including port from URL."""
        host = extract_host("https://apic.example.com:443")
        assert host == "apic.example.com:443"

    def test_extracts_host_from_ip_address(self) -> None:
        """Extracts IP address from URL."""
        host = extract_host("https://10.1.2.3")
        assert host == "10.1.2.3"

    def test_handles_trailing_slash(self) -> None:
        """Handles URL with trailing slash."""
        host = extract_host("https://apic.example.com/")
        assert host == "apic.example.com"

    def test_handles_url_without_scheme(self) -> None:
        """Handles URL without scheme prefix."""
        host = extract_host("apic.example.com")
        assert host == "apic.example.com"

    def test_handles_url_with_path(self) -> None:
        """Extracts host from URL with path, ignoring the path."""
        host = extract_host("https://apic.example.com/api/v1")
        assert host == "apic.example.com"

    def test_handles_empty_string(self) -> None:
        """Returns empty string for empty input."""
        host = extract_host("")
        assert host == ""


class TestGetCurlExample:
    """Tests for _get_curl_example helper function."""

    def test_aci_curl_example(self) -> None:
        """Returns correct curl command for ACI."""
        curl = _get_curl_example("ACI", "https://apic.example.com")
        assert "aaaLogin.json" in curl
        assert "apic.example.com" in curl

    def test_sdwan_curl_example(self) -> None:
        """Returns correct curl command for SDWAN."""
        curl = _get_curl_example("SDWAN", "https://sdwan.example.com")
        assert "j_security_check" in curl
        assert "sdwan.example.com" in curl

    def test_cc_curl_example(self) -> None:
        """Returns correct curl command for Catalyst Center."""
        curl = _get_curl_example("CC", "https://catc.example.com")
        assert "auth/token" in curl
        assert "catc.example.com" in curl

    def test_unknown_controller_curl_example(self) -> None:
        """Returns URL only for unknown controller types."""
        curl = _get_curl_example("UNKNOWN", "https://example.com")
        assert curl == "https://example.com"


class TestGenerateAuthFailureReport:
    """Tests for generate_auth_failure_report function."""

    def test_creates_html_file(self, tmp_path: Path) -> None:
        """Creates an HTML file in the output directory."""
        auth_result = AuthCheckResult(
            success=False,
            reason=AuthOutcome.BAD_CREDENTIALS,
            controller_type="ACI",
            controller_url="https://apic.example.com",
            detail="HTTP 401: Unauthorized",
        )

        report_path = generate_auth_failure_report(auth_result, tmp_path)

        assert report_path.exists()
        assert report_path.name == AUTH_FAILURE_REPORT_FILENAME
        assert report_path.parent == tmp_path

    def test_creates_output_directory_if_missing(self, tmp_path: Path) -> None:
        """Creates output directory if it doesn't exist."""
        output_dir = tmp_path / "nested" / "output"
        auth_result = AuthCheckResult(
            success=False,
            reason=AuthOutcome.BAD_CREDENTIALS,
            controller_type="ACI",
            controller_url="https://apic.example.com",
            detail="HTTP 401: Unauthorized",
        )

        report_path = generate_auth_failure_report(auth_result, output_dir)

        assert output_dir.exists()
        assert report_path.exists()

    def test_report_contains_controller_type(self, tmp_path: Path) -> None:
        """Report includes the controller type."""
        auth_result = AuthCheckResult(
            success=False,
            reason=AuthOutcome.BAD_CREDENTIALS,
            controller_type="ACI",
            controller_url="https://apic.example.com",
            detail="HTTP 401: Unauthorized",
        )

        report_path = generate_auth_failure_report(auth_result, tmp_path)
        content = report_path.read_text()

        # Should contain display name
        assert "APIC" in content

    def test_report_contains_controller_url(self, tmp_path: Path) -> None:
        """Report includes the controller URL."""
        auth_result = AuthCheckResult(
            success=False,
            reason=AuthOutcome.BAD_CREDENTIALS,
            controller_type="SDWAN",
            controller_url="https://sdwan-manager.lab.local",
            detail="HTTP 403: Forbidden",
        )

        report_path = generate_auth_failure_report(auth_result, tmp_path)
        content = report_path.read_text()

        assert "sdwan-manager.lab.local" in content

    def test_report_contains_error_detail(self, tmp_path: Path) -> None:
        """Report includes the error detail."""
        auth_result = AuthCheckResult(
            success=False,
            reason=AuthOutcome.BAD_CREDENTIALS,
            controller_type="ACI",
            controller_url="https://apic.example.com",
            detail="HTTP 401: Unauthorized",
        )

        report_path = generate_auth_failure_report(auth_result, tmp_path)
        content = report_path.read_text()

        assert "401" in content

    def test_unreachable_report_contains_connectivity_info(
        self, tmp_path: Path
    ) -> None:
        """Unreachable report includes connectivity debugging info."""
        auth_result = AuthCheckResult(
            success=False,
            reason=AuthOutcome.UNREACHABLE,
            controller_type="CC",
            controller_url="https://catc.example.com",
            detail="Connection timed out",
        )

        report_path = generate_auth_failure_report(auth_result, tmp_path)
        content = report_path.read_text()

        # Should contain connectivity hints
        assert "curl" in content or "ping" in content
        assert "unreachable" in content.lower() or "Unreachable" in content

    def test_403_report_contains_permission_callout(self, tmp_path: Path) -> None:
        """403 error report contains the permission-specific callout."""
        auth_result = AuthCheckResult(
            success=False,
            reason=AuthOutcome.BAD_CREDENTIALS,
            controller_type="ACI",
            controller_url="https://apic.example.com",
            detail="HTTP 403: Forbidden",
        )

        report_path = generate_auth_failure_report(auth_result, tmp_path)
        content = report_path.read_text()

        # Should contain 403-specific note about permissions vs credentials
        assert "403" in content

    def test_report_contains_timestamp(self, tmp_path: Path) -> None:
        """Report includes a timestamp."""
        auth_result = AuthCheckResult(
            success=False,
            reason=AuthOutcome.BAD_CREDENTIALS,
            controller_type="ACI",
            controller_url="https://apic.example.com",
            detail="HTTP 401: Unauthorized",
        )

        report_path = generate_auth_failure_report(auth_result, tmp_path)
        content = report_path.read_text()

        # Timestamp format: YYYY-MM-DD HH:MM:SS
        import re

        timestamp_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
        assert re.search(timestamp_pattern, content)
