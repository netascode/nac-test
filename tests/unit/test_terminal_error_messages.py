# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Test terminal error message formatting for controller auto-detection."""

from nac_test.utils.terminal import terminal


class TestTerminalErrorMessages:
    """Test the updated error messages for controller auto-detection."""

    def test_format_env_var_error_auto_detection_messaging(self) -> None:
        """Verify error message explains auto-detection and does not mention CONTROLLER_TYPE."""
        # Arrange
        missing_vars = ["ACI_URL", "ACI_PASSWORD"]
        controller_type = "ACI"

        # Act
        error_msg = terminal.format_env_var_error(missing_vars, controller_type)
        plain_msg = terminal.strip_ansi(error_msg)

        # Assert - Check auto-detection messaging
        assert "automatically detects" in plain_msg
        assert "Controller type detected: ACI" in plain_msg
        assert "To switch to a different controller:" in plain_msg
        assert "unset ACI_URL ACI_USERNAME ACI_PASSWORD" in plain_msg

        # Assert - Ensure CONTROLLER_TYPE is NOT mentioned
        assert "CONTROLLER_TYPE" not in plain_msg
        assert "export CONTROLLER_TYPE" not in plain_msg

    def test_format_env_var_error_includes_all_controllers(self) -> None:
        """Verify error message includes examples for all supported controllers."""
        # Arrange
        missing_vars = ["SDWAN_USERNAME"]
        controller_type = "SDWAN"

        # Act
        error_msg = terminal.format_env_var_error(missing_vars, controller_type)
        plain_msg = terminal.strip_ansi(error_msg)

        # Assert - Check all controller types are mentioned
        controllers = ["ACI", "SDWAN", "CC", "MERAKI", "FMC", "ISE"]
        for controller in controllers:
            assert f"{controller}_URL" in plain_msg
            assert f"{controller}_USERNAME" in plain_msg
            assert f"{controller}_PASSWORD" in plain_msg

    def test_format_env_var_error_shows_missing_vars(self) -> None:
        """Verify error message lists all missing variables."""
        # Arrange
        missing_vars = ["CC_URL", "CC_USERNAME", "CC_PASSWORD"]
        controller_type = "CC"

        # Act
        error_msg = terminal.format_env_var_error(missing_vars, controller_type)
        plain_msg = terminal.strip_ansi(error_msg)

        # Assert - All missing vars are shown
        for var in missing_vars:
            assert var in plain_msg

    def test_format_env_var_error_actionable_instructions(self) -> None:
        """Verify error message provides clear actionable instructions."""
        # Arrange
        missing_vars = ["MERAKI_PASSWORD"]
        controller_type = "MERAKI"

        # Act
        error_msg = terminal.format_env_var_error(missing_vars, controller_type)
        plain_msg = terminal.strip_ansi(error_msg)

        # Assert - Check for actionable instructions
        assert "unset MERAKI_URL MERAKI_USERNAME MERAKI_PASSWORD" in plain_msg
        assert "Then set credentials for your desired controller:" in plain_msg
        assert "export MERAKI_URL" in plain_msg
        assert "export MERAKI_USERNAME" in plain_msg
        assert "export MERAKI_PASSWORD" in plain_msg
