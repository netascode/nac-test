# -*- coding: utf-8 -*-

"""Connection broker service for managing persistent device connections.

This service runs as a long-lived daemon process that:
1. Loads a consolidated testbed with all devices
2. Manages persistent pyATS testbed connections
3. Provides command execution API via Unix socket
4. Handles connection pooling and resource limits
"""

import asyncio
import json
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, Optional, Set

from ..ssh.command_cache import CommandCache

if TYPE_CHECKING:
    from pyats.topology import Testbed

logger = logging.getLogger(__name__)


class ConnectionBroker:
    """Broker service that manages persistent device connections."""

    def __init__(
        self,
        testbed_path: Optional[Path] = None,
        socket_path: Optional[Path] = None,
        max_connections: int = 50,
        output_dir: Optional[Path] = None,
    ):
        """Initialize the connection broker.

        Args:
            testbed_path: Path to consolidated testbed YAML file
            socket_path: Path for Unix domain socket (auto-generated if None)
            max_connections: Maximum concurrent connections to maintain
            output_dir: Directory for Unicon CLI logs (defaults to /tmp if None)
        """
        self.testbed_path = testbed_path
        self.socket_path = socket_path or self._generate_socket_path()
        self.max_connections = max_connections
        self.output_dir = Path(output_dir) if output_dir else Path("/tmp")

        # Connection management
        self.testbed: Optional[Testbed] = None
        self.connected_devices: Dict[str, Any] = {}  # hostname -> device connection
        self.connection_locks: Dict[str, asyncio.Lock] = {}
        self.connection_semaphore = asyncio.Semaphore(max_connections)

        # Command caching - shared across all clients
        self.command_cache: Dict[str, CommandCache] = {}  # hostname -> CommandCache

        # Socket server
        self.server: Optional[asyncio.Server] = None
        self.active_clients: Set[asyncio.StreamWriter] = set()

        # Shutdown flag
        self._shutdown_event = asyncio.Event()

    def _generate_socket_path(self) -> Path:
        """Generate a unique socket path in temp directory."""
        temp_dir = Path(tempfile.gettempdir())
        return temp_dir / f"nac_test_broker_{os.getpid()}.sock"

    async def start(self) -> None:
        """Start the broker service."""
        logger.info(f"Starting connection broker with socket: {self.socket_path}")

        # Load testbed if provided
        if self.testbed_path:
            await self._load_testbed()

        # Start Unix socket server
        await self._start_socket_server()

        logger.info("Connection broker started successfully")

    async def _load_testbed(self) -> None:
        """Load pyATS testbed from YAML file."""
        try:
            # Import pyATS components here to delay initialization
            from pyats.topology import loader

            logger.info(f"Loading testbed from: {self.testbed_path}")

            # Load testbed using pyATS loader
            self.testbed = loader.load(str(self.testbed_path))

            if self.testbed is None:
                raise RuntimeError("Failed to load testbed - loader returned None")

            logger.info(f"Loaded testbed with {len(self.testbed.devices)} devices")

            # Initialize connection locks for all devices
            for hostname in self.testbed.devices:
                self.connection_locks[hostname] = asyncio.Lock()

        except Exception as e:
            logger.error(f"Failed to load testbed: {e}", exc_info=True)
            raise

    async def _start_socket_server(self) -> None:
        """Start Unix domain socket server for client communication."""
        # Remove existing socket file if it exists
        if self.socket_path.exists():
            self.socket_path.unlink()

        # Create socket server
        self.server = await asyncio.start_unix_server(
            self._handle_client, path=str(self.socket_path)
        )

        # Set socket permissions (readable/writable by owner only)
        os.chmod(self.socket_path, 0o600)

        logger.info(f"Socket server listening on: {self.socket_path}")

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle incoming client connections."""
        client_addr = writer.get_extra_info("peername", "unknown")
        logger.debug(f"Client connected: {client_addr}")

        self.active_clients.add(writer)

        try:
            while not self._shutdown_event.is_set():
                # Read message length (4 bytes, big-endian)
                length_data = await reader.readexactly(4)
                message_length = int.from_bytes(length_data, byteorder="big")

                if message_length == 0:
                    break

                # Read message data
                message_data = await reader.readexactly(message_length)
                message = json.loads(message_data.decode("utf-8"))

                # Process request
                response = await self._process_request(message)

                # Send response
                response_data = json.dumps(response).encode("utf-8")
                response_length = len(response_data).to_bytes(4, byteorder="big")

                writer.write(response_length + response_data)
                await writer.drain()

        except asyncio.IncompleteReadError:
            # Client disconnected normally
            logger.debug(f"Client disconnected: {client_addr}")
        except Exception as e:
            logger.error(f"Error handling client {client_addr}: {e}", exc_info=True)
        finally:
            self.active_clients.discard(writer)
            writer.close()
            await writer.wait_closed()

    async def _process_request(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process a client request and return response."""
        try:
            command = message.get("command")

            if command == "ping":
                return {"status": "success", "result": "pong"}

            elif command == "execute":
                hostname = message.get("hostname")
                cmd_string = message.get("cmd")

                if not hostname or not cmd_string:
                    return {
                        "status": "error",
                        "error": "Missing hostname or cmd parameter",
                    }

                result = await self._execute_command(hostname, cmd_string)
                return {"status": "success", "result": result}

            elif command == "connect":
                hostname = message.get("hostname")

                if not hostname:
                    return {"status": "error", "error": "Missing hostname parameter"}

                success = await self._ensure_connection(hostname)
                return {"status": "success" if success else "error", "result": success}

            elif command == "disconnect":
                hostname = message.get("hostname")

                if not hostname:
                    return {"status": "error", "error": "Missing hostname parameter"}

                await self._disconnect_device(hostname)
                return {"status": "success", "result": True}

            elif command == "status":
                status = await self._get_broker_status()
                return {"status": "success", "result": status}

            else:
                return {"status": "error", "error": f"Unknown command: {command}"}

        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    async def _execute_command(self, hostname: str, cmd: str) -> str:
        """Execute command on device via established connection with caching.

        This method implements command caching at the broker level, ensuring
        that identical commands are only executed once across all test subprocesses.
        """
        # Get or create cache for this device
        if hostname not in self.command_cache:
            self.command_cache[hostname] = CommandCache(
                hostname, ttl=3600
            )  # 1 hour TTL
            logger.info(f"Created command cache for device: {hostname}")

        cache = self.command_cache[hostname]

        # Check cache first
        cached_output = cache.get(cmd)
        if cached_output is not None:
            logger.debug(f"Broker cache hit for '{cmd}' on {hostname}")
            return cached_output

        # Command not in cache, need to execute
        logger.debug(f"Broker cache miss for '{cmd}' on {hostname}, executing...")

        # Ensure device is connected
        connection = await self._get_connection(hostname)
        if not connection:
            raise ConnectionError(f"Failed to connect to device: {hostname}")

        # Execute command in thread pool (since Unicon is synchronous)
        loop = asyncio.get_event_loop()
        try:
            output = await loop.run_in_executor(None, connection.execute, cmd)
            output_str = str(output)

            # Cache the output for future requests
            cache.set(cmd, output_str)
            logger.info(
                f"Cached command output for '{cmd}' on {hostname} ({len(output_str)} chars)"
            )

            return output_str
        except Exception as e:
            logger.error(f"Command execution failed on {hostname}: {e}")
            # Try to reconnect on failure
            await self._disconnect_device(hostname)
            raise

    async def _get_connection(self, hostname: str) -> Optional[Any]:
        """Get or create connection to device."""
        if hostname not in self.connection_locks:
            self.connection_locks[hostname] = asyncio.Lock()

        async with self.connection_locks[hostname]:
            # Return existing connection if healthy
            if hostname in self.connected_devices:
                connection = self.connected_devices[hostname]
                if self._is_connection_healthy(connection):
                    return connection
                else:
                    # Remove unhealthy connection
                    await self._disconnect_device_internal(hostname)

            # Create new connection
            return await self._create_connection(hostname)

    async def _create_connection(self, hostname: str) -> Optional[Any]:
        """Create new connection to device using testbed."""
        if not self.testbed:
            logger.error("No testbed loaded")
            return None

        if hostname not in self.testbed.devices:
            logger.error(f"Device {hostname} not found in testbed")
            return None

        async with self.connection_semaphore:
            try:
                device = self.testbed.devices[hostname]
                logger.info(f"Connecting to device: {hostname}")

                # Create unique log file path in output directory
                import time

                timestamp = (
                    int(time.time() * 1000000) % 10000000000
                )  # Last 10 digits of microsecond timestamp
                logfile_path = self.output_dir / f"{hostname}-cli-{timestamp}.log"

                logger.info(f"Unicon CLI log will be written to: {logfile_path}")

                # Connect using pyATS testbed with custom logfile location
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, lambda: device.connect(logfile=str(logfile_path))
                )

                # Store connection
                self.connected_devices[hostname] = device
                logger.info(f"Successfully connected to device: {hostname}")

                return device

            except Exception as e:
                logger.error(f"Failed to connect to {hostname}: {e}", exc_info=True)
                return None

    async def _ensure_connection(self, hostname: str) -> bool:
        """Ensure device is connected, return success status."""
        connection = await self._get_connection(hostname)
        return connection is not None

    async def _disconnect_device(self, hostname: str) -> None:
        """Disconnect from device and clean up."""
        if hostname in self.connection_locks:
            async with self.connection_locks[hostname]:
                await self._disconnect_device_internal(hostname)

    async def _disconnect_device_internal(self, hostname: str) -> None:
        """Internal disconnect without locking."""
        if hostname in self.connected_devices:
            try:
                connection = self.connected_devices[hostname]
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, connection.disconnect)
                logger.info(f"Disconnected from device: {hostname}")
            except Exception as e:
                logger.warning(f"Error disconnecting from {hostname}: {e}")
            finally:
                del self.connected_devices[hostname]

        # Clear command cache for this device when disconnecting
        if hostname in self.command_cache:
            cache_stats = self.command_cache[hostname].get_cache_stats()
            logger.info(f"Clearing command cache for {hostname}: {cache_stats}")
            del self.command_cache[hostname]

    def _is_connection_healthy(self, connection: Any) -> bool:
        """Check if connection is healthy."""
        try:
            return (
                hasattr(connection, "connected")
                and connection.connected
                and hasattr(connection, "spawn")
                and connection.spawn
            )
        except Exception:
            return False

    async def _get_broker_status(self) -> Dict[str, Any]:
        """Get broker status information."""
        # Collect cache statistics for all devices
        cache_stats = {}
        total_cached_commands = 0

        for hostname, cache in self.command_cache.items():
            stats = cache.get_cache_stats()
            cache_stats[hostname] = stats
            total_cached_commands += stats["valid_entries"]

        return {
            "socket_path": str(self.socket_path),
            "max_connections": self.max_connections,
            "connected_devices": list(self.connected_devices.keys()),
            "active_clients": len(self.active_clients),
            "testbed_loaded": self.testbed is not None,
            "testbed_devices": list(self.testbed.devices.keys())
            if self.testbed
            else [],
            "command_cache_stats": {
                "devices_with_cache": list(self.command_cache.keys()),
                "total_cached_commands": total_cached_commands,
                "per_device_stats": cache_stats,
            },
        }

    async def shutdown(self) -> None:
        """Shutdown the broker service."""
        logger.info("Shutting down connection broker...")

        # Signal shutdown
        self._shutdown_event.set()

        # Close all client connections
        for writer in list(self.active_clients):
            writer.close()
            await writer.wait_closed()

        # Disconnect all devices
        for hostname in list(self.connected_devices.keys()):
            await self._disconnect_device(hostname)

        # Stop socket server
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # Remove socket file
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove socket file: {e}")

        logger.info("Connection broker shutdown complete")

    @asynccontextmanager
    async def run_context(self) -> AsyncGenerator[Any, None]:
        """Context manager for running the broker."""
        try:
            await self.start()
            yield self
        finally:
            await self.shutdown()
