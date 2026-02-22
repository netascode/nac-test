# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Unit tests for pre-flight controller authentication CLI behavior.

These tests verify that the pre-flight auth check behaves correctly
at the CLI level, including proper exit codes, banner display, and
HTML report generation. Uses mocked auth responses to test CLI flow.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

import nac_test.cli.main
from nac_test.cli.validators.controller_auth import (
    AuthCheckResult,
    AuthOutcome,
    preflight_auth_check,
)


class TestPreflightAuthCli:
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


class TestPreflightCacheInvalidation:
    """Tests verifying that preflight_auth_check invalidates the AuthCache
    before attempting authentication, preventing stale tokens from masking
    credential changes.
    """

    @pytest.mark.parametrize(
        "controller_type,url_env_var,url_value,expected_cache_key",
        [
            ("ACI", "ACI_URL", "https://apic.test.local", "ACI"),
            ("SDWAN", "SDWAN_URL", "https://sdwan.test.local", "SDWAN_MANAGER"),
            ("CC", "CC_URL", "https://catc.test.local", "CC"),
        ],
    )
    def test_cache_invalidated_before_auth_for_each_controller(
        self,
        controller_type: str,
        url_env_var: str,
        url_value: str,
        expected_cache_key: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AuthCache.invalidate is called with the correct cache_key and URL
        before the auth callable is invoked, for each supported controller type.

        Args:
            controller_type: Controller type key in CONTROLLER_REGISTRY.
            url_env_var: Environment variable name for the controller URL.
            url_value: URL value to set in the environment.
            expected_cache_key: The cache_key that should be passed to invalidate().
            monkeypatch: Pytest monkeypatch fixture.
        """
        monkeypatch.setenv(url_env_var, url_value)

        # Track call order to prove invalidate happens before auth
        call_order: list[str] = []

        def mock_auth() -> dict[str, str]:
            call_order.append("auth")
            return {"token": "fresh-token"}

        def mock_invalidate(cache_key: str, url: str) -> None:
            call_order.append("invalidate")

        with (
            patch(
                "nac_test.cli.validators.controller_auth._get_auth_callable",
                return_value=mock_auth,
            ),
            patch(
                "nac_test.cli.validators.controller_auth.AuthCache.invalidate",
                side_effect=mock_invalidate,
            ) as patched_invalidate,
        ):
            result = preflight_auth_check(controller_type)

        assert result.success is True
        patched_invalidate.assert_called_once_with(
            expected_cache_key,
            url_value,
        )
        assert call_order == ["invalidate", "auth"]

    def test_cache_not_invalidated_when_no_auth_adapter(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Controllers without an auth adapter skip cache invalidation entirely."""
        monkeypatch.setenv("MERAKI_URL", "https://meraki.test.local")

        with (
            patch(
                "nac_test.cli.validators.controller_auth._get_auth_callable",
                return_value=None,
            ),
            patch(
                "nac_test.cli.validators.controller_auth.AuthCache.invalidate",
            ) as patched_invalidate,
        ):
            result = preflight_auth_check("MERAKI")

        # Skipped because no auth adapter — invalidate should not be called
        assert result.success is True
        patched_invalidate.assert_not_called()

    def test_cache_invalidation_failure_does_not_block_auth(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A failure in AuthCache.invalidate must not prevent authentication."""
        monkeypatch.setenv("ACI_URL", "https://apic.test.local")

        def mock_auth() -> dict[str, str]:
            return {"token": "fresh-token"}

        with (
            patch(
                "nac_test.cli.validators.controller_auth._get_auth_callable",
                return_value=mock_auth,
            ),
            patch(
                "nac_test.cli.validators.controller_auth.AuthCache.invalidate",
                side_effect=OSError("disk on fire"),
            ),
        ):
            result = preflight_auth_check("ACI")

        # Auth should still succeed despite invalidation failure
        assert result.success is True
        assert result.detail == "Authentication successful"
