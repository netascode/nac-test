# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for URL parsing utilities."""

import pytest

from nac_test.utils.url import extract_host, sanitize_url_for_display


class TestSanitizeUrlForDisplay:
    """Tests for sanitize_url_for_display utility function."""

    @pytest.mark.parametrize(
        ("input_url", "expected"),
        [
            ("https://apic.example.com", "https://apic.example.com"),
            ("https://apic.example.com/", "https://apic.example.com"),
            ("https://apic.example.com///", "https://apic.example.com"),
            ("  https://apic.example.com/  ", "https://apic.example.com"),
            ("", ""),
            ("   ", ""),
            ("https://admin:secret@apic.example.com/", "https://apic.example.com"),
            ("https://admin@apic.example.com", "https://apic.example.com"),
            (
                "https://admin:secret@apic.example.com:8443/api/v1/",
                "https://apic.example.com:8443/api/v1",
            ),
            (
                "https://admin:pass@[2001:db8::1]:8443/path/",
                "https://[2001:db8::1]:8443/path",
            ),
            (
                "admin:pass@apic.example.com:8443/path",
                "apic.example.com:8443/path",
            ),
            (
                "https://user:pass@apic.example.com/api?debug=true#section",
                "https://apic.example.com/api?debug=true#section",
            ),
        ],
        ids=[
            "without_trailing_slash",
            "single_trailing_slash",
            "multiple_trailing_slashes",
            "surrounding_whitespace",
            "empty_string",
            "whitespace_only",
            "embedded_username_and_password",
            "embedded_username_only",
            "credentials_with_port_and_path",
            "credentials_with_ipv6",
            "schemeless_with_credentials",
            "preserves_query_and_fragment",
        ],
    )
    def test_sanitize_url_for_display(self, input_url: str, expected: str) -> None:
        """Verify URL sanitization behavior for various inputs."""
        assert sanitize_url_for_display(input_url) == expected


class TestExtractHost:
    """Tests for extract_host utility function."""

    def test_https_url_returns_host(self) -> None:
        """Standard HTTPS URL extracts hostname."""
        assert extract_host("https://apic.example.com") == "apic.example.com"

    def test_url_with_port_excludes_port(self) -> None:
        """URL with explicit port excludes port from result."""
        assert extract_host("https://apic.example.com:443") == "apic.example.com"

    def test_url_with_path_strips_path(self) -> None:
        """URL with path returns only the host portion."""
        assert extract_host("https://apic.example.com:443/api/v1") == "apic.example.com"

    def test_http_url_returns_host(self) -> None:
        """HTTP URL extracts hostname correctly."""
        assert extract_host("http://10.1.2.3") == "10.1.2.3"

    def test_ip_with_port_and_path(self) -> None:
        """IP address with port and path extracts host only."""
        assert extract_host("https://10.81.239.29:8443/some/path") == "10.81.239.29"

    def test_bare_hostname_without_scheme(self) -> None:
        """Hostname without scheme falls back to path parsing."""
        assert extract_host("controller.local") == "controller.local"

    def test_bare_hostname_with_path_strips_path(self) -> None:
        """Hostname without scheme but with path strips the path."""
        assert extract_host("controller.local/api") == "controller.local"

    def test_empty_string_returns_empty(self) -> None:
        """Empty input returns empty string."""
        assert extract_host("") == ""

    def test_ipv6_url_strips_brackets(self) -> None:
        """IPv6 literal has brackets stripped."""
        assert extract_host("https://[2001:db8::1]") == "2001:db8::1"

    def test_ipv6_with_port_strips_brackets(self) -> None:
        """IPv6 literal with port has brackets stripped, port excluded."""
        assert extract_host("https://[2001:db8::1]:8443") == "2001:db8::1"

    def test_ipv6_with_port_and_path(self) -> None:
        """IPv6 literal with port and path extracts host only."""
        assert extract_host("https://[2001:db8::1]:8443/api") == "2001:db8::1"
