from nac_test.pyats_core.common.base_test import NACTestBase
from nac_test.pyats_core.ssh.command_cache import CommandCache
from nac_test.pyats_core.broker.broker_client import BrokerClient, BrokerCommandExecutor
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
        # In PyATS aetest, testbed is passed as an internal parameter
        if hasattr(self, "parameters"):
            # Check internal parameters (where PyATS stores testbed)
            if (
                hasattr(self.parameters, "internal")
                and "testbed" in self.parameters.internal
            ):
                return self.parameters.internal["testbed"]
            # Fallback to regular parameters
            if "testbed" in self.parameters:
                return self.parameters["testbed"]
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

        # try:
        #     with open(data_file_path, "r") as f:
        #         self.data_model = json.load(f)
        # except FileNotFoundError:
        #     self.failed(
        #         f"Framework Error: Could not find data model file at path: {data_file_path}"
        #     )
        #     return
        # except json.JSONDecodeError as e:
        #     try:
        #         with open(data_file_path, "r") as f:
        #             file_content = f.read()
        #     except Exception:
        #         file_content = "[Could not read file content]"

        #     self.failed(
        #         f"Framework Error: Could not parse JSON from data model file '{data_file_path}': {e}\n"
        #         f"File content: {file_content}"
        #     )
        #     return

        # The BrokerClient communicates with the centralized connection broker
        # We'll attach it to the runtime object for the test's duration
        if not hasattr(self.parent, "broker_client"):
            self.parent.broker_client = BrokerClient()
        self.broker_client = self.parent.broker_client

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
                # Use broker client for connection management
                self.logger.info(
                    f"Connecting to device {hostname} via connection broker"
                )
                # Connect to broker service
                await self.broker_client.connect()

                # Create broker command executor for this device
                self.connection = BrokerCommandExecutor(hostname, self.broker_client)

                # Ensure device connection through broker
                await self.connection.connect()

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

            # Execute command via connection (broker or testbed device)
            logging.debug(f"Executing command: {command}")

            if hasattr(connection, "execute") and asyncio.iscoroutinefunction(
                connection.execute
            ):
                # Broker command executor - already async
                output = await connection.execute(command)
            else:
                # Testbed device or legacy connection - run in thread pool
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

    def run_async_verification_test(self, steps) -> None:
        """Run async verification test using existing event loop.

        This method orchestrates the async verification process for SSH-based tests:
        1. Uses the existing event loop (created in SSHTestBase.setup)
        2. Calls NACTestBase.run_verification_async() to execute verifications
        3. Calls NACTestBase.process_results_smart() to process results
        4. Handles SSH-specific cleanup (broker client and connections)

        The actual verification logic is handled by:
        - get_items_to_verify() - implemented by the test class
        - verify_item() - implemented by the test class

        Args:
            steps: PyATS steps object for test reporting

        Note:
            This method does NOT close the event loop as it's managed by the
            PyATS framework. The loop was created in setup() and will be
            properly cleaned up by the framework.
        """
        # Get the existing event loop that was created in setup
        loop = asyncio.get_event_loop()

        try:
            # Call the base class generic orchestration
            results = loop.run_until_complete(self.run_verification_async())

            # Process results using smart configuration-driven processing
            self.process_results_smart(results, steps)

        finally:
            # SSH-specific cleanup
            try:
                # Disconnect broker client if it exists
                if hasattr(self, "broker_client") and self.broker_client:
                    self.logger.debug("Disconnecting broker client")
                    loop.run_until_complete(self.broker_client.disconnect())

                # Disconnect the connection if using broker executor
                if hasattr(self, "connection") and isinstance(
                    self.connection, BrokerCommandExecutor
                ):
                    self.logger.debug("Disconnecting broker command executor")
                    loop.run_until_complete(self.connection.disconnect())

            except Exception as e:
                # Log cleanup errors but don't fail the test
                self.logger.warning(f"Error during SSH cleanup: {e}")

            # Note: We do NOT close the event loop here as it's managed by PyATS
