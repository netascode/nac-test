from nac_test.pyats_core.common.base_test import NACTestBase
from nac_test.pyats_core.ssh.command_cache import CommandCache
from nac_test.pyats_core.ssh.connection_manager import DeviceConnectionManager
import asyncio
from pyats import aetest
import logging
import os
import json
from typing import Any, Optional, Callable, Coroutine


class SSHTestBase(NACTestBase):
    """Base class for all SSH-based device tests.

    This class provides the core framework for SSH test execution, including
    automatic context setup and command execution capabilities.

    The class also provides access to the PyATS testbed object when available,
    enabling the use of Genie parsers and other PyATS/Genie features.
    #TODO: Move this to its own thing to better adhere for SRP. Hustling the MVP.
    """

    @property
    def testbed(self) -> Optional[Any]:
        """Access the PyATS testbed object if available.

        When tests are run via PyATS with --testbed-file, the testbed is loaded
        and made available through the runtime. This property provides convenient
        access to it.

        Returns:
            The PyATS testbed object if available, None otherwise.
        """
        # In PyATS aetest, the testbed is available via self.parent (runtime)
        if hasattr(self.parent, "testbed"):
            return self.parent.testbed
        return None

    @property
    def testbed_device(self) -> Optional[Any]:
        """Access the current device from the PyATS testbed.

        This provides a convenient way to access the current device's testbed
        object, which includes Genie parsing capabilities.

        Returns:
            The device object from the testbed if available, None otherwise.
        """
        if self.testbed and hasattr(self, "hostname"):
            # Look up device by hostname in the testbed
            if self.hostname in self.testbed.devices:
                return self.testbed.devices[self.hostname]
        return None

    @aetest.setup
    def setup(self) -> None:
        """
        Combined setup that calls parent setup then sets up SSH context.

        This lifecycle hook is called by PyATS automatically. It first calls
        the parent NACTestBase setup, then reads device info and establishes
        SSH connections with necessary tools (like self.execute_command).

        If a PyATS testbed is available, it also ensures the device connection
        is established through the testbed for Genie parser access.
        """
        # Call parent setup first
        super().setup()

        # Then do SSH-specific setup
        # These environment variables are not set by the user, but are passed
        # by the nac-test orchestrator to provide context to this isolated
        # PyATS job process.
        device_info_json = os.environ.get("DEVICE_INFO")
        data_file_path = os.environ.get("MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH")

        if not device_info_json or not data_file_path:
            self.failed(
                "Framework Error: DEVICE_INFO and MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH env vars must be set by the orchestrator."
            )
            return

        try:
            self.device_info = json.loads(device_info_json)
        except json.JSONDecodeError as e:
            self.failed(
                f"Framework Error: Could not parse device info JSON from environment variable DEVICE_INFO: {e}\n"
                f"Raw content: {device_info_json}"
            )
            return

        # The ConnectionManager is instantiated within the job's process space
        # We'll attach it to the runtime object for the test's duration
        if not hasattr(self.parent, "connection_manager"):
            self.parent.connection_manager = DeviceConnectionManager()
        self.connection_manager = self.parent.connection_manager

        try:
            hostname = self.device_info["hostname"]
        except KeyError:
            self.failed(
                "Framework Error: device_info from resolver MUST contain a 'hostname' field. "
                "This is a required field per the nac-test contract."
            )
            return

        # Store hostname early so testbed_device property can use it
        self.hostname = hostname

        # The rest of the setup is async, we'll run it in the event loop
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self._async_setup(hostname))
        except ConnectionError as e:
            # Connection failed - fail the test with clear message
            self.failed(str(e))

    async def _async_setup(self, hostname: str) -> None:
        """Helper for async setup operations with connection error handling."""
        try:
            # Check if we have a testbed device available
            if self.testbed_device:
                # Connect via testbed to enable Genie features
                self.logger.info(f"Connecting to device {hostname} via PyATS testbed")
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.testbed_device.connect)
                # Store the testbed device connection for command execution
                self.connection = self.testbed_device
            else:
                # Fall back to standard nac-test connection
                self.logger.info(
                    f"Connecting to device {hostname} via nac-test connection manager"
                )
                self.connection = await self.connection_manager.get_connection(
                    hostname, self.device_info
                )
        except Exception as e:
            # Connection failed - raise exception to be caught in setup_ssh_context
            error_msg = f"Failed to connect to device {hostname}: {str(e)}"
            self.logger.error(error_msg)

            # Raise with a clear message that will be caught by the calling method
            raise ConnectionError(
                f"Device connection failed: {hostname}\nError: {str(e)}"
            )

        # 2. Create and attach the command cache
        self.command_cache = CommandCache(hostname)

        # 3. Create and attach the execute_command helper method
        self.execute_command = self._create_execute_command_method(
            self.connection, self.command_cache
        )

        # 4. Attach device_data for easy access in the test
        self.device_data = self.device_info
        # hostname already set in setup_ssh_context

    def parse_output(
        self, command: str, output: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """Parse command output using Genie parser if available.

        This method attempts to use Genie parsers when a PyATS testbed is available.
        If no testbed is available or parsing fails, it returns None.

        Args:
            command: The command whose output should be parsed
            output: Optional pre-fetched command output. If not provided,
                   the command will be executed.

        Returns:
            Parsed output dictionary if successful, None otherwise.
        """
        # If we have a testbed device, use its parse method
        if self.testbed_device:
            try:
                if output is not None:
                    # Parse provided output
                    result = self.testbed_device.parse(command, output=output)
                    return dict(result) if result is not None else None
                else:
                    # Execute and parse in one step
                    result = self.testbed_device.parse(command)
                    return dict(result) if result is not None else None
            except Exception as e:
                self.logger.warning(f"Genie parser failed for '{command}': {e}")
                return None
        else:
            self.logger.debug("No testbed device available for Genie parsing")
            return None

    def _create_execute_command_method(
        self, connection: Any, command_cache: CommandCache
    ) -> Callable[[str], Coroutine[Any, Any, str]]:
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
