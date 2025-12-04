# -*- coding: utf-8 -*-

"""Unicon connection utilities for manual Connection object construction.

This module provides helper functions to construct Unicon Connection objects
outside of the pyATS testbed framework, addressing the IndexError that occurs
when the 'start' parameter is missing or improperly formatted.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def build_connection_start_command(
    protocol: str,
    host: str,
    port: Optional[int] = None,
    username: Optional[str] = None,
    ssh_options: Optional[str] = None,
) -> str:
    """Build Unicon start command similar to get_start_command() from topology.py.

    This function mimics the logic from unicon.adapters.topology.get_start_command()
    to construct connection commands for manual Unicon Connection object creation.

    Args:
        protocol: Connection protocol ('ssh', 'telnet', 'console')
        host: IP address, hostname, or device path
        port: Port number (optional)
        username: SSH username for user@host format (optional)
        ssh_options: Additional SSH options like '-o StrictHostKeyChecking=no' (optional)

    Returns:
        Complete connection command string

    Raises:
        ValueError: If protocol is not supported
        ValueError: If required parameters are missing or invalid

    Examples:
        >>> build_connection_start_command('ssh', '10.90.41.178')
        'ssh 10.90.41.178'

        >>> build_connection_start_command('ssh', '10.90.41.178', username='admin', port=2222)
        'ssh admin@10.90.41.178 -p 2222'

        >>> build_connection_start_command('telnet', '192.168.1.1', port=23)
        'telnet 192.168.1.1 23'

        >>> build_connection_start_command('console', '/dev/ttyS0')
        'cu -l /dev/ttyS0'
    """
    if not protocol:
        raise ValueError("Protocol cannot be None or empty")

    if not host:
        raise ValueError("Host cannot be None or empty")

    protocol = protocol.lower().strip()

    if protocol == "ssh":
        return _build_ssh_command(host, port, username, ssh_options)
    elif protocol == "telnet":
        return _build_telnet_command(host, port)
    elif protocol == "console":
        return _build_console_command(host)
    else:
        raise ValueError(
            f"Unsupported protocol: {protocol}. Supported protocols: ssh, telnet, console"
        )


def _build_ssh_command(
    host: str,
    port: Optional[int] = None,
    username: Optional[str] = None,
    ssh_options: Optional[str] = None,
) -> str:
    """Build SSH connection command.

    Args:
        host: IP address or hostname
        port: SSH port (default 22)
        username: SSH username
        ssh_options: Additional SSH options

    Returns:
        SSH command string
    """
    if username:
        cmd = f"ssh {username}@{host}"
    else:
        cmd = f"ssh {host}"

    if port is not None:
        if not isinstance(port, int) or port <= 0 or port > 65535:
            raise ValueError(
                f"Invalid port number: {port}. Must be integer between 1-65535"
            )
        cmd = f"{cmd} -p {port}"

    if ssh_options:
        # Ensure ssh_options is properly formatted (starts with space if not)
        ssh_options = ssh_options.strip()
        if ssh_options and not ssh_options.startswith("-"):
            logger.warning(f"SSH options should start with '-': {ssh_options}")
        cmd = f"{cmd} {ssh_options}"

    return cmd


def _build_telnet_command(host: str, port: Optional[int] = None) -> str:
    """Build Telnet connection command.

    Args:
        host: IP address or hostname
        port: Telnet port (default 23)

    Returns:
        Telnet command string
    """
    cmd = f"telnet {host}"

    if port is not None:
        if not isinstance(port, int) or port <= 0 or port > 65535:
            raise ValueError(
                f"Invalid port number: {port}. Must be integer between 1-65535"
            )
        cmd = f"{cmd} {port}"

    return cmd


def _build_console_command(device_path: str) -> str:
    """Build console connection command.

    Args:
        device_path: Serial device path (e.g., '/dev/ttyS0')

    Returns:
        Console command string
    """
    # For console connections, the host is typically a device path
    return f"cu -l {device_path}"


def build_connection_start_list(
    connections: List[dict],
) -> List[str]:
    """Build a list of start commands for multi-connection scenarios.

    Useful for dual RP/HA connections where multiple connection commands are needed.

    Args:
        connections: List of connection dictionaries, each containing:
            - protocol: Connection protocol
            - host: IP address or hostname
            - port (optional): Port number
            - username (optional): Username
            - ssh_options (optional): SSH options

    Returns:
        List of connection command strings

    Examples:
        >>> connections = [
        ...     {'protocol': 'ssh', 'host': '10.90.41.178', 'username': 'admin'},
        ...     {'protocol': 'ssh', 'host': '10.90.41.179', 'username': 'admin'}
        ... ]
        >>> build_connection_start_list(connections)
        ['ssh admin@10.90.41.178', 'ssh admin@10.90.41.179']
    """
    if not connections:
        raise ValueError("Connections list cannot be empty")

    start_commands = []
    for i, conn in enumerate(connections):
        try:
            cmd = build_connection_start_command(
                protocol=conn.get("protocol"),
                host=conn.get("host"),
                port=conn.get("port"),
                username=conn.get("username"),
                ssh_options=conn.get("ssh_options"),
            )
            start_commands.append(cmd)
        except (ValueError, KeyError) as e:
            raise ValueError(f"Invalid connection at index {i}: {e}") from e

    return start_commands


def determine_chassis_type(connection_count: int) -> str:
    """Determine appropriate chassis_type based on connection count.

    Args:
        connection_count: Number of connections

    Returns:
        Chassis type string ('single_rp', 'dual_rp', 'stack')

    Examples:
        >>> determine_chassis_type(1)
        'single_rp'
        >>> determine_chassis_type(2)
        'dual_rp'
        >>> determine_chassis_type(4)
        'stack'
    """
    if connection_count == 1:
        return "single_rp"
    elif connection_count == 2:
        return "dual_rp"
    else:
        return "stack"
