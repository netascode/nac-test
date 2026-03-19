# -*- coding: utf-8 -*-

"""Unit tests for ConnectionManager integration with connection_utils.

These tests verify that the ConnectionManager correctly uses connection_utils
to resolve the "list index out of range" error when creating Connection objects.
"""

import pytest
from unittest.mock import Mock, patch

from nac_test.pyats_core.ssh.connection_manager import DeviceConnectionManager


class TestConnectionManagerUtilsIntegration:
    """Test ConnectionManager integration with connection_utils."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = DeviceConnectionManager(max_concurrent=5)
        self.device_info = {
            "host": "10.90.41.178",
            "username": "admin",
            "password": "secret123",
            "platform": "iosxe",
        }

    @patch("unicon.Connection")
    def test_unicon_connect_uses_start_parameter(self, mock_connection_class):
        """Test that _unicon_connect creates Connection with start parameter."""
        # Setup mock
        mock_conn = Mock()
        mock_connection_class.return_value = mock_conn

        # Call the internal method directly (synchronous)
        result = self.manager._unicon_connect(self.device_info)

        # Verify Connection was called with start parameter
        mock_connection_class.assert_called_once()
        call_kwargs = mock_connection_class.call_args[1]

        # The key assertion - start parameter should be present
        assert "start" in call_kwargs, (
            "Connection should be created with start parameter"
        )
        assert isinstance(call_kwargs["start"], list), "start should be a list"
        assert len(call_kwargs["start"]) == 1, "start should have one command"
        assert call_kwargs["start"][0] == "ssh admin@10.90.41.178", (
            f"Expected 'ssh admin@10.90.41.178', got {call_kwargs['start'][0]}"
        )

        # Verify other key parameters
        assert call_kwargs["hostname"] == "10.90.41.178"
        assert call_kwargs["username"] == "admin"
        assert call_kwargs["password"] == "secret123"
        assert call_kwargs["platform"] == "iosxe"
        assert call_kwargs["chassis_type"] == "single_rp"

        # Verify connect was called and result returned
        mock_conn.connect.assert_called_once()
        assert result == mock_conn

    @patch("unicon.Connection")
    def test_start_command_with_custom_port(self, mock_connection_class):
        """Test start command construction with custom port."""
        device_info_with_port = {**self.device_info, "port": 2222}

        mock_conn = Mock()
        mock_connection_class.return_value = mock_conn

        self.manager._unicon_connect(device_info_with_port)

        call_kwargs = mock_connection_class.call_args[1]
        assert call_kwargs["start"][0] == "ssh admin@10.90.41.178 -p 2222"

    @patch("unicon.Connection")
    def test_start_command_with_ssh_options(self, mock_connection_class):
        """Test start command construction with SSH options."""
        device_info_with_options = {
            **self.device_info,
            "ssh_options": "-o StrictHostKeyChecking=no",
        }

        mock_conn = Mock()
        mock_connection_class.return_value = mock_conn

        self.manager._unicon_connect(device_info_with_options)

        call_kwargs = mock_connection_class.call_args[1]
        assert (
            call_kwargs["start"][0]
            == "ssh admin@10.90.41.178 -o StrictHostKeyChecking=no"
        )

    @patch("unicon.Connection")
    def test_start_command_with_telnet_protocol(self, mock_connection_class):
        """Test start command construction with Telnet protocol."""
        device_info_telnet = {**self.device_info, "protocol": "telnet", "port": 23}

        mock_conn = Mock()
        mock_connection_class.return_value = mock_conn

        self.manager._unicon_connect(device_info_telnet)

        call_kwargs = mock_connection_class.call_args[1]
        assert call_kwargs["start"][0] == "telnet 10.90.41.178 23"

    @patch("unicon.Connection")
    def test_chassis_type_determination(self, mock_connection_class):
        """Test chassis type determination using connection_utils."""
        mock_conn = Mock()
        mock_connection_class.return_value = mock_conn

        # Test default chassis type
        self.manager._unicon_connect(self.device_info)
        call_kwargs = mock_connection_class.call_args[1]
        assert call_kwargs["chassis_type"] == "single_rp"

        # Test custom chassis type preservation
        device_info_custom = {**self.device_info, "chassis_type": "dual_rp"}
        self.manager._unicon_connect(device_info_custom)
        call_kwargs = mock_connection_class.call_args[1]
        assert call_kwargs["chassis_type"] == "dual_rp"

    def test_connection_command_build_error_handling(self):
        """Test error handling when connection command building fails."""
        # Use invalid protocol to trigger connection_utils error
        invalid_device_info = {**self.device_info, "protocol": "invalid_protocol"}

        # Should raise ConnectionError with helpful message
        with pytest.raises(Exception) as exc_info:
            self.manager._unicon_connect(invalid_device_info)

        error_message = str(exc_info.value)
        assert (
            "Failed to build connection command" in error_message
            or "Unsupported protocol" in error_message
        )

    @patch("unicon.Connection")
    def test_before_and_after_fix_demonstration(self, mock_connection_class):
        """Test demonstrating the before/after fix for IndexError."""
        mock_conn = Mock()
        mock_connection_class.return_value = mock_conn

        # Call the updated method
        self.manager._unicon_connect(self.device_info)

        # Verify the fix
        call_kwargs = mock_connection_class.call_args[1]

        # BEFORE: Connection would be called without start parameter
        # This would cause: IndexError: list index out of range at unicon/bases/routers/connection.py:158
        # because self.start would be None or empty, and accessing self.start[0] would fail

        # AFTER: Connection is called with start parameter
        assert "start" in call_kwargs, "The key fix - start parameter must be present"
        assert call_kwargs["start"] == ["ssh admin@10.90.41.178"], (
            "start[0] now provides the missing command"
        )

        # This resolves the IndexError because:
        # - self.start is now ["ssh admin@10.90.41.178"] instead of None/empty
        # - self.start[0] returns "ssh admin@10.90.41.178" instead of raising IndexError
        # - Unicon can properly parse and execute the SSH connection command

    @patch("unicon.Connection")
    def test_complex_real_world_scenario(self, mock_connection_class):
        """Test complex real-world scenario with all parameters."""
        complex_device_info = {
            "host": "192.168.1.100",
            "username": "netadmin",
            "password": "complex_password_123",
            "protocol": "ssh",
            "port": 2222,
            "ssh_options": "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
            "platform": "iosxr",
            "chassis_type": "dual_rp",
            "timeout": 300,
        }

        mock_conn = Mock()
        mock_connection_class.return_value = mock_conn

        self.manager._unicon_connect(complex_device_info)

        call_kwargs = mock_connection_class.call_args[1]

        # Verify complex start command construction
        expected_start_command = "ssh netadmin@192.168.1.100 -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
        assert call_kwargs["start"] == [expected_start_command]

        # Verify all other parameters
        assert call_kwargs["hostname"] == "192.168.1.100"
        assert call_kwargs["username"] == "netadmin"
        assert call_kwargs["password"] == "complex_password_123"
        assert call_kwargs["platform"] == "iosxr"
        assert call_kwargs["chassis_type"] == "dual_rp"
        assert call_kwargs["timeout"] == 300

    @patch("nac_test.pyats_core.ssh.connection_manager.build_connection_start_command")
    @patch("unicon.Connection")
    def test_connection_utils_functions_are_called(
        self, mock_connection_class, mock_build_command
    ):
        """Test that connection_utils functions are actually called."""
        # Setup mocks
        mock_build_command.return_value = "ssh admin@10.90.41.178"
        mock_conn = Mock()
        mock_connection_class.return_value = mock_conn

        # Call method
        self.manager._unicon_connect(self.device_info)

        # Verify connection_utils function was called
        mock_build_command.assert_called_once_with(
            protocol="ssh",
            host="10.90.41.178",
            username="admin",
            port=None,
            ssh_options=None,
        )

        # Verify the result was used in Connection creation
        call_kwargs = mock_connection_class.call_args[1]
        assert call_kwargs["start"] == ["ssh admin@10.90.41.178"]


class TestConnectionManagerErrorFormatting:
    """Test that error formatting still works with the updated connection logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = DeviceConnectionManager(max_concurrent=5)

    def test_format_connection_error_includes_connection_details(self):
        """Test that connection error formatting includes relevant details."""
        device_info = {"host": "10.90.41.178", "username": "admin", "platform": "iosxe"}

        # Create a mock connection error
        from unicon.core.errors import ConnectionError as UniconConnectionError

        error = UniconConnectionError("failed to connect")

        # Format the error
        formatted_error = self.manager._format_connection_error(
            "test-device", device_info, error
        )

        # Verify error message contains relevant information
        assert "Connection failure for device 'test-device'" in formatted_error
        assert "Host: 10.90.41.178" in formatted_error
        assert "Platform: iosxe" in formatted_error
        assert "Failed to establish SSH connection" in formatted_error

    def test_format_auth_error_includes_auth_details(self):
        """Test that authentication error formatting includes auth details."""
        device_info = {"host": "10.90.41.178", "username": "admin"}

        # Create a mock auth error
        from unicon.core.errors import CredentialsExhaustedError

        error = CredentialsExhaustedError("credentials exhausted")

        # Format the error
        formatted_error = self.manager._format_auth_error(
            "test-device", device_info, error
        )

        # Verify error message contains auth information
        assert "Authentication failure for device 'test-device'" in formatted_error
        assert "Host: 10.90.41.178" in formatted_error
        assert "Username: admin" in formatted_error
        assert "Verify the username and password are correct" in formatted_error
