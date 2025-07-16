# -*- coding: utf-8 -*-

"""Device connection manager for SSH testing.

This module provides connection management for SSH-based device testing,
including connection pooling, resource limits, and per-device locking.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from unicon import Connection
from unicon.core.errors import (
    UniconConnectionError,
    CredentialsExhaustedError,
    StateMachineError,
    TimeoutError as UniconTimeoutError,
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
        self.connections: Dict[str, Connection] = {}
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
        self, device_id: str, device_info: Dict[str, Any]
    ) -> Connection:
        """Get or create SSH connection for a device.

        This method ensures that only one connection exists per device at a time
        and respects the global connection limit.

        Args:
            device_id: Unique device identifier
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
        if device_id not in self.device_locks:
            self.device_locks[device_id] = asyncio.Lock()

        async with self.device_locks[device_id]:
            # Return existing connection if available
            if device_id in self.connections:
                conn = self.connections[device_id]
                if self._is_connection_healthy(conn):
                    logger.debug(f"Reusing existing connection for {device_id}")
                    return conn
                else:
                    # Connection is unhealthy, remove it
                    logger.warning(f"Removing unhealthy connection for {device_id}")
                    await self._close_connection_internal(device_id)

            # Create new connection
            return await self._create_connection(device_id, device_info)

    async def _create_connection(
        self, device_id: str, device_info: Dict[str, Any]
    ) -> Connection:
        """Create new SSH connection for a device.

        Args:
            device_id: Unique device identifier
            device_info: Device connection information

        Returns:
            New Unicon Connection object

        Raises:
            ConnectionError: With detailed error information about the failure type
        """
        # Respect global connection limit
        async with self.semaphore:
            host = device_info.get("host", "unknown")
            logger.info(f"Creating SSH connection to {device_id} at {host}")

            try:
                # Run Unicon connection in thread pool (since it's synchronous)
                loop = asyncio.get_event_loop()
                conn = await loop.run_in_executor(
                    None, self._unicon_connect, device_info
                )

                # Store connection
                self.connections[device_id] = conn
                logger.info(f"Successfully connected to {device_id}")

                return conn

            except CredentialsExhaustedError as e:
                # Authentication failure - no point retrying
                error_msg = self._format_auth_error(device_id, device_info, e)
                logger.error(error_msg)
                raise ConnectionError(error_msg) from e

            except (UniconConnectionError, StateMachineError, UniconTimeoutError) as e:
                # Connection-related errors
                error_msg = self._format_connection_error(device_id, device_info, e)
                logger.error(error_msg)
                raise ConnectionError(error_msg) from e

            except Exception as e:
                # Unexpected errors
                error_msg = self._format_unexpected_error(device_id, device_info, e)
                logger.error(error_msg)
                raise ConnectionError(error_msg) from e

    def _unicon_connect(self, device_info: Dict[str, Any]) -> Connection:
        """Create Unicon connection (runs in thread pool).

        Args:
            device_info: Device connection information

        Returns:
            Connected Unicon Connection object

        Raises:
            Exception: Any exception from Unicon connection attempt
        """
        # Extract connection parameters
        connection_params = {
            "hostname": device_info["host"],
            "username": device_info["username"],
            "password": device_info["password"],
            "platform": device_info.get("platform", "ios"),
            "timeout": device_info.get("timeout", 120),
            "init_exec_commands": [],
            "init_config_commands": [],
        }

        # Create and connect - let exceptions bubble up
        conn = Connection(**connection_params)
        conn.connect()

        return conn

    def _is_connection_healthy(self, conn: Connection) -> bool:
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
        self, device_id: str, device_info: Dict[str, Any], error: Exception
    ) -> str:
        """Format connection error with detailed information.

        Args:
            device_id: Device identifier
            device_info: Device connection information
            error: The connection exception that occurred

        Returns:
            Formatted error message with troubleshooting hints
        """
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
        else:  # UniconConnectionError or other connection errors
            category = "Connection failure"
            hints = [
                f"Failed to establish SSH connection to {host}",
                "Verify the device is reachable (ping/traceroute)",
                "Check if SSH service is enabled and running on the device",
                "Verify firewall rules allow SSH connections",
                "Check if the SSH port (usually 22) is correct",
            ]

        return (
            f"{category} for device '{device_id}'\n"
            f"  Host: {host}\n"
            f"  Platform: {platform}\n"
            f"  Error: {error_type}: {error}\n"
            f"  Troubleshooting:\n" + "\n".join(f"    - {hint}" for hint in hints)
        )

    def _format_auth_error(
        self,
        device_id: str,
        device_info: Dict[str, Any],
        error: CredentialsExhaustedError,
    ) -> str:
        """Format authentication error with detailed information.

        Args:
            device_id: Device identifier
            device_info: Device connection information
            error: The authentication exception

        Returns:
            Formatted error message with troubleshooting hints
        """
        host = device_info.get("host", "unknown")
        username = device_info.get("username", "unknown")

        return (
            f"Authentication failure for device '{device_id}'\n"
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
        self, device_id: str, device_info: Dict[str, Any], error: Exception
    ) -> str:
        """Format unexpected error with detailed information.

        Args:
            device_id: Device identifier
            device_info: Device connection information
            error: The unexpected exception

        Returns:
            Formatted error message
        """
        host = device_info.get("host", "unknown")
        platform = device_info.get("platform", "unknown")

        return (
            f"Unexpected error connecting to device '{device_id}'\n"
            f"  Host: {host}\n"
            f"  Platform: {platform}\n"
            f"  Error: {type(error).__name__}: {error}\n"
            f"  This may indicate:\n"
            f"    - An issue with the device configuration\n"
            f"    - A bug in the connection handling\n"
            f"    - An unsupported device type or firmware version"
        )

    async def close_connection(self, device_id: str) -> None:
        """Close and cleanup connection for a device.

        Args:
            device_id: Unique device identifier
        """
        if device_id in self.device_locks:
            async with self.device_locks[device_id]:
                await self._close_connection_internal(device_id)

    async def _close_connection_internal(self, device_id: str) -> None:
        """Internal method to close connection without locking.

        Args:
            device_id: Unique device identifier
        """
        if device_id in self.connections:
            try:
                conn = self.connections[device_id]
                # Run disconnect in thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._disconnect_unicon, conn)
                logger.info(f"Closed connection to {device_id}")
            except Exception as e:
                logger.error(f"Error closing connection to {device_id}: {e}")
            finally:
                # Always remove from connections dict
                del self.connections[device_id]

    def _disconnect_unicon(self, conn: Connection) -> None:
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
        device_ids = list(self.connections.keys())

        logger.info(f"Closing {len(device_ids)} active connections")

        for device_id in device_ids:
            await self.close_connection(device_id)

    @asynccontextmanager
    async def device_connection(self, device_id: str, device_info: Dict[str, Any]):
        """Context manager for device connections with automatic cleanup.

        Args:
            device_id: Unique device identifier
            device_info: Device connection information

        Yields:
            Unicon Connection object
        """
        conn = None
        try:
            conn = await self.get_connection(device_id, device_info)
            yield conn
        finally:
            if conn:
                await self.close_connection(device_id)

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
