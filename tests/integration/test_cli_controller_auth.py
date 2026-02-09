# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""CLI integration tests for pre-flight controller authentication.

These tests verify that the pre-flight auth check behaves correctly
at the CLI level, including proper exit codes, banner display, and
HTML report generation.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

import nac_test.cli.main
from nac_test.cli.validators.controller_auth import (
    AuthCheckResult,
    AuthOutcome,
)

pytestmark = pytest.mark.integration


class TestPreflightAuthCliIntegration:
    """Integration tests for pre-flight auth at the CLI level."""

    def test_cli_exits_1_with_auth_failure_banner(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLI exits with code 1 and displays banner when auth fails."""
        # Set up ACI credentials
        monkeypatch.setenv("ACI_URL", "https://apic.test.local")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "wrongpassword")

        # Mock the auth check to return failure
        failed_result = AuthCheckResult(
            success=False,
            reason=AuthOutcome.BAD_CREDENTIALS,
            controller_type="ACI",
            controller_url="https://apic.test.local",
            detail="HTTP 401: Unauthorized",
        )
        with patch(
            "nac_test.cli.main.preflight_auth_check",
            return_value=failed_result,
        ):
            runner = CliRunner()
            result = runner.invoke(
                nac_test.cli.main.app,
                [
                    "-d",
                    "tests/integration/fixtures/data/",
                    "-t",
                    "tests/integration/fixtures/templates/",
                    "-o",
                    str(tmp_path),
                ],
            )

        assert result.exit_code == 1
        # Banner should be displayed
        assert "AUTHENTICATION FAILED" in result.output or "401" in result.output

    def test_cli_exits_1_with_unreachable_banner(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLI exits with code 1 and displays unreachable banner when controller down."""
        # Set up SDWAN credentials
        monkeypatch.setenv("SDWAN_URL", "https://sdwan.test.local")
        monkeypatch.setenv("SDWAN_USERNAME", "admin")
        monkeypatch.setenv("SDWAN_PASSWORD", "password")

        # Mock the auth check to return unreachable
        failed_result = AuthCheckResult(
            success=False,
            reason=AuthOutcome.UNREACHABLE,
            controller_type="SDWAN",
            controller_url="https://sdwan.test.local",
            detail="Connection timed out",
        )
        with patch(
            "nac_test.cli.main.preflight_auth_check",
            return_value=failed_result,
        ):
            runner = CliRunner()
            result = runner.invoke(
                nac_test.cli.main.app,
                [
                    "-d",
                    "tests/integration/fixtures/data/",
                    "-t",
                    "tests/integration/fixtures/templates/",
                    "-o",
                    str(tmp_path),
                ],
            )

        assert result.exit_code == 1
        # Unreachable banner should be displayed
        assert "UNREACHABLE" in result.output or "timed out" in result.output

    def test_cli_proceeds_when_auth_succeeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLI proceeds normally when authentication succeeds."""
        # Set up ACI credentials
        monkeypatch.setenv("ACI_URL", "https://apic.test.local")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "correctpassword")

        # Mock the auth check to return success
        success_result = AuthCheckResult(
            success=True,
            reason=AuthOutcome.SUCCESS,
            controller_type="ACI",
            controller_url="https://apic.test.local",
            detail="Authentication successful",
        )
        with patch(
            "nac_test.cli.main.preflight_auth_check",
            return_value=success_result,
        ):
            runner = CliRunner()
            result = runner.invoke(
                nac_test.cli.main.app,
                [
                    "-d",
                    "tests/integration/fixtures/data/",
                    "-t",
                    "tests/integration/fixtures/templates/",
                    "-o",
                    str(tmp_path),
                ],
            )

        # Should proceed to data merging (which succeeds)
        assert result.exit_code == 0
        assert "Merging data model files" in result.output

    def test_cli_skips_auth_check_in_render_only_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLI skips auth check when --render-only flag is set."""
        # Set up ACI credentials
        monkeypatch.setenv("ACI_URL", "https://apic.test.local")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        # Use a mock that would fail if called
        fail_if_called = MagicMock(
            side_effect=AssertionError(
                "Auth check should not be called in render-only mode"
            )
        )
        with patch(
            "nac_test.cli.main.preflight_auth_check",
            fail_if_called,
        ):
            runner = CliRunner()
            result = runner.invoke(
                nac_test.cli.main.app,
                [
                    "-d",
                    "tests/integration/fixtures/data/",
                    "-t",
                    "tests/integration/fixtures/templates/",
                    "-o",
                    str(tmp_path),
                    "--render-only",
                ],
            )

        # Should succeed since auth check is skipped
        assert result.exit_code == 0
        # Auth check should NOT have been called
        fail_if_called.assert_not_called()

    def test_cli_generates_html_report_on_auth_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLI generates HTML report when auth fails."""
        # Set up CC credentials
        monkeypatch.setenv("CC_URL", "https://catc.test.local")
        monkeypatch.setenv("CC_USERNAME", "admin")
        monkeypatch.setenv("CC_PASSWORD", "wrongpassword")

        # Mock the auth check to return failure
        failed_result = AuthCheckResult(
            success=False,
            reason=AuthOutcome.BAD_CREDENTIALS,
            controller_type="CC",
            controller_url="https://catc.test.local",
            detail="HTTP 403: Forbidden",
        )
        with patch(
            "nac_test.cli.main.preflight_auth_check",
            return_value=failed_result,
        ):
            runner = CliRunner()
            result = runner.invoke(
                nac_test.cli.main.app,
                [
                    "-d",
                    "tests/integration/fixtures/data/",
                    "-t",
                    "tests/integration/fixtures/templates/",
                    "-o",
                    str(tmp_path),
                ],
            )

        assert result.exit_code == 1
        # HTML report should be generated
        report_file = tmp_path / "auth_failure_report.html"
        assert report_file.exists(), "Auth failure HTML report should be generated"

        # Report should contain relevant info
        report_content = report_file.read_text()
        assert (
            "Catalyst Center" in report_content or "catc.test.local" in report_content
        )
