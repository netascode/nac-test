# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Unit tests for CLI UI banner components.

These tests verify the banner display functions work correctly,
including color/ASCII mode handling for different terminal environments.
"""

import pytest
from _pytest.monkeypatch import MonkeyPatch

from nac_test.cli.ui.banners import display_aci_defaults_banner


class TestDisplayAciDefaultsBanner:
    """Tests for display_aci_defaults_banner function.

    These tests verify the banner displays correctly without errors.
    We don't test exact output format (that would be testing implementation
    details), but we verify it executes and contains key information.
    """

    def test_banner_outputs_without_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Banner function executes without raising exceptions."""
        # Should not raise any exceptions
        display_aci_defaults_banner()

        captured = capsys.readouterr()
        assert "DEFAULTS FILE REQUIRED FOR ACI" in captured.out

    def test_banner_contains_example_command(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Banner includes helpful example command for users."""
        display_aci_defaults_banner()

        captured = capsys.readouterr()
        assert "nac-test -d" in captured.out
        assert "-d ./defaults/" in captured.out

    def test_banner_uses_ascii_when_no_color_set(
        self, monkeypatch: MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Banner uses ASCII characters when NO_COLOR is set.

        This ensures CI/CD environments and accessibility tools get
        plain text output without Unicode box-drawing characters.
        """
        # Patch the class attribute directly since it's computed at import time
        from nac_test.utils.terminal import TerminalColors

        monkeypatch.setattr(TerminalColors, "NO_COLOR", True)

        display_aci_defaults_banner()

        captured = capsys.readouterr()
        # Should NOT contain Unicode box-drawing characters
        assert "╔" not in captured.out
        assert "║" not in captured.out
        assert "╚" not in captured.out
        # Should contain ASCII equivalents
        assert "+" in captured.out
        assert "=" in captured.out
        assert "|" in captured.out
        # Should NOT contain emoji
        assert "🛑" not in captured.out

    def test_banner_uses_unicode_when_no_color_not_set(
        self, monkeypatch: MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Banner uses Unicode box-drawing when NO_COLOR is not set.

        Interactive terminals should get the visually prominent version.
        """
        monkeypatch.delenv("NO_COLOR", raising=False)

        display_aci_defaults_banner()

        captured = capsys.readouterr()
        # Should contain Unicode box-drawing characters
        assert "╔" in captured.out or "║" in captured.out
        # Should contain emoji
        assert "🛑" in captured.out
