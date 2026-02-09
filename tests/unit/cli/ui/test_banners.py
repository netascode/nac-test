# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Unit tests for CLI banner components.

These tests verify that the banner functions display correctly and
include the expected content for user guidance.
"""

from io import StringIO
from unittest.mock import patch

from nac_test.cli.ui.banners import (
    display_aci_defaults_banner,
    display_auth_failure_banner,
    display_unreachable_banner,
)


class TestDisplayAciDefaultsBanner:
    """Tests for display_aci_defaults_banner function."""

    def test_displays_without_error(self) -> None:
        """Banner displays without raising exceptions."""
        with patch("sys.stdout", new=StringIO()):
            display_aci_defaults_banner()

    def test_contains_defaults_directory_example(self) -> None:
        """Banner includes example command with defaults directory."""
        output = StringIO()
        with patch("sys.stdout", new=output):
            display_aci_defaults_banner()

        content = output.getvalue()
        assert "-d ./defaults/" in content or "defaults" in content.lower()

    def test_respects_no_color_mode(self) -> None:
        """Banner uses ASCII characters in NO_COLOR mode."""
        output = StringIO()
        with (
            patch("nac_test.utils.terminal.TerminalColors.NO_COLOR", True),
            patch("sys.stdout", new=output),
        ):
            display_aci_defaults_banner()

        content = output.getvalue()
        # In NO_COLOR mode, should use ASCII box characters (+ and =)
        assert "+" in content or "=" in content


class TestDisplayAuthFailureBanner:
    """Tests for display_auth_failure_banner function."""

    def test_displays_without_error(self) -> None:
        """Banner displays without raising exceptions."""
        with patch("sys.stdout", new=StringIO()):
            display_auth_failure_banner(
                controller_type="ACI",
                controller_url="https://apic.example.com",
                detail="HTTP 401: Unauthorized",
                env_var_prefix="ACI",
            )

    def test_contains_controller_type_display_name(self) -> None:
        """Banner shows the controller display name (APIC for ACI)."""
        output = StringIO()
        with patch("sys.stdout", new=output):
            display_auth_failure_banner(
                controller_type="ACI",
                controller_url="https://apic.example.com",
                detail="HTTP 401: Unauthorized",
                env_var_prefix="ACI",
            )

        content = output.getvalue()
        assert "APIC" in content

    def test_contains_controller_url(self) -> None:
        """Banner includes the controller URL."""
        output = StringIO()
        with patch("sys.stdout", new=output):
            display_auth_failure_banner(
                controller_type="SDWAN",
                controller_url="https://sdwan-manager.lab.local",
                detail="HTTP 403: Forbidden",
                env_var_prefix="SDWAN",
            )

        content = output.getvalue()
        assert "sdwan-manager.lab.local" in content

    def test_contains_credential_env_var_hints(self) -> None:
        """Banner shows environment variable names for credentials."""
        output = StringIO()
        with patch("sys.stdout", new=output):
            display_auth_failure_banner(
                controller_type="CC",
                controller_url="https://catc.example.com",
                detail="HTTP 401: Unauthorized",
                env_var_prefix="CC",
            )

        content = output.getvalue()
        assert "CC_USERNAME" in content
        assert "CC_PASSWORD" in content

    def test_contains_error_detail(self) -> None:
        """Banner includes the error detail string."""
        output = StringIO()
        with patch("sys.stdout", new=output):
            display_auth_failure_banner(
                controller_type="ACI",
                controller_url="https://apic.example.com",
                detail="HTTP 401: Unauthorized - Invalid credentials",
                env_var_prefix="ACI",
            )

        content = output.getvalue()
        assert "401" in content

    def test_respects_no_color_mode(self) -> None:
        """Banner uses ASCII characters in NO_COLOR mode."""
        output = StringIO()
        with (
            patch("nac_test.utils.terminal.TerminalColors.NO_COLOR", True),
            patch("sys.stdout", new=output),
        ):
            display_auth_failure_banner(
                controller_type="ACI",
                controller_url="https://apic.example.com",
                detail="HTTP 401: Unauthorized",
                env_var_prefix="ACI",
            )

        content = output.getvalue()
        # In NO_COLOR mode, should use ASCII title (no emoji)
        assert "AUTHENTICATION FAILED" in content


class TestDisplayUnreachableBanner:
    """Tests for display_unreachable_banner function."""

    def test_displays_without_error(self) -> None:
        """Banner displays without raising exceptions."""
        with patch("sys.stdout", new=StringIO()):
            display_unreachable_banner(
                controller_type="ACI",
                controller_url="https://apic.example.com",
                detail="Connection timed out",
            )

    def test_contains_controller_url(self) -> None:
        """Banner includes the controller URL."""
        output = StringIO()
        with patch("sys.stdout", new=output):
            display_unreachable_banner(
                controller_type="SDWAN",
                controller_url="https://sdwan.example.com",
                detail="Connection refused",
            )

        content = output.getvalue()
        assert "sdwan.example.com" in content

    def test_contains_curl_command_for_testing(self) -> None:
        """Banner includes a curl command for connectivity testing."""
        output = StringIO()
        with patch("sys.stdout", new=output):
            display_unreachable_banner(
                controller_type="CC",
                controller_url="https://catc.example.com",
                detail="Connection timed out",
            )

        content = output.getvalue()
        assert "curl" in content

    def test_contains_ping_command(self) -> None:
        """Banner includes a ping command for connectivity testing."""
        output = StringIO()
        with patch("sys.stdout", new=output):
            display_unreachable_banner(
                controller_type="ACI",
                controller_url="https://apic.lab.local",
                detail="Connection refused",
            )

        content = output.getvalue()
        assert "ping" in content
        assert "apic.lab.local" in content

    def test_extracts_host_from_https_url(self) -> None:
        """Banner correctly extracts host from HTTPS URL for ping command."""
        output = StringIO()
        with patch("sys.stdout", new=output):
            display_unreachable_banner(
                controller_type="ACI",
                controller_url="https://10.1.2.3:443",
                detail="Timeout",
            )

        content = output.getvalue()
        # Should extract IP address for ping, not include port
        assert "10.1.2.3" in content

    def test_respects_no_color_mode(self) -> None:
        """Banner uses ASCII characters in NO_COLOR mode."""
        output = StringIO()
        with (
            patch("nac_test.utils.terminal.TerminalColors.NO_COLOR", True),
            patch("sys.stdout", new=output),
        ):
            display_unreachable_banner(
                controller_type="ACI",
                controller_url="https://apic.example.com",
                detail="Connection refused",
            )

        content = output.getvalue()
        # In NO_COLOR mode, should use ASCII title (no emoji)
        assert "UNREACHABLE" in content
