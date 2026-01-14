# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tests for controller type detection utilities."""

import os
from collections.abc import Generator
from unittest.mock import patch

import pytest

from nac_test.utils.controller import (
    CREDENTIAL_PATTERNS,
    _find_credential_sets,
    _format_multiple_credentials_error,
    _format_no_credentials_error,
    detect_controller_type,
)


class TestControllerDetection:
    """Test controller type detection functionality."""

    @pytest.fixture(autouse=True)
    def clean_environment(self) -> Generator[None, None, None]:
        """Clean environment variables before and after each test."""
        # Store original environment
        original_env = os.environ.copy()

        # Remove all controller-related variables
        for controller_vars in CREDENTIAL_PATTERNS.values():
            for var in controller_vars:
                os.environ.pop(var, None)

        # Also remove legacy CONTROLLER_TYPE if present
        os.environ.pop("CONTROLLER_TYPE", None)

        yield

        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)

    @pytest.mark.parametrize(
        "controller_type,env_vars",
        [
            ("ACI", ["ACI_URL", "ACI_USERNAME", "ACI_PASSWORD"]),
            ("SDWAN", ["SDWAN_URL", "SDWAN_USERNAME", "SDWAN_PASSWORD"]),
            ("CC", ["CC_URL", "CC_USERNAME", "CC_PASSWORD"]),
            ("MERAKI", ["MERAKI_URL", "MERAKI_USERNAME", "MERAKI_PASSWORD"]),
            ("FMC", ["FMC_URL", "FMC_USERNAME", "FMC_PASSWORD"]),
            ("ISE", ["ISE_URL", "ISE_USERNAME", "ISE_PASSWORD"]),
        ],
    )
    def test_detect_single_controller_type(
        self, controller_type: str, env_vars: list[str]
    ) -> None:
        """Test detection of each supported controller type."""
        # Set complete credentials for one controller
        os.environ[env_vars[0]] = f"https://{controller_type.lower()}.example.com"
        os.environ[env_vars[1]] = "testuser"
        os.environ[env_vars[2]] = "testpass"

        result = detect_controller_type()
        assert result == controller_type

    def test_multiple_controllers_error(self) -> None:
        """Test error when multiple controllers have complete credentials."""
        # Set credentials for ACI
        os.environ["ACI_URL"] = "https://apic.example.com"
        os.environ["ACI_USERNAME"] = "aci_user"
        os.environ["ACI_PASSWORD"] = "aci_pass"

        # Set credentials for SDWAN
        os.environ["SDWAN_URL"] = "https://vmanage.example.com"
        os.environ["SDWAN_USERNAME"] = "sdwan_user"
        os.environ["SDWAN_PASSWORD"] = "sdwan_pass"

        with pytest.raises(ValueError) as exc_info:
            detect_controller_type()

        error_msg = str(exc_info.value)
        assert "Multiple controller credentials detected: ACI, SDWAN" in error_msg
        assert "unset SDWAN_URL SDWAN_USERNAME SDWAN_PASSWORD" in error_msg
        assert "unset ACI_URL ACI_USERNAME ACI_PASSWORD" in error_msg

    def test_no_credentials_error(self) -> None:
        """Test error when no controller credentials are found."""
        # Ensure environment is completely clean
        for controller_vars in CREDENTIAL_PATTERNS.values():
            for var in controller_vars:
                os.environ.pop(var, None)

        with pytest.raises(ValueError) as exc_info:
            detect_controller_type()

        error_msg = str(exc_info.value)
        assert "No controller credentials found in environment" in error_msg
        assert "Controller credentials are required for ALL test types" in error_msg
        assert "export ACI_URL=" in error_msg
        assert "export SDWAN_URL=" in error_msg

    def test_partial_credentials_error(self) -> None:
        """Test error when controller has incomplete credentials."""
        # Set only URL and username for ACI (missing password)
        os.environ["ACI_URL"] = "https://apic.example.com"
        os.environ["ACI_USERNAME"] = "admin"
        # Deliberately not setting ACI_PASSWORD

        with pytest.raises(ValueError) as exc_info:
            detect_controller_type()

        error_msg = str(exc_info.value)
        assert "Incomplete controller credentials detected" in error_msg
        assert "ACI: missing ACI_PASSWORD" in error_msg

    def test_empty_string_handling(self) -> None:
        """Test that empty string values are treated as missing."""
        # Set ACI credentials with empty password
        os.environ["ACI_URL"] = "https://apic.example.com"
        os.environ["ACI_USERNAME"] = "admin"
        os.environ["ACI_PASSWORD"] = ""  # Empty string

        with pytest.raises(ValueError) as exc_info:
            detect_controller_type()

        error_msg = str(exc_info.value)
        assert "Incomplete controller credentials detected" in error_msg
        assert "ACI: missing ACI_PASSWORD" in error_msg

    def test_whitespace_handling(self) -> None:
        """Test that whitespace-only values are treated as missing."""
        # Set SDWAN credentials with whitespace-only password
        os.environ["SDWAN_URL"] = "https://vmanage.example.com"
        os.environ["SDWAN_USERNAME"] = "admin"
        os.environ["SDWAN_PASSWORD"] = "   "  # Only whitespace

        with pytest.raises(ValueError) as exc_info:
            detect_controller_type()

        error_msg = str(exc_info.value)
        assert "Incomplete controller credentials detected" in error_msg
        assert "SDWAN: missing SDWAN_PASSWORD" in error_msg

    def test_d2d_scenario_with_dummy_credentials(self) -> None:
        """Test D2D scenario where controller credentials are still required."""
        # Set complete ACI credentials (even for D2D tests)
        os.environ["ACI_URL"] = "https://dummy.controller.local"
        os.environ["ACI_USERNAME"] = "dummy"
        os.environ["ACI_PASSWORD"] = "dummy"

        # Also set device credentials (for D2D)
        os.environ["IOSXE_USERNAME"] = "device_user"
        os.environ["IOSXE_PASSWORD"] = "device_pass"

        result = detect_controller_type()
        assert result == "ACI"  # Controller type still detected


class TestHelperFunctions:
    """Test helper functions for credential detection."""

    @pytest.fixture(autouse=True)
    def clean_environment(self) -> Generator[None, None, None]:
        """Clean environment variables before and after each test."""
        original_env = os.environ.copy()

        for controller_vars in CREDENTIAL_PATTERNS.values():
            for var in controller_vars:
                os.environ.pop(var, None)

        yield

        os.environ.clear()
        os.environ.update(original_env)

    def test_find_credential_sets_complete(self) -> None:
        """Test finding complete credential sets."""
        # Set complete credentials for CC
        os.environ["CC_URL"] = "https://cc.example.com"
        os.environ["CC_USERNAME"] = "admin"
        os.environ["CC_PASSWORD"] = "password"

        complete, partial = _find_credential_sets()

        assert complete == ["CC"]
        assert partial == {}

    def test_find_credential_sets_partial(self) -> None:
        """Test finding partial credential sets."""
        # Set partial credentials for FMC (missing password)
        os.environ["FMC_URL"] = "https://fmc.example.com"
        os.environ["FMC_USERNAME"] = "admin"
        # No FMC_PASSWORD

        complete, partial = _find_credential_sets()

        assert complete == []
        assert "FMC" in partial
        assert partial["FMC"]["present"] == ["FMC_URL", "FMC_USERNAME"]
        assert partial["FMC"]["missing"] == ["FMC_PASSWORD"]

    def test_find_credential_sets_multiple_partial(self) -> None:
        """Test finding multiple partial credential sets."""
        # Partial ISE credentials
        os.environ["ISE_URL"] = "https://ise.example.com"
        # Missing ISE_USERNAME and ISE_PASSWORD

        # Partial MERAKI credentials
        os.environ["MERAKI_USERNAME"] = "meraki_user"
        # Missing MERAKI_URL and MERAKI_PASSWORD

        complete, partial = _find_credential_sets()

        assert complete == []
        assert len(partial) == 2
        assert "ISE" in partial
        assert "MERAKI" in partial
        assert partial["ISE"]["missing"] == ["ISE_USERNAME", "ISE_PASSWORD"]
        assert partial["MERAKI"]["missing"] == ["MERAKI_URL", "MERAKI_PASSWORD"]

    def test_format_multiple_credentials_error(self) -> None:
        """Test formatting error message for multiple controllers."""
        error_msg = _format_multiple_credentials_error(["ACI", "SDWAN", "CC"])

        assert "Multiple controller credentials detected: ACI, SDWAN, CC" in error_msg
        assert "To use ACI only:" in error_msg
        assert (
            "unset SDWAN_URL SDWAN_USERNAME SDWAN_PASSWORD CC_URL CC_USERNAME CC_PASSWORD"
            in error_msg
        )
        assert "To use SDWAN only:" in error_msg
        assert (
            "unset ACI_URL ACI_USERNAME ACI_PASSWORD CC_URL CC_USERNAME CC_PASSWORD"
            in error_msg
        )
        assert "To use CC only:" in error_msg
        assert "Use a separate shell session" in error_msg

    def test_format_no_credentials_error(self) -> None:
        """Test formatting error message for no credentials."""
        error_msg = _format_no_credentials_error({})

        assert "No controller credentials found in environment" in error_msg
        assert "Controller credentials are required for ALL test types" in error_msg
        assert "ACI:" in error_msg
        assert "export ACI_URL=<value>" in error_msg
        assert "SDWAN:" in error_msg
        assert "export SDWAN_URL=<value>" in error_msg
        assert "Example for ACI:" in error_msg
        assert "Set credentials for only ONE controller type at a time" in error_msg


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    @pytest.fixture(autouse=True)
    def clean_environment(self) -> Generator[None, None, None]:
        """Clean environment variables before and after each test."""
        original_env = os.environ.copy()

        for controller_vars in CREDENTIAL_PATTERNS.values():
            for var in controller_vars:
                os.environ.pop(var, None)

        yield

        os.environ.clear()
        os.environ.update(original_env)

    def test_case_sensitivity(self) -> None:
        """Test that environment variable names are case-sensitive."""
        # Set lowercase variables (should not be detected)
        os.environ["aci_url"] = "https://apic.example.com"
        os.environ["aci_username"] = "admin"
        os.environ["aci_password"] = "password"

        with pytest.raises(ValueError) as exc_info:
            detect_controller_type()

        assert "No controller credentials found" in str(exc_info.value)

    def test_special_characters_in_credentials(self) -> None:
        """Test handling of special characters in credential values."""
        # Set credentials with special characters
        os.environ["CC_URL"] = "https://cc.example.com:8443/path"
        os.environ["CC_USERNAME"] = "user@domain.com"
        os.environ["CC_PASSWORD"] = "p@$$w0rd!#$%^&*()"

        result = detect_controller_type()
        assert result == "CC"

    def test_legacy_controller_type_ignored(self) -> None:
        """Test that legacy CONTROLLER_TYPE variable is ignored."""
        # Set legacy CONTROLLER_TYPE (should be ignored)
        os.environ["CONTROLLER_TYPE"] = "APIC"

        # Set actual SDWAN credentials
        os.environ["SDWAN_URL"] = "https://vmanage.example.com"
        os.environ["SDWAN_USERNAME"] = "admin"
        os.environ["SDWAN_PASSWORD"] = "password"

        result = detect_controller_type()
        assert (
            result == "SDWAN"
        )  # Should use credential-based detection, not CONTROLLER_TYPE

    def test_mixed_complete_and_partial_credentials(self) -> None:
        """Test scenario with one complete and one partial credential set."""
        # Complete FMC credentials
        os.environ["FMC_URL"] = "https://fmc.example.com"
        os.environ["FMC_USERNAME"] = "admin"
        os.environ["FMC_PASSWORD"] = "password"

        # Partial ISE credentials (missing password)
        os.environ["ISE_URL"] = "https://ise.example.com"
        os.environ["ISE_USERNAME"] = "ise_admin"

        result = detect_controller_type()
        assert result == "FMC"  # Should detect the complete set

    def test_whitespace_trimming_in_values(self) -> None:
        """Test that leading/trailing whitespace in values is handled correctly."""
        # Set credentials with extra whitespace (should still work)
        os.environ["MERAKI_URL"] = "  https://meraki.example.com  "
        os.environ["MERAKI_USERNAME"] = "  admin  "
        os.environ["MERAKI_PASSWORD"] = "  password  "

        result = detect_controller_type()
        assert result == "MERAKI"

    @patch.dict(os.environ, {}, clear=True)
    def test_truly_empty_environment(self) -> None:
        """Test with a completely empty environment."""
        with pytest.raises(ValueError) as exc_info:
            detect_controller_type()

        error_msg = str(exc_info.value)
        assert "No controller credentials found" in error_msg

    def test_three_way_multiple_controllers(self) -> None:
        """Test error message with three controllers configured."""
        # Set credentials for three controllers
        os.environ["ACI_URL"] = "https://apic.example.com"
        os.environ["ACI_USERNAME"] = "aci_user"
        os.environ["ACI_PASSWORD"] = "aci_pass"

        os.environ["CC_URL"] = "https://cc.example.com"
        os.environ["CC_USERNAME"] = "cc_user"
        os.environ["CC_PASSWORD"] = "cc_pass"

        os.environ["ISE_URL"] = "https://ise.example.com"
        os.environ["ISE_USERNAME"] = "ise_user"
        os.environ["ISE_PASSWORD"] = "ise_pass"

        with pytest.raises(ValueError) as exc_info:
            detect_controller_type()

        error_msg = str(exc_info.value)
        assert "Multiple controller credentials detected: ACI, CC, ISE" in error_msg
        assert "To use ACI only:" in error_msg
        assert "To use CC only:" in error_msg
        assert "To use ISE only:" in error_msg

    def test_unicode_in_credentials(self) -> None:
        """Test handling of unicode characters in credentials."""
        # Set credentials with unicode characters
        os.environ["ACI_URL"] = "https://apic.example.com"
        os.environ["ACI_USERNAME"] = "用户名"  # Chinese characters
        os.environ["ACI_PASSWORD"] = "пароль"  # Cyrillic characters

        result = detect_controller_type()
        assert result == "ACI"

    def test_url_with_path_and_query(self) -> None:
        """Test URL values with paths and query parameters."""
        os.environ["SDWAN_URL"] = "https://vmanage.example.com:8443/api/v1?test=true"
        os.environ["SDWAN_USERNAME"] = "admin"
        os.environ["SDWAN_PASSWORD"] = "password"

        result = detect_controller_type()
        assert result == "SDWAN"
