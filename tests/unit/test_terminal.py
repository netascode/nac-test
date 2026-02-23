# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for terminal formatting utilities.

Tests for format_test_summary() coloring behavior:
- Numbers are colored only when > 0
- Labels (passed, failed, skipped) are never colored
- NO_COLOR environment variable disables all colors
"""

import pytest

from nac_test.core.types import CombinedResults, TestResults
from nac_test.utils.terminal import TerminalColors, terminal


class TestFormatTestSummary:
    """Test format_test_summary() coloring behavior."""

    def test_basic_format_structure(self) -> None:
        """Verify output has correct structure: 'N tests, N passed, N failed, N skipped.'"""
        results = CombinedResults(
            robot=TestResults(passed=5, failed=2, skipped=1),
        )
        output = terminal.format_test_summary(results)
        plain = terminal.strip_ansi(output)

        assert plain == "8 tests, 5 passed, 2 failed, 1 skipped."

    def test_passed_colored_green_when_positive(self) -> None:
        """Verify passed count is colored green when > 0."""
        results = CombinedResults(
            robot=TestResults(passed=3, failed=0, skipped=0),
        )
        output = terminal.format_test_summary(results)

        # Check that green color code wraps the "3"
        assert TerminalColors.SUCCESS in output
        assert f"{TerminalColors.SUCCESS}3{TerminalColors.RESET}" in output

    def test_passed_not_colored_when_zero(self) -> None:
        """Verify passed count is NOT colored when 0."""
        results = CombinedResults(
            robot=TestResults(passed=0, failed=1, skipped=0),
        )
        output = terminal.format_test_summary(results)

        # The "0" for passed should appear without green color
        # Verify green is not applied to "0" by checking the literal appears
        plain = terminal.strip_ansi(output)
        assert "0 passed" in plain

        # Green should NOT wrap "0" - check that the success color + "0" combo doesn't appear
        assert f"{TerminalColors.SUCCESS}0" not in output

    def test_failed_colored_red_when_positive(self) -> None:
        """Verify failed count is colored red when > 0."""
        results = CombinedResults(
            robot=TestResults(passed=0, failed=2, skipped=0),
        )
        output = terminal.format_test_summary(results)

        # Check that red color code wraps the "2"
        assert TerminalColors.ERROR in output
        assert f"{TerminalColors.ERROR}2{TerminalColors.RESET}" in output

    def test_failed_not_colored_when_zero(self) -> None:
        """Verify failed count is NOT colored when 0."""
        results = CombinedResults(
            robot=TestResults(passed=1, failed=0, skipped=0),
        )
        output = terminal.format_test_summary(results)

        # Red should NOT wrap "0" for failed
        assert f"{TerminalColors.ERROR}0" not in output

    def test_skipped_colored_yellow_when_positive(self) -> None:
        """Verify skipped count is colored yellow when > 0."""
        results = CombinedResults(
            robot=TestResults(passed=0, failed=0, skipped=4),
        )
        output = terminal.format_test_summary(results)

        # Check that yellow color code wraps the "4"
        assert TerminalColors.WARNING in output
        assert f"{TerminalColors.WARNING}4{TerminalColors.RESET}" in output

    def test_skipped_not_colored_when_zero(self) -> None:
        """Verify skipped count is NOT colored when 0."""
        results = CombinedResults(
            robot=TestResults(passed=1, failed=0, skipped=0),
        )
        output = terminal.format_test_summary(results)

        # Yellow should NOT wrap "0" for skipped
        assert f"{TerminalColors.WARNING}0" not in output

    def test_labels_never_colored(self) -> None:
        """Verify labels (passed, failed, skipped) are never colored."""
        results = CombinedResults(
            robot=TestResults(passed=5, failed=3, skipped=2),
        )
        output = terminal.format_test_summary(results)

        # The words "passed", "failed", "skipped" should appear without color codes
        # They should follow the colored number and appear as plain text

        # After stripping ANSI, the labels should still be there
        plain = terminal.strip_ansi(output)
        assert " passed" in plain
        assert " failed" in plain
        assert " skipped" in plain

        # More specifically: color codes should only wrap numbers, not labels
        # This is verified by checking the structure: "{color}{number}{reset} label"
        assert f"{TerminalColors.SUCCESS}5{TerminalColors.RESET} passed" in output
        assert f"{TerminalColors.ERROR}3{TerminalColors.RESET} failed" in output
        assert f"{TerminalColors.WARNING}2{TerminalColors.RESET} skipped" in output

    def test_all_zeros_no_colors_applied(self) -> None:
        """Verify no colors are applied when all counts are zero."""
        results = CombinedResults(
            robot=TestResults(passed=0, failed=0, skipped=0),
        )
        output = terminal.format_test_summary(results)

        # No color codes should be present
        assert TerminalColors.SUCCESS not in output
        assert TerminalColors.ERROR not in output
        assert TerminalColors.WARNING not in output

        # Plain output should still be correct
        plain = terminal.strip_ansi(output)
        assert plain == "0 tests, 0 passed, 0 failed, 0 skipped."

    def test_combined_results_aggregates_correctly(self) -> None:
        """Verify format_test_summary correctly aggregates multiple result sources."""
        results = CombinedResults(
            api=TestResults(passed=2, failed=1, skipped=0),
            d2d=TestResults(passed=3, failed=0, skipped=1),
            robot=TestResults(passed=5, failed=2, skipped=0),
        )
        output = terminal.format_test_summary(results)
        plain = terminal.strip_ansi(output)

        # Total: 2+3+5=10 passed, 1+0+2=3 failed, 0+1+0=1 skipped = 14 total
        assert plain == "14 tests, 10 passed, 3 failed, 1 skipped."

    def test_other_shown_when_positive(self) -> None:
        """Verify 'other' count appears when > 0."""
        results = CombinedResults(
            api=TestResults(passed=2, failed=1, skipped=0, other=3),
        )
        output = terminal.format_test_summary(results)
        plain = terminal.strip_ansi(output)

        assert plain == "6 tests, 2 passed, 1 failed, 0 skipped, 3 other."

    def test_other_colored_magenta_when_positive(self) -> None:
        """Verify 'other' count is colored magenta when > 0."""
        results = CombinedResults(
            api=TestResults(passed=2, failed=0, skipped=0, other=1),
        )
        output = terminal.format_test_summary(results)

        assert TerminalColors.HIGHLIGHT in output
        assert f"{TerminalColors.HIGHLIGHT}1{TerminalColors.RESET}" in output

    def test_other_not_shown_when_zero(self) -> None:
        """Verify 'other' count is NOT shown when 0."""
        results = CombinedResults(
            robot=TestResults(passed=5, failed=2, skipped=1, other=0),
        )
        output = terminal.format_test_summary(results)
        plain = terminal.strip_ansi(output)

        assert "other" not in plain
        assert plain == "8 tests, 5 passed, 2 failed, 1 skipped."


class TestFormatTestSummaryNoColor:
    """Test format_test_summary() behavior with NO_COLOR environment variable."""

    def test_no_color_env_disables_all_colors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify NO_COLOR environment variable disables all coloring."""
        # Set NO_COLOR (any value enables it per spec)
        monkeypatch.setenv("NO_COLOR", "1")

        # Need to reload the class attribute since it's set at import time
        # Force re-evaluation by directly setting the class attribute
        original_no_color = TerminalColors.NO_COLOR
        try:
            TerminalColors.NO_COLOR = True

            results = CombinedResults(
                robot=TestResults(passed=5, failed=3, skipped=2),
            )
            output = terminal.format_test_summary(results)

            # With NO_COLOR, output should have no ANSI codes at all
            assert TerminalColors.SUCCESS not in output
            assert TerminalColors.ERROR not in output
            assert TerminalColors.WARNING not in output
            assert TerminalColors.RESET not in output

            # Output should be plain text
            assert output == "10 tests, 5 passed, 3 failed, 2 skipped."
        finally:
            # Restore original value
            TerminalColors.NO_COLOR = original_no_color


class TestTerminalErrorMessages:
    """Test the updated error messages for controller auto-detection."""

    def test_format_env_var_error_auto_detection_messaging(self) -> None:
        """Verify error message explains auto-detection and does not mention CONTROLLER_TYPE."""
        missing_vars = ["ACI_URL", "ACI_PASSWORD"]
        controller_type = "ACI"

        error_msg = terminal.format_env_var_error(missing_vars, controller_type)
        plain_msg = terminal.strip_ansi(error_msg)

        assert "automatically detects" in plain_msg
        assert "Controller type detected: ACI" in plain_msg
        assert "To switch to a different controller:" in plain_msg
        assert "unset ACI_URL ACI_USERNAME ACI_PASSWORD" in plain_msg

        # Ensure CONTROLLER_TYPE is NOT mentioned
        assert "CONTROLLER_TYPE" not in plain_msg
        assert "export CONTROLLER_TYPE" not in plain_msg

    def test_format_env_var_error_includes_all_controllers(self) -> None:
        """Verify error message includes examples for all supported controllers."""
        missing_vars = ["SDWAN_USERNAME"]
        controller_type = "SDWAN"

        error_msg = terminal.format_env_var_error(missing_vars, controller_type)
        plain_msg = terminal.strip_ansi(error_msg)

        controllers = ["ACI", "SDWAN", "CC", "MERAKI", "FMC", "ISE"]
        for controller in controllers:
            assert f"{controller}_URL" in plain_msg
            assert f"{controller}_USERNAME" in plain_msg
            assert f"{controller}_PASSWORD" in plain_msg

    def test_format_env_var_error_shows_missing_vars(self) -> None:
        """Verify error message lists all missing variables."""
        missing_vars = ["CC_URL", "CC_USERNAME", "CC_PASSWORD"]
        controller_type = "CC"

        error_msg = terminal.format_env_var_error(missing_vars, controller_type)
        plain_msg = terminal.strip_ansi(error_msg)

        for var in missing_vars:
            assert var in plain_msg

    def test_format_env_var_error_actionable_instructions(self) -> None:
        """Verify error message provides clear actionable instructions."""
        missing_vars = ["MERAKI_PASSWORD"]
        controller_type = "MERAKI"

        error_msg = terminal.format_env_var_error(missing_vars, controller_type)
        plain_msg = terminal.strip_ansi(error_msg)

        assert "unset MERAKI_URL MERAKI_USERNAME MERAKI_PASSWORD" in plain_msg
        assert "Then set credentials for your desired controller:" in plain_msg
        assert "export MERAKI_URL" in plain_msg
        assert "export MERAKI_USERNAME" in plain_msg
        assert "export MERAKI_PASSWORD" in plain_msg
