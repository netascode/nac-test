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
            (
                "https://admin:s3cret@h:notaport/api",
                "https://h:notaport/api",
            ),
            (
                "https://h:99999/",
                "https://h:99999",
            ),
            (
                "u:p@ss@host/x",
                "host/x",
            ),
            (
                "host/path?u=a@b",
                "host/path?u=a@b",
            ),
            (
                "//user:pass@h:8443/p",
                "//h:8443/p",
            ),
            (
                "https://admin:pass@[2001:db8::1]:notaport/path",
                "https://[2001:db8::1]:notaport/path",
            ),
            (
                "APIC.Example.COM:8443/x",
                "apic.example.com:8443/x",
            ),
            (
                "HTTPS://Admin:Secret@Host.Example.COM:8443/Path/",
                "https://host.example.com:8443/Path",
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
            "malformed_non_numeric_port",
            "out_of_range_port",
            "schemeless_password_with_at_sign",
            "schemeless_query_with_at_sign",
            "protocol_relative_with_credentials",
            "ipv6_with_malformed_port",
            "schemeless_hostname_lowercased",
            "scheme_and_hostname_lowercased_path_preserved",
        ],
    )
    def test_sanitize_url_for_display(self, input_url: str, expected: str) -> None:
        """Verify URL sanitization behavior for various inputs."""
        assert sanitize_url_for_display(input_url) == expected


class TestExtractHost:
    """Tests for extract_host utility function."""

    @pytest.mark.parametrize(
        ("input_url", "expected"),
        [
            ("https://apic.example.com", "apic.example.com"),
            ("https://apic.example.com:443", "apic.example.com"),
            ("https://apic.example.com:443/api/v1", "apic.example.com"),
            ("http://10.1.2.3", "10.1.2.3"),
            ("https://10.81.239.29:8443/some/path", "10.81.239.29"),
            ("controller.local", "controller.local"),
            ("controller.local/api", "controller.local"),
            ("", ""),
            ("   ", ""),
            ("https://[2001:db8::1]", "2001:db8::1"),
            ("https://[2001:db8::1]:8443", "2001:db8::1"),
            ("https://[2001:db8::1]:8443/api", "2001:db8::1"),
            ("https://admin:secret@apic.example.com", "apic.example.com"),
            (
                "user:pass@apic.example.com:8443/path",
                "apic.example.com",
            ),
            ("admin@apic.example.com", "apic.example.com"),
            ("host:8080/path", "host"),
            ("Controller.LOCAL", "controller.local"),
        ],
        ids=[
            "https_url",
            "url_with_port",
            "url_with_port_and_path",
            "http_ip_address",
            "ip_with_port_and_path",
            "bare_hostname_without_scheme",
            "bare_hostname_with_path",
            "empty_string",
            "whitespace_only",
            "ipv6_url_strips_brackets",
            "ipv6_with_port_strips_brackets",
            "ipv6_with_port_and_path",
            "https_with_embedded_credentials",
            "schemeless_with_credentials_and_port",
            "schemeless_user_only",
            "schemeless_host_with_port_and_path",
            "hostname_lowercased",
        ],
    )
    def test_extract_host(self, input_url: str, expected: str) -> None:
        """Verify host extraction behavior for various inputs."""
        assert extract_host(input_url) == expected
