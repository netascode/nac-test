from nac_test.pyats.common.base_test import NACTestBase
from nac_test.pyats.ssh.command_cache import CommandCache
from nac_test.pyats.ssh.connection_manager import DeviceConnectionManager
import asyncio
from pyats import aetest
import logging
import os
import json
from typing import Any


class SSHTestBase(NACTestBase):
    """Base class for all SSH-based device tests.

    This class provides the core framework for SSH test execution, including
    automatic context setup and command execution capabilities.
    """

    @aetest.setup
    def setup_ssh_context(self) -> None:
        """
        Automatically sets up the SSH context before the test runs.

        This lifecycle hook is called by PyATS automatically. It reads the
        device info and the main data model from environment variables set by
        the orchestrator. It then establishes a connection and injects the
        necessary tools (like self.execute_command) into the test instance.
        """
        # These environment variables are not set by the user, but are passed
        # by the nac-test orchestrator to provide context to this isolated
        # PyATS job process.
        device_info_json = os.environ.get("DEVICE_INFO")
        data_file_path = os.environ.get("DATA_FILE")

        if not device_info_json or not data_file_path:
            self.failed(
                "Framework Error: DEVICE_INFO and DATA_FILE env vars must be set by the orchestrator."
            )
            return

        try:
            self.device_info = json.loads(device_info_json)
            with open(data_file_path, "r") as f:
                self.data_model = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            self.failed(
                f"Framework Error: Could not load test context from environment: {e}"
            )
            return

        # The ConnectionManager is instantiated within the job's process space
        # We'll attach it to the runtime object for the test's duration
        if not hasattr(self.parent, "connection_manager"):
            self.parent.connection_manager = DeviceConnectionManager()
        self.connection_manager = self.parent.connection_manager

        device_id = self.device_info.get("device_id") or self.device_info.get("host")
        if not device_id:
            self.failed(
                "Framework Error: device_info from resolver must contain a 'device_id'."
            )
            return

        # The rest of the setup is async, we'll run it in the event loop
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self._async_setup(device_id))
        except ConnectionError as e:
            # Connection failed - fail the test with clear message
            self.failed(str(e))

    async def _async_setup(self, device_id: str) -> None:
        """Helper for async setup operations with connection error handling."""
        try:
            # 1. Establish the connection using the manager
            self.connection = await self.connection_manager.get_connection(
                device_id, self.device_info
            )
        except Exception as e:
            # Connection failed - raise exception to be caught in setup_ssh_context
            error_msg = f"Failed to connect to device {device_id}: {str(e)}"
            self.logger.error(error_msg)

            # Raise with a clear message that will be caught by the calling method
            raise ConnectionError(
                f"Device connection failed: {device_id}\nError: {str(e)}"
            )

        # 2. Create and attach the command cache
        self.command_cache = CommandCache(device_id)

        # 3. Create and attach the execute_command helper method
        self.execute_command = self._create_execute_command_method(
            self.connection, self.command_cache
        )

        # 4. Attach device_data for easy access in the test
        self.device_data = self.device_info
        self.device_id = device_id

    def _create_execute_command_method(
        self, connection: Any, command_cache: CommandCache
    ):
        """Create an async command execution method for the test.

        Args:
            connection: SSH connection to the device.
            command_cache: Command cache for the device.

        Returns:
            Async method for command execution with caching.
        """
        # Capture self reference for use in the closure
        test_instance = self

        async def execute_command(command: str) -> str:
            """Execute command with caching and tracking.

            Args:
                command: Command to execute.

            Returns:
                Command output.
            """
            # Check cache first
            cached_output = command_cache.get(command)
            if cached_output is not None:
                logging.debug(f"Using cached output for command: {command}")
                # Track cached command execution for reporting
                test_instance._track_ssh_command(command, cached_output)
                return cached_output

            # Execute command via Unicon in thread pool
            logging.debug(f"Executing command: {command}")
            loop = asyncio.get_event_loop()
            output = await loop.run_in_executor(None, connection.execute, command)

            # Convert output to string to ensure consistent type
            output_str = str(output)

            # Cache the output
            command_cache.set(command, output_str)

            # Track the command execution for reporting
            test_instance._track_ssh_command(command, output_str)

            return output_str

        return execute_command

    def _track_ssh_command(self, command: str, output: str) -> None:
        """Track SSH command execution for HTML reporting.

        This method integrates with the base class's result collector to track
        SSH commands for the HTML report generation.

        Args:
            command: The command that was executed
            output: The command output
        """
        if not hasattr(self, "result_collector"):
            # Safety check - collector might not be initialized in some edge cases
            return

        try:
            # Get device name from device info
            device_name = self.device_info.get(
                "hostname", self.device_info.get("host", "Unknown Device")
            )

            # Get current test context if available (set by base class methods)
            test_context = getattr(self, "_current_test_context", None)

            # Track the command execution using the base class's result collector
            self.result_collector.add_command_api_execution(
                device_name=device_name,
                command=command,
                output=output[:50000],  # Pre-truncate to 50KB to prevent memory issues
                data=None,  # SSH commands don't have structured data like APIs
                test_context=test_context,
            )

            # Log at debug level
            self.logger.debug(f"Tracked SSH command: {command} on {device_name}")

        except Exception as e:
            # Don't let tracking errors break the test
            self.logger.warning(f"Failed to track SSH command: {e}")
