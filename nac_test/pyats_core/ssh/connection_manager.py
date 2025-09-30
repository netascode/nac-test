# -*- coding: utf-8 -*-

"""Device connection manager for SSH testing.

This module provides connection management for SSH-based device testing,
including connection pooling, resource limits, and per-device locking.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, Optional

# Only import for type checking to avoid early PyATS initialization
if TYPE_CHECKING:
    from unicon import Connection

from nac_test.pyats_core.ssh.connection_utils import (
    build_connection_start_command,
    determine_chassis_type,
)
from nac_test.utils.system_resources import SystemResourceCalculator

logger = logging.getLogger(__name__)


class DeviceConnectionManager:
    """Manages SSH connections with per-device locking and resource limits.

    This class ensures orderly device access by:
    - Limiting total concurrent SSH connections
    - Providing one connection per device (with per-device locking)
    - Managing connection lifecycle and cleanup
    - Respecting system resource limits
    """

    def __init__(self, max_concurrent: Optional[int] = None):
        """Initialize the device connection manager.

        Args:
            max_concurrent: Maximum concurrent SSH connections. If None,
                           will be calculated based on system resources.
        """
        self.max_concurrent = max_concurrent or self._calculate_ssh_capacity()
        self.device_locks: Dict[str, asyncio.Lock] = {}
        self.connections: Dict[str, Any] = {}  # Changed from Connection to avoid import
        self.semaphore = asyncio.Semaphore(self.max_concurrent)

        logger.info(
            f"Initialized DeviceConnectionManager with max_concurrent={self.max_concurrent}"
        )

    def _calculate_ssh_capacity(self) -> int:
        """Calculate maximum safe SSH connections based on system resources.

        Returns:
            Maximum number of concurrent SSH connections
        """
        return SystemResourceCalculator.calculate_connection_capacity(
            memory_per_connection_mb=10.0,  # 10MB per SSH connection
            fds_per_connection=5,  # 5 FDs per SSH connection
            max_connections=1000,  # Cap at 1000 connections
            env_var="MAX_SSH_CONNECTIONS",
        )

    async def get_connection(
        self, hostname: str, device_info: Dict[str, Any]
    ) -> Any:  # Changed from Connection to avoid import
        """Get or create SSH connection for a device.

        This method ensures that only one connection exists per device at a time
        and respects the global connection limit.

        Args:
            hostname: Unique device identifier
            device_info: Device connection information containing:
                - host: Device IP address or hostname
                - username: SSH username
                - password: SSH password
                - platform: Device platform (ios, iosxr, nxos, etc.)
                - timeout: Connection timeout (optional)

        Returns:
            Unicon Connection object for the device

        Raises:
            ConnectionError: If connection cannot be established
        """
        # Ensure one connection per device
        if hostname not in self.device_locks:
            self.device_locks[hostname] = asyncio.Lock()

        async with self.device_locks[hostname]:
            # Return existing connection if available
            if hostname in self.connections:
                conn = self.connections[hostname]
                if self._is_connection_healthy(conn):
                    logger.debug(f"Reusing existing connection for {hostname}")
                    return conn
                else:
                    # Connection is unhealthy, remove it
                    logger.warning(f"Removing unhealthy connection for {hostname}")
                    await self._close_connection_internal(hostname)

            # Create new connection
            return await self._create_connection(hostname, device_info)

    async def _create_connection(
        self, hostname: str, device_info: Dict[str, Any]
    ) -> Any:  # Changed from Connection to avoid import
        """Create new SSH connection for a device.

        Args:
            hostname: Unique device identifier
            device_info: Device connection information

        Returns:
            New Unicon Connection object

        Raises:
            ConnectionError: With detailed error information about the failure type
        """
        # Import unicon exceptions here to delay PyATS initialization
        from unicon.core.errors import (
            ConnectionError,
            CredentialsExhaustedError,
            StateMachineError,
            TimeoutError as UniconTimeoutError,
        )

        # Respect global connection limit
        async with self.semaphore:
            host = device_info.get("host", "unknown")
            logger.info(f"Creating SSH connection to {hostname} at {host}")

            try:
                # Run Unicon connection in thread pool (since it's synchronous)
                loop = asyncio.get_event_loop()
                conn = await loop.run_in_executor(
                    None, self._unicon_connect, device_info
                )

                # Store connection
                self.connections[hostname] = conn
                logger.info(f"Successfully connected to {hostname}")

                return conn

            except CredentialsExhaustedError as e:
                # Authentication failure - no point retrying
                error_msg = self._format_auth_error(hostname, device_info, e)
                logger.error(error_msg, exc_info=True)
                raise ConnectionError(error_msg) from e

            except (ConnectionError, StateMachineError, UniconTimeoutError) as e:
                # Connection-related errors
                error_msg = self._format_connection_error(hostname, device_info, e)
                logger.error(error_msg, exc_info=True)
                raise ConnectionError(error_msg) from e

            except Exception as e:
                # Unexpected errors
                error_msg = self._format_unexpected_error(hostname, device_info, e)
                logger.error(error_msg, exc_info=True)
                raise ConnectionError(error_msg) from e

    def _unicon_connect(
        self, device_info: Dict[str, Any]
    ) -> Any:  # Changed from Connection to avoid import
        """Create Unicon connection (runs in thread pool).

        Args:
            device_info: Device connection information containing:
                - host: Device IP address or hostname
                - username: SSH username
                - password: SSH password
                - platform: Device platform (optional)
                - protocol: Connection protocol (optional, defaults to 'ssh')
                - port: SSH port (optional, defaults to 22)
                - ssh_options: Additional SSH options (optional)
                - chassis_type: Device chassis type (optional, auto-determined)
                - timeout: Connection timeout (optional, defaults to 120)

        Returns:
            Connected Unicon Connection object

        Raises:
            Exception: Any exception from Unicon connection attempt
        """
        # Import unicon here to delay PyATS initialization until actually needed
        from unicon import Connection

        # Extract connection details
        host = device_info["host"]
        username = device_info["username"]
        protocol = device_info.get("protocol", "ssh")  # Default to SSH
        port = device_info.get("port")  # Optional port
        ssh_options = device_info.get("ssh_options")  # Optional SSH options

        # Build the connection start command using our utility
        # This resolves the "list index out of range" error by providing the missing start parameter
        try:
            start_command = build_connection_start_command(
                protocol=protocol,
                host=host,
                username=username,
                port=port,
                ssh_options=ssh_options,
            )
        except ValueError as e:
            raise ConnectionError(f"Failed to build connection command: {e}") from e

        # Determine chassis type (can be overridden in device_info)
        chassis_type = device_info.get("chassis_type")
        if not chassis_type:
            # Default to single_rp for single connection
            chassis_type = determine_chassis_type(1)

        # Build connection parameters with the start command
        connection_params = {
            "hostname": host,
            "start": [start_command],
            "username": username,
            "password": device_info["password"],
            "platform": device_info.get("platform"),
            "timeout": device_info.get("timeout", 120),
            # Chassis type MUST be defined for the connection to successfully
            # establish.
            "chassis_type": chassis_type,
            "init_exec_commands": [],
            "init_config_commands": [],
        }

        logger.debug(f"Creating Connection with start command: {start_command}")

        # Create and connect - let exceptions bubble up
        conn = Connection(**connection_params)
        conn.connect()

        return conn

    def _is_connection_healthy(
        self, conn: Any
    ) -> bool:  # Changed from Connection to avoid import
        """Check if connection is healthy and usable.

        Args:
            conn: Unicon Connection object

        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            return conn.connected and hasattr(conn, "spawn") and conn.spawn
        except Exception:
            return False

    def _format_connection_error(
        self, hostname: str, device_info: Dict[str, Any], error: Exception
    ) -> str:
        """Format connection error with detailed information.

        Args:
            hostname: Device identifier
            device_info: Device connection information
            error: The connection exception that occurred

        Returns:
            Formatted error message with troubleshooting hints
        """
        # Import unicon exceptions here for error type checking
        from unicon.core.errors import (
            StateMachineError,
        )
        from unicon.core.errors import (
            TimeoutError as UniconTimeoutError,
        )

        host = device_info.get("host", "unknown")
        platform = device_info.get("platform", "unknown")
        error_type = type(error).__name__

        if isinstance(error, UniconTimeoutError):
            category = "Connection timeout"
            hints = [
                f"Device at {host} is not responding within the timeout period",
                "Check if the device is powered on and accessible",
                "Verify network connectivity to the device",
                "Consider increasing the timeout value if the device is slow to respond",
            ]
        elif isinstance(error, StateMachineError):
            category = "Device state machine error"
            hints = [
                f"Failed to navigate device prompts/states on {host}",
                f"Verify the platform type '{platform}' is correct for this device",
                "Check if the device CLI behavior matches expected patterns",
                "Device may be in an unexpected state or mode",
            ]
        else:  # ConnectionError or other connection errors
            category = "Connection failure"
            hints = [
                f"Failed to establish SSH connection to {host}",
                "Verify the device is reachable (ping/traceroute)",
                "Check if SSH service is enabled and running on the device",
                "Verify firewall rules allow SSH connections",
                "Check if the SSH port (usually 22) is correct",
            ]

        return (
            f"{category} for device '{hostname}'\n"
            f"  Host: {host}\n"
            f"  Platform: {platform}\n"
            f"  Error: {error_type}: {error}\n"
            f"  Troubleshooting:\n" + "\n".join(f"    - {hint}" for hint in hints)
        )

    def _format_auth_error(
        self,
        hostname: str,
        device_info: Dict[str, Any],
        error: Exception,  # Changed from CredentialsExhaustedError to avoid import
    ) -> str:
        """Format authentication error with detailed information.

        Args:
            hostname: Device identifier
            device_info: Device connection information
            error: The authentication exception

        Returns:
            Formatted error message with troubleshooting hints
        """
        host = device_info.get("host", "unknown")
        username = device_info.get("username", "unknown")

        return (
            f"Authentication failure for device '{hostname}'\n"
            f"  Host: {host}\n"
            f"  Username: {username}\n"
            f"  Error: {type(error).__name__}: {error}\n"
            f"  Troubleshooting:\n"
            f"    - Verify the username and password are correct\n"
            f"    - Check if the user account is locked or disabled\n"
            f"    - Ensure the user has SSH access permissions on the device\n"
            f"    - Verify any two-factor authentication requirements"
        )

    def _format_unexpected_error(
        self, hostname: str, device_info: Dict[str, Any], error: Exception
    ) -> str:
        """Format unexpected error with detailed information.

        Args:
            hostname: Device identifier
            device_info: Device connection information
            error: The unexpected exception

        Returns:
            Formatted error message
        """
        host = device_info.get("host", "unknown")
        platform = device_info.get("platform", "Not Defined")

        return (
            f"Unexpected error connecting to device '{hostname}'\n"
            f"  Host: {host}\n"
            f"  Platform: {platform}\n"
            f"  Error: {type(error).__name__}: {error}\n"
            f"  This may indicate:\n"
            f"    - An issue with the device configuration\n"
            f"    - A bug in the connection handling\n"
            f"    - An unsupported device type or firmware version"
        )

    async def close_connection(self, hostname: str) -> None:
        """Close and cleanup connection for a device.

        Args:
            hostname: Unique device identifier
        """
        if hostname in self.device_locks:
            async with self.device_locks[hostname]:
                await self._close_connection_internal(hostname)

    async def _close_connection_internal(self, hostname: str) -> None:
        """Internal method to close connection without locking.

        Args:
            hostname: Unique device identifier
        """
        if hostname in self.connections:
            try:
                conn = self.connections[hostname]
                # Run disconnect in thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._disconnect_unicon, conn)
                logger.info(f"Closed connection to {hostname}")
            except Exception as e:
                logger.error(f"Error closing connection to {hostname}: {e}", exc_info=True)
            finally:
                # Always remove from connections dict
                del self.connections[hostname]

    def _disconnect_unicon(self, conn: "Connection") -> None:
        """Disconnect Unicon connection (runs in thread pool).

        Args:
            conn: Unicon Connection object to disconnect
        """
        try:
            if conn.connected:
                conn.disconnect()
        except Exception as e:
            logger.warning(f"Error during Unicon disconnect: {e}")

    async def close_all_connections(self) -> None:
        """Close all active connections."""
        hostnames = list(self.connections.keys())

        logger.info(f"Closing {len(hostnames)} active connections")

        for hostname in hostnames:
            await self.close_connection(hostname)

    @asynccontextmanager
    async def device_connection(
        self, hostname: str, device_info: Dict[str, Any]
    ) -> AsyncIterator["Connection"]:
        """Context manager for device connections with automatic cleanup.

        Args:
            hostname: Unique device identifier
            device_info: Device connection information

        Yields:
            Unicon Connection object
        """
        conn = None
        try:
            conn = await self.get_connection(hostname, device_info)
            yield conn
        finally:
            if conn:
                await self.close_connection(hostname)

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection manager statistics.

        Returns:
            Dictionary containing connection statistics
        """
        active_connections = len(self.connections)
        healthy_connections = sum(
            1 for conn in self.connections.values() if self._is_connection_healthy(conn)
        )

        return {
            "max_concurrent": self.max_concurrent,
            "active_connections": active_connections,
            "healthy_connections": healthy_connections,
            "available_slots": self.max_concurrent - active_connections,
            "device_locks": len(self.device_locks),
        }
