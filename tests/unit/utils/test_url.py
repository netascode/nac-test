# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for URL parsing utilities."""

from nac_test.utils.url import extract_host


class TestExtractHost:
    """Tests for extract_host utility function."""

    def test_https_url_returns_host(self) -> None:
        """Standard HTTPS URL extracts hostname."""
        assert extract_host("https://apic.example.com") == "apic.example.com"

    def test_url_with_port_preserves_port(self) -> None:
        """URL with explicit port includes port in result."""
        assert extract_host("https://apic.example.com:443") == "apic.example.com:443"

    def test_url_with_path_strips_path(self) -> None:
        """URL with path returns only the host portion."""
        assert (
            extract_host("https://apic.example.com:443/api/v1")
            == "apic.example.com:443"
        )

    def test_http_url_returns_host(self) -> None:
        """HTTP URL extracts hostname correctly."""
        assert extract_host("http://10.1.2.3") == "10.1.2.3"

    def test_ip_with_port_and_path(self) -> None:
        """IP address with port and path extracts host:port."""
        assert (
            extract_host("https://10.81.239.29:8443/some/path") == "10.81.239.29:8443"
        )

    def test_bare_hostname_without_scheme(self) -> None:
        """Hostname without scheme falls back to path parsing."""
        assert extract_host("controller.local") == "controller.local"

    def test_bare_hostname_with_path_strips_path(self) -> None:
        """Hostname without scheme but with path strips the path."""
        assert extract_host("controller.local/api") == "controller.local"

    def test_empty_string_returns_empty(self) -> None:
        """Empty input returns empty string."""
        assert extract_host("") == ""
