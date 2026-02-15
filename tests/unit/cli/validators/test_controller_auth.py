# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Unit tests for pre-flight controller authentication validator.

These tests verify the business logic of the pre-flight auth check,
ensuring the CLI correctly identifies authentication failures and
classifies them appropriately.
"""

from unittest.mock import MagicMock, patch

from _pytest.monkeypatch import MonkeyPatch

from nac_test.cli.validators.controller_auth import (
    CONTROLLER_REGISTRY,
    AuthOutcome,
    _classify_auth_error,
    _get_auth_callable,
    _get_controller_url,
    preflight_auth_check,
)


class TestControllerRegistry:
    """Tests for CONTROLLER_REGISTRY configuration."""

    def test_registry_covers_all_supported_controllers(self) -> None:
        """Registry includes all supported controller types with valid configs."""
        # After consolidation: CONTROLLER_REGISTRY now includes ALL controllers
        expected_controllers = {"ACI", "SDWAN", "CC", "MERAKI", "FMC", "ISE", "IOSXE"}
        assert set(CONTROLLER_REGISTRY.keys()) == expected_controllers

        for controller_type, config in CONTROLLER_REGISTRY.items():
            assert config.display_name, f"{controller_type} missing display_name"
            assert config.url_env_var, f"{controller_type} missing url_env_var"
            assert config.env_var_prefix, f"{controller_type} missing env_var_prefix"


class TestGetControllerUrl:
    """Tests for _get_controller_url helper function."""

    def test_returns_url_from_env_var(self, monkeypatch: MonkeyPatch) -> None:
        """Returns URL from the appropriate environment variable."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        result = _get_controller_url("ACI")

        assert result == "https://apic.example.com"

    def test_strips_trailing_slash(self, monkeypatch: MonkeyPatch) -> None:
        """Removes trailing slash from URL."""
        monkeypatch.setenv("SDWAN_URL", "https://sdwan.example.com/")

        result = _get_controller_url("SDWAN")

        assert result == "https://sdwan.example.com"

    def test_returns_empty_string_when_not_set(self, monkeypatch: MonkeyPatch) -> None:
        """Returns empty string when env var not set."""
        monkeypatch.delenv("CC_URL", raising=False)

        result = _get_controller_url("CC")

        assert result == ""

    def test_returns_empty_string_for_unknown_controller(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Returns empty string for unknown controller type."""
        result = _get_controller_url("UNKNOWN_CONTROLLER")

        assert result == ""


class TestClassifyAuthError:
    """Tests for _classify_auth_error helper function."""

    def test_classifies_401_as_bad_credentials(self) -> None:
        """HTTP 401 errors are classified as bad credentials."""
        error = Exception("HTTP 401: Unauthorized")

        reason, detail = _classify_auth_error(error)

        assert reason == AuthOutcome.BAD_CREDENTIALS
        assert detail == "HTTP 401: Unauthorized"

    def test_classifies_403_as_bad_credentials(self) -> None:
        """HTTP 403 errors are classified as bad credentials."""
        error = Exception("HTTP 403: Forbidden - insufficient privileges")

        reason, detail = _classify_auth_error(error)

        assert reason == AuthOutcome.BAD_CREDENTIALS
        assert detail == "HTTP 403: Forbidden"

    def test_classifies_timeout_as_unreachable(self) -> None:
        """Timeout errors are classified as unreachable."""
        error = Exception("Connection timed out after 30 seconds")

        reason, detail = _classify_auth_error(error)

        assert reason == AuthOutcome.UNREACHABLE
        assert "timed out" in detail.lower()

    def test_classifies_connection_refused_as_unreachable(self) -> None:
        """Connection refused errors are classified as unreachable."""
        error = Exception("Connection refused on port 443")

        reason, detail = _classify_auth_error(error)

        assert reason == AuthOutcome.UNREACHABLE

    def test_classifies_dns_failure_as_unreachable(self) -> None:
        """DNS resolution failures are classified as unreachable."""
        error = Exception("Name or service not known: apic.example.com")

        reason, detail = _classify_auth_error(error)

        assert reason == AuthOutcome.UNREACHABLE

    def test_classifies_unknown_as_unexpected_error(self) -> None:
        """Unknown errors are classified as unexpected."""
        error = Exception("Something completely unexpected happened")

        reason, detail = _classify_auth_error(error)

        assert reason == AuthOutcome.UNEXPECTED_ERROR
        assert "unexpected" in detail.lower()

    def test_classifies_503_as_unreachable(self) -> None:
        """HTTP 503 Service Unavailable is classified as unreachable."""
        error = Exception("HTTP 503: Service Unavailable")

        reason, detail = _classify_auth_error(error)

        assert reason == AuthOutcome.UNREACHABLE
        assert "503" in detail

    def test_classifies_429_as_unreachable(self) -> None:
        """HTTP 429 Too Many Requests is classified as unreachable."""
        error = Exception("HTTP 429: Too Many Requests")

        reason, detail = _classify_auth_error(error)

        assert reason == AuthOutcome.UNREACHABLE
        assert "429" in detail

    def test_classifies_500_as_unexpected_error(self) -> None:
        """HTTP 500 Server Error is classified as unexpected error."""
        error = Exception("HTTP 500: Internal Server Error")

        reason, detail = _classify_auth_error(error)

        assert reason == AuthOutcome.UNEXPECTED_ERROR
        assert "500" in detail

    def test_classifies_404_as_unexpected_error(self) -> None:
        """HTTP 404 Not Found is classified as unexpected error (not auth failure)."""
        error = Exception("HTTP 404: Not Found - endpoint does not exist")

        reason, detail = _classify_auth_error(error)

        assert reason == AuthOutcome.UNEXPECTED_ERROR
        assert "404" in detail

    def test_network_indicators_take_precedence_over_port_numbers(self) -> None:
        """Network errors with port numbers don't get misclassified as HTTP errors."""
        # Port 443 should not be matched as HTTP 443 status code
        error = Exception("Connection refused on port 443")

        reason, detail = _classify_auth_error(error)

        assert reason == AuthOutcome.UNREACHABLE
        assert "Connection refused" in detail


class TestGetAuthCallable:
    """Tests for _get_auth_callable helper function."""

    def test_returns_none_for_unknown_controller(self) -> None:
        """Returns None for unknown controller types."""
        result = _get_auth_callable("UNKNOWN_CONTROLLER")

        assert result is None

    def test_returns_none_for_empty_string(self) -> None:
        """Returns None for empty string controller type."""
        result = _get_auth_callable("")

        assert result is None

    def test_returns_none_for_iosxe(self) -> None:
        """Returns None for IOSXE (no controller auth needed)."""
        result = _get_auth_callable("IOSXE")

        assert result is None


class TestPreflightAuthCheck:
    """Tests for preflight_auth_check main function."""

    def test_returns_success_when_no_auth_adapter(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Returns success when no auth adapter is available."""
        monkeypatch.setenv("IOSXE_URL", "https://device.example.com")

        result = preflight_auth_check("IOSXE")

        assert result.success is True
        assert result.reason == AuthOutcome.SUCCESS
        assert "skipped" in result.detail.lower()

    def test_returns_success_when_adapters_not_installed(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Returns success when nac-test-pyats-common not installed."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        with patch(
            "nac_test.cli.validators.controller_auth._get_auth_callable",
            return_value=None,
        ):
            result = preflight_auth_check("ACI")

        assert result.success is True
        assert "skipped" in result.detail.lower()

    def test_returns_success_when_auth_succeeds(self, monkeypatch: MonkeyPatch) -> None:
        """Returns success when authentication succeeds."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        mock_auth = MagicMock(return_value="token123")
        with patch(
            "nac_test.cli.validators.controller_auth._get_auth_callable",
            return_value=mock_auth,
        ):
            result = preflight_auth_check("ACI")

        assert result.success is True
        assert result.reason == AuthOutcome.SUCCESS
        assert result.controller_type == "ACI"
        assert result.controller_url == "https://apic.example.com"
        mock_auth.assert_called_once()

    def test_returns_failure_for_bad_credentials(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Returns failure when credentials are rejected."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        mock_auth = MagicMock(side_effect=Exception("HTTP 401: Unauthorized"))
        with patch(
            "nac_test.cli.validators.controller_auth._get_auth_callable",
            return_value=mock_auth,
        ):
            result = preflight_auth_check("ACI")

        assert result.success is False
        assert result.reason == AuthOutcome.BAD_CREDENTIALS
        assert "401" in result.detail

    def test_returns_failure_for_unreachable(self, monkeypatch: MonkeyPatch) -> None:
        """Returns failure when controller is unreachable."""
        monkeypatch.setenv("SDWAN_URL", "https://sdwan.example.com")

        mock_auth = MagicMock(side_effect=Exception("Connection timed out"))
        with patch(
            "nac_test.cli.validators.controller_auth._get_auth_callable",
            return_value=mock_auth,
        ):
            result = preflight_auth_check("SDWAN")

        assert result.success is False
        assert result.reason == AuthOutcome.UNREACHABLE
        assert result.controller_type == "SDWAN"

    def test_returns_success_when_missing_env_vars(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Returns success when env vars are missing (let real auth fail later)."""
        monkeypatch.setenv("CC_URL", "https://catc.example.com")

        # ValueError is raised when env vars are missing
        mock_auth = MagicMock(
            side_effect=ValueError(
                "Missing required environment variables: CC_USERNAME"
            )
        )
        with patch(
            "nac_test.cli.validators.controller_auth._get_auth_callable",
            return_value=mock_auth,
        ):
            result = preflight_auth_check("CC")

        # Should succeed to let the actual auth call fail with proper error
        assert result.success is True
        assert "skipped" in result.detail.lower()

    def test_includes_controller_url_in_result(self, monkeypatch: MonkeyPatch) -> None:
        """Auth result includes the controller URL for error messages."""
        monkeypatch.setenv("ACI_URL", "https://apic.lab.local")

        mock_auth = MagicMock(side_effect=Exception("HTTP 403: Forbidden"))
        with patch(
            "nac_test.cli.validators.controller_auth._get_auth_callable",
            return_value=mock_auth,
        ):
            result = preflight_auth_check("ACI")

        assert result.controller_url == "https://apic.lab.local"

    def test_handles_unknown_controller_type(self) -> None:
        """Unknown controller types are handled gracefully (skipped)."""
        result = preflight_auth_check("UNKNOWN_CONTROLLER")

        assert result.success is True
        assert "skipped" in result.detail.lower()
