# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Unit tests for CLI banner components.

These tests verify that the banner functions display correctly and
include the expected content for user guidance.
"""

from io import StringIO
from unittest.mock import patch

from nac_test.cli.ui.banners import (
    BANNER_CONTENT_WIDTH,
    UNICODE_BOX_STYLE,
    _build_title_line,
    _get_visual_width,
    _wrap_url_lines,
    display_aci_defaults_banner,
    display_auth_failure_banner,
    display_unreachable_banner,
)


class TestDisplayAciDefaultsBanner:
    """Tests for display_aci_defaults_banner function."""

    def test_contains_defaults_directory_example(self) -> None:
        """Banner includes example command with defaults directory."""
        output = StringIO()
        with patch("sys.stdout", new=output):
            display_aci_defaults_banner()

        content = output.getvalue()
        assert "-d ./defaults/" in content or "defaults" in content.lower()

    def test_respects_no_color_mode(self) -> None:
        """Banner uses ASCII characters in NO_COLOR mode and excludes Unicode."""
        output = StringIO()
        with (
            patch("nac_test.cli.ui.banners.TerminalColors.NO_COLOR", True),
            patch("sys.stdout", new=output),
        ):
            display_aci_defaults_banner()

        content = output.getvalue()
        # Assert presence of ASCII box characters
        assert "+" in content, "ASCII box character '+' not found"
        assert "=" in content, "ASCII box character '=' not found"

        # Assert ABSENCE of Unicode box characters
        unicode_chars = ["╔", "╗", "╚", "╝", "═", "║", "╠", "╣"]
        for char in unicode_chars:
            assert char not in content, (
                f"Unicode character '{char}' found in NO_COLOR mode"
            )

        # Assert title without emoji
        assert "!!!" in content, "ASCII title markers '!!!' not found"
        assert "🛑" not in content, "Emoji '🛑' found in NO_COLOR mode"


class TestDisplayAuthFailureBanner:
    """Tests for display_auth_failure_banner function."""

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

    def test_contains_auth_failed_message(self) -> None:
        """Banner includes the authentication failed message."""
        output = StringIO()
        with patch("sys.stdout", new=output):
            display_auth_failure_banner(
                controller_type="ACI",
                controller_url="https://apic.example.com",
                detail="HTTP 401: Unauthorized - Invalid credentials",
                env_var_prefix="ACI",
            )

        content = output.getvalue()
        # Banner shows authentication failure message (detail goes to HTML report)
        assert "AUTHENTICATION FAILED" in content
        assert "Could not authenticate" in content

    def test_respects_no_color_mode(self) -> None:
        """Banner uses ASCII characters in NO_COLOR mode and excludes Unicode."""
        output = StringIO()
        with (
            patch("nac_test.cli.ui.banners.TerminalColors.NO_COLOR", True),
            patch("sys.stdout", new=output),
        ):
            display_auth_failure_banner(
                controller_type="ACI",
                controller_url="https://apic.example.com",
                detail="HTTP 401: Unauthorized",
                env_var_prefix="ACI",
            )

        content = output.getvalue()
        # Assert presence of ASCII box characters
        assert "+" in content, "ASCII box character '+' not found"
        assert "=" in content, "ASCII box character '=' not found"

        # Assert ABSENCE of Unicode box characters
        unicode_chars = ["╔", "╗", "╚", "╝", "═", "║", "╠", "╣"]
        for char in unicode_chars:
            assert char not in content, (
                f"Unicode character '{char}' found in NO_COLOR mode"
            )

        # Assert title without emoji
        assert "!!!" in content, "ASCII title markers '!!!' not found"
        assert "AUTHENTICATION FAILED" in content
        assert "⛔" not in content, "Emoji '⛔' found in NO_COLOR mode"


class TestDisplayUnreachableBanner:
    """Tests for display_unreachable_banner function."""

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
        """Banner uses ASCII characters in NO_COLOR mode and excludes Unicode."""
        output = StringIO()
        with (
            patch("nac_test.cli.ui.banners.TerminalColors.NO_COLOR", True),
            patch("sys.stdout", new=output),
        ):
            display_unreachable_banner(
                controller_type="ACI",
                controller_url="https://apic.example.com",
                detail="Connection refused",
            )

        content = output.getvalue()
        # Assert presence of ASCII box characters
        assert "+" in content, "ASCII box character '+' not found"
        assert "=" in content, "ASCII box character '=' not found"

        # Assert ABSENCE of Unicode box characters
        unicode_chars = ["╔", "╗", "╚", "╝", "═", "║", "╠", "╣"]
        for char in unicode_chars:
            assert char not in content, (
                f"Unicode character '{char}' found in NO_COLOR mode"
            )

        # Assert title without emoji
        assert "!!!" in content, "ASCII title markers '!!!' not found"
        assert "UNREACHABLE" in content
        assert "⛔" not in content, "Emoji '⛔' found in NO_COLOR mode"


class TestWrapUrlLines:
    """Tests for the _wrap_url_lines helper."""

    def test_short_url_stays_on_one_line(self) -> None:
        """A prefix + URL that fits within BANNER_CONTENT_WIDTH stays on one line."""
        result = _wrap_url_lines("Could not connect to APIC at", "https://apic.local")
        assert len(result) == 1
        assert "Could not connect to APIC at https://apic.local" == result[0]

    def test_long_url_wraps_to_two_lines(self) -> None:
        """A prefix + URL that exceeds BANNER_CONTENT_WIDTH wraps to two lines."""
        long_url = "https://sandboxdnacultramegaultralong.cisco.com"
        prefix = "Could not connect to Catalyst Center at"
        combined = f"{prefix} {long_url}"
        # Verify our test data actually exceeds the width
        assert len(combined) > BANNER_CONTENT_WIDTH

        result = _wrap_url_lines(prefix, long_url)
        assert len(result) == 2
        assert result[0] == prefix
        assert result[1] == f"  {long_url}"

    def test_indent_applied_to_both_lines_when_wrapping(self) -> None:
        """Indent is applied to both the prefix and URL lines."""
        long_url = "https://this-is-a-really-long-controller-hostname-that-exceeds-width.example.com"
        # Verify our test data actually triggers wrapping with indent
        assert len(f"  curl -k {long_url}") > BANNER_CONTENT_WIDTH

        result = _wrap_url_lines("curl -k", long_url, indent="  ")
        assert len(result) == 2
        assert result[0] == "  curl -k"
        assert result[1] == f"    {long_url}"

    def test_indent_applied_when_single_line(self) -> None:
        """Indent is applied when content fits on one line."""
        result = _wrap_url_lines("curl -k", "https://short.local", indent="  ")
        assert len(result) == 1
        assert result[0] == "  curl -k https://short.local"


class TestLongUrlBannerRendering:
    """Tests that banners with long URLs render within box borders."""

    def test_unreachable_banner_long_url_fits_in_box(self) -> None:
        """Long URLs in unreachable banner wrap so all lines fit within borders."""
        long_url = "https://sandboxdnacultramdeupURL.cisco.com"
        output = StringIO()
        with patch("sys.stdout", new=output):
            display_unreachable_banner(
                controller_type="CC",
                controller_url=long_url,
                detail="Connection timed out",
            )

        lines = output.getvalue().splitlines()
        # Every bordered line should be exactly BANNER_CONTENT_WIDTH + 2 (for ║ on each side)
        expected_line_width = BANNER_CONTENT_WIDTH + 2
        for line in lines:
            assert len(line) <= expected_line_width, (
                f"Line overflows box ({len(line)} > {expected_line_width}): {line!r}"
            )

    def test_auth_failure_banner_long_url_fits_in_box(self) -> None:
        """Long URLs in auth failure banner wrap so all lines fit within borders."""
        long_url = "https://sandboxdnacultramdeupURL.cisco.com"
        output = StringIO()
        with patch("sys.stdout", new=output):
            display_auth_failure_banner(
                controller_type="CC",
                controller_url=long_url,
                detail="HTTP 401: Unauthorized",
                env_var_prefix="CC",
            )

        lines = output.getvalue().splitlines()
        expected_line_width = BANNER_CONTENT_WIDTH + 2
        for line in lines:
            assert len(line) <= expected_line_width, (
                f"Line overflows box ({len(line)} > {expected_line_width}): {line!r}"
            )


class TestTitleAlignment:
    """Tests for banner title alignment with emojis (#638)."""

    def test_get_visual_width_counts_emoji_as_two(self) -> None:
        """Emojis are counted as 2 display columns."""
        assert _get_visual_width("⛔") == 2
        assert _get_visual_width("🛑") == 2
        assert _get_visual_width("A") == 1

    def test_get_visual_width_mixed_text(self) -> None:
        """Mixed text with emojis calculates correctly."""
        # "⛔ CONTROLLER" = 2 + 11 = 13
        assert _get_visual_width("⛔ CONTROLLER") == 13
        # "🛑 ACI 🛑" = 2 + 5 + 2 = 9
        assert _get_visual_width("🛑 ACI 🛑") == 9

    def test_single_emoji_title_is_centered(self) -> None:
        """Single-emoji title is properly centered (#638)."""
        title = "⛔ CONTROLLER AUTHENTICATION FAILED"
        line = _build_title_line(title, BANNER_CONTENT_WIDTH, UNICODE_BOX_STYLE)
        # Line should be exactly BANNER_CONTENT_WIDTH + 2 (for border chars)
        assert _get_visual_width(line) == BANNER_CONTENT_WIDTH + 2

    def test_double_emoji_title_is_centered(self) -> None:
        """Double-emoji title is properly centered."""
        title = "🛑 DEFAULTS FILE REQUIRED FOR ACI 🛑"
        line = _build_title_line(title, BANNER_CONTENT_WIDTH, UNICODE_BOX_STYLE)
        assert _get_visual_width(line) == BANNER_CONTENT_WIDTH + 2
