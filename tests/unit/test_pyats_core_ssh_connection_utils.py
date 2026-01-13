
"""Unit tests for nac_test.pyats_core.ssh.connection_utils module."""

from unittest.mock import patch

import pytest

from nac_test.pyats_core.ssh.connection_utils import (
    _build_console_command,
    _build_ssh_command,
    _build_telnet_command,
    build_connection_start_command,
    build_connection_start_list,
    determine_chassis_type,
)


class TestBuildConnectionStartCommand:
    """Test cases for build_connection_start_command function."""

    def test_ssh_basic(self):
        """Test basic SSH command construction."""
        result = build_connection_start_command("ssh", "10.90.41.178")
        assert result == "ssh 10.90.41.178"

    def test_ssh_with_username(self):
        """Test SSH command with username."""
        result = build_connection_start_command("ssh", "10.90.41.178", username="admin")
        assert result == "ssh admin@10.90.41.178"

    def test_ssh_with_port(self):
        """Test SSH command with custom port."""
        result = build_connection_start_command("ssh", "10.90.41.178", port=2222)
        assert result == "ssh 10.90.41.178 -p 2222"

    def test_ssh_with_username_and_port(self):
        """Test SSH command with username and port."""
        result = build_connection_start_command(
            "ssh", "10.90.41.178", username="admin", port=2222
        )
        assert result == "ssh admin@10.90.41.178 -p 2222"

    def test_ssh_with_options(self):
        """Test SSH command with additional options."""
        result = build_connection_start_command(
            "ssh",
            "10.90.41.178",
            username="admin",
            ssh_options="-o StrictHostKeyChecking=no",
        )
        assert result == "ssh admin@10.90.41.178 -o StrictHostKeyChecking=no"

    def test_ssh_with_all_parameters(self):
        """Test SSH command with all parameters."""
        result = build_connection_start_command(
            "ssh",
            "10.90.41.178",
            port=2222,
            username="admin",
            ssh_options="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
        )
        assert (
            result
            == "ssh admin@10.90.41.178 -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
        )

    def test_telnet_basic(self):
        """Test basic Telnet command construction."""
        result = build_connection_start_command("telnet", "192.168.1.1")
        assert result == "telnet 192.168.1.1"

    def test_telnet_with_port(self):
        """Test Telnet command with custom port."""
        result = build_connection_start_command("telnet", "192.168.1.1", port=23)
        assert result == "telnet 192.168.1.1 23"

    def test_console_basic(self):
        """Test console command construction."""
        result = build_connection_start_command("console", "/dev/ttyS0")
        assert result == "cu -l /dev/ttyS0"

    def test_protocol_case_insensitive(self):
        """Test that protocol is case insensitive."""
        result1 = build_connection_start_command("SSH", "10.90.41.178")
        result2 = build_connection_start_command("ssh", "10.90.41.178")
        result3 = build_connection_start_command("Ssh", "10.90.41.178")
        assert result1 == result2 == result3 == "ssh 10.90.41.178"

    def test_protocol_with_whitespace(self):
        """Test protocol with leading/trailing whitespace."""
        result = build_connection_start_command("  ssh  ", "10.90.41.178")
        assert result == "ssh 10.90.41.178"

    def test_invalid_protocol(self):
        """Test error handling for invalid protocol."""
        with pytest.raises(ValueError, match="Unsupported protocol: ftp"):
            build_connection_start_command("ftp", "10.90.41.178")

    def test_empty_protocol(self):
        """Test error handling for empty protocol."""
        with pytest.raises(ValueError, match="Protocol cannot be None or empty"):
            build_connection_start_command("", "10.90.41.178")

    def test_none_protocol(self):
        """Test error handling for None protocol."""
        with pytest.raises(ValueError, match="Protocol cannot be None or empty"):
            build_connection_start_command(None, "10.90.41.178")

    def test_empty_host(self):
        """Test error handling for empty host."""
        with pytest.raises(ValueError, match="Host cannot be None or empty"):
            build_connection_start_command("ssh", "")

    def test_none_host(self):
        """Test error handling for None host."""
        with pytest.raises(ValueError, match="Host cannot be None or empty"):
            build_connection_start_command("ssh", None)


class TestBuildSshCommand:
    """Test cases for _build_ssh_command function."""

    def test_basic_ssh(self):
        """Test basic SSH command."""
        result = _build_ssh_command("10.90.41.178")
        assert result == "ssh 10.90.41.178"

    def test_ssh_with_username(self):
        """Test SSH with username."""
        result = _build_ssh_command("10.90.41.178", username="admin")
        assert result == "ssh admin@10.90.41.178"

    def test_ssh_with_port(self):
        """Test SSH with port."""
        result = _build_ssh_command("10.90.41.178", port=2222)
        assert result == "ssh 10.90.41.178 -p 2222"

    def test_ssh_invalid_port_zero(self):
        """Test SSH with invalid port (zero)."""
        with pytest.raises(ValueError, match="Invalid port number: 0"):
            _build_ssh_command("10.90.41.178", port=0)

    def test_ssh_invalid_port_negative(self):
        """Test SSH with invalid port (negative)."""
        with pytest.raises(ValueError, match="Invalid port number: -1"):
            _build_ssh_command("10.90.41.178", port=-1)

    def test_ssh_invalid_port_too_large(self):
        """Test SSH with invalid port (too large)."""
        with pytest.raises(ValueError, match="Invalid port number: 65536"):
            _build_ssh_command("10.90.41.178", port=65536)

    def test_ssh_invalid_port_non_integer(self):
        """Test SSH with non-integer port."""
        with pytest.raises(ValueError, match="Invalid port number: abc"):
            _build_ssh_command("10.90.41.178", port="abc")

    def test_ssh_options_with_leading_dash(self):
        """Test SSH options that start with dash."""
        result = _build_ssh_command(
            "10.90.41.178", ssh_options="-o StrictHostKeyChecking=no"
        )
        assert result == "ssh 10.90.41.178 -o StrictHostKeyChecking=no"

    @patch("nac_test.pyats_core.ssh.connection_utils.logger")
    def test_ssh_options_without_leading_dash(self, mock_logger):
        """Test SSH options that don't start with dash (should warn)."""
        result = _build_ssh_command(
            "10.90.41.178", ssh_options="StrictHostKeyChecking=no"
        )
        assert result == "ssh 10.90.41.178 StrictHostKeyChecking=no"
        mock_logger.warning.assert_called_once()

    def test_ssh_options_with_whitespace(self):
        """Test SSH options with leading/trailing whitespace."""
        result = _build_ssh_command(
            "10.90.41.178", ssh_options="  -o StrictHostKeyChecking=no  "
        )
        assert result == "ssh 10.90.41.178 -o StrictHostKeyChecking=no"


class TestBuildTelnetCommand:
    """Test cases for _build_telnet_command function."""

    def test_basic_telnet(self):
        """Test basic Telnet command."""
        result = _build_telnet_command("192.168.1.1")
        assert result == "telnet 192.168.1.1"

    def test_telnet_with_port(self):
        """Test Telnet with port."""
        result = _build_telnet_command("192.168.1.1", port=23)
        assert result == "telnet 192.168.1.1 23"

    def test_telnet_invalid_port_zero(self):
        """Test Telnet with invalid port (zero)."""
        with pytest.raises(ValueError, match="Invalid port number: 0"):
            _build_telnet_command("192.168.1.1", port=0)

    def test_telnet_invalid_port_negative(self):
        """Test Telnet with invalid port (negative)."""
        with pytest.raises(ValueError, match="Invalid port number: -1"):
            _build_telnet_command("192.168.1.1", port=-1)

    def test_telnet_invalid_port_too_large(self):
        """Test Telnet with invalid port (too large)."""
        with pytest.raises(ValueError, match="Invalid port number: 65536"):
            _build_telnet_command("192.168.1.1", port=65536)


class TestBuildConsoleCommand:
    """Test cases for _build_console_command function."""

    def test_console_command(self):
        """Test console command construction."""
        result = _build_console_command("/dev/ttyS0")
        assert result == "cu -l /dev/ttyS0"

    def test_console_command_different_path(self):
        """Test console command with different device path."""
        result = _build_console_command("/dev/ttyUSB0")
        assert result == "cu -l /dev/ttyUSB0"


class TestBuildConnectionStartList:
    """Test cases for build_connection_start_list function."""

    def test_single_connection(self):
        """Test single connection in list."""
        connections = [{"protocol": "ssh", "host": "10.90.41.178", "username": "admin"}]
        result = build_connection_start_list(connections)
        assert result == ["ssh admin@10.90.41.178"]

    def test_dual_connections(self):
        """Test dual connections for HA setup."""
        connections = [
            {"protocol": "ssh", "host": "10.90.41.178", "username": "admin"},
            {"protocol": "ssh", "host": "10.90.41.179", "username": "admin"},
        ]
        result = build_connection_start_list(connections)
        assert result == ["ssh admin@10.90.41.178", "ssh admin@10.90.41.179"]

    def test_mixed_protocols(self):
        """Test mixed protocol connections."""
        connections = [
            {
                "protocol": "ssh",
                "host": "10.90.41.178",
                "username": "admin",
                "port": 22,
            },
            {"protocol": "telnet", "host": "10.90.41.179", "port": 23},
        ]
        result = build_connection_start_list(connections)
        assert result == ["ssh admin@10.90.41.178 -p 22", "telnet 10.90.41.179 23"]

    def test_empty_connections_list(self):
        """Test error handling for empty connections list."""
        with pytest.raises(ValueError, match="Connections list cannot be empty"):
            build_connection_start_list([])

    def test_invalid_connection_missing_protocol(self):
        """Test error handling for missing protocol."""
        connections = [{"host": "10.90.41.178"}]
        with pytest.raises(ValueError, match="Invalid connection at index 0"):
            build_connection_start_list(connections)

    def test_invalid_connection_missing_host(self):
        """Test error handling for missing host."""
        connections = [{"protocol": "ssh"}]
        with pytest.raises(ValueError, match="Invalid connection at index 0"):
            build_connection_start_list(connections)

    def test_invalid_connection_in_middle(self):
        """Test error handling for invalid connection in middle of list."""
        connections = [
            {"protocol": "ssh", "host": "10.90.41.178", "username": "admin"},
            {"protocol": "invalid", "host": "10.90.41.179"},  # Invalid protocol
            {"protocol": "ssh", "host": "10.90.41.180", "username": "admin"},
        ]
        with pytest.raises(ValueError, match="Invalid connection at index 1"):
            build_connection_start_list(connections)


class TestDetermineChassisType:
    """Test cases for determine_chassis_type function."""

    def test_single_rp(self):
        """Test single RP chassis type."""
        result = determine_chassis_type(1)
        assert result == "single_rp"

    def test_dual_rp(self):
        """Test dual RP chassis type."""
        result = determine_chassis_type(2)
        assert result == "dual_rp"

    def test_stack_three_connections(self):
        """Test stack chassis type with 3 connections."""
        result = determine_chassis_type(3)
        assert result == "stack"

    def test_stack_many_connections(self):
        """Test stack chassis type with many connections."""
        result = determine_chassis_type(8)
        assert result == "stack"

    def test_zero_connections(self):
        """Test edge case with zero connections."""
        result = determine_chassis_type(0)
        assert result == "stack"  # Falls through to else case


class TestIntegrationScenarios:
    """Integration test scenarios that simulate real-world usage."""

    def test_single_rp_device_construction(self):
        """Test complete single RP device construction scenario."""
        # Build start command
        start_cmd = build_connection_start_command(
            protocol="ssh", host="10.90.41.178", username="admin", port=22
        )

        # Determine chassis type
        chassis_type = determine_chassis_type(1)

        # Verify expected values for Connection construction
        assert start_cmd == "ssh admin@10.90.41.178 -p 22"
        assert chassis_type == "single_rp"

        # These would be used like:
        # conn = Connection(
        #     hostname='device1',
        #     start=[start_cmd],
        #     os='iosxe',
        #     chassis_type=chassis_type
        # )

    def test_dual_rp_ha_device_construction(self):
        """Test complete dual RP HA device construction scenario."""
        connections = [
            {"protocol": "ssh", "host": "10.90.41.178", "username": "admin"},
            {"protocol": "ssh", "host": "10.90.41.179", "username": "admin"},
        ]

        # Build start commands
        start_commands = build_connection_start_list(connections)

        # Determine chassis type
        chassis_type = determine_chassis_type(len(connections))

        # Verify expected values
        assert start_commands == ["ssh admin@10.90.41.178", "ssh admin@10.90.41.179"]
        assert chassis_type == "dual_rp"

    def test_telnet_console_mixed_scenario(self):
        """Test mixed protocol scenario (Telnet + Console)."""
        connections = [
            {"protocol": "telnet", "host": "192.168.1.1", "port": 23},
            {"protocol": "console", "host": "/dev/ttyS0"},
        ]

        start_commands = build_connection_start_list(connections)
        chassis_type = determine_chassis_type(len(connections))

        assert start_commands == ["telnet 192.168.1.1 23", "cu -l /dev/ttyS0"]
        assert chassis_type == "dual_rp"

    def test_complex_ssh_options_scenario(self):
        """Test complex SSH options scenario."""
        start_cmd = build_connection_start_command(
            protocol="ssh",
            host="10.90.41.178",
            username="admin",
            port=2222,
            ssh_options="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=30",
        )

        expected = "ssh admin@10.90.41.178 -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=30"
        assert start_cmd == expected

    def test_stack_scenario(self):
        """Test stack scenario with multiple switches."""
        connections = [
            {"protocol": "ssh", "host": "10.90.41.178", "username": "admin"},
            {"protocol": "ssh", "host": "10.90.41.179", "username": "admin"},
            {"protocol": "ssh", "host": "10.90.41.180", "username": "admin"},
            {"protocol": "ssh", "host": "10.90.41.181", "username": "admin"},
        ]

        start_commands = build_connection_start_list(connections)
        chassis_type = determine_chassis_type(len(connections))

        assert len(start_commands) == 4
        assert all("ssh admin@" in cmd for cmd in start_commands)
        assert chassis_type == "stack"


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases."""

    def test_port_edge_cases(self):
        """Test port number edge cases."""
        # Valid edge cases
        assert (
            _build_ssh_command("host", port=1) == "ssh host -p 1"
        )  # Minimum valid port
        assert (
            _build_ssh_command("host", port=65535) == "ssh host -p 65535"
        )  # Maximum valid port

        # Invalid edge cases
        with pytest.raises(ValueError):
            _build_ssh_command("host", port=0)
        with pytest.raises(ValueError):
            _build_ssh_command("host", port=65536)

    def test_username_edge_cases(self):
        """Test username edge cases."""
        # Empty username should not use @ format
        result = _build_ssh_command("host", username="")
        assert result == "ssh host"  # Empty username should not include @

        # Username with special characters
        result = _build_ssh_command("host", username="admin-user_123")
        assert result == "ssh admin-user_123@host"

    def test_host_edge_cases(self):
        """Test host edge cases."""
        # IPv6 address
        result = build_connection_start_command("ssh", "2001:db8::1")
        assert result == "ssh 2001:db8::1"

        # Hostname with dots
        result = build_connection_start_command("ssh", "router.example.com")
        assert result == "ssh router.example.com"

        # IP with port
        result = build_connection_start_command("ssh", "192.168.1.1", port=2222)
        assert result == "ssh 192.168.1.1 -p 2222"
