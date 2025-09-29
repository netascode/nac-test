# -*- coding: utf-8 -*-

"""Generic base test class for all architectures."""

from pyats import aetest
import os
import sys
import yaml
import logging
import json
import time
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    TypeVar,
    Callable,
    Awaitable,
    Optional,
    Iterator,
    Union,
)
from functools import lru_cache
from datetime import datetime
from contextlib import contextmanager

from nac_test.pyats_core.common.connection_pool import ConnectionPool
from nac_test.pyats_core.common.retry_strategy import SmartRetry
from nac_test.pyats_core.common.types import (
    VerificationResult,
    BaseVerificationResultOptional,
    ApiDetails,
)
from nac_test.pyats_core.reporting.collector import TestResultCollector
from nac_test.pyats_core.reporting.batching_reporter import BatchingReporter
from nac_test.pyats_core.reporting.step_interceptor import StepInterceptor
from nac_test.pyats_core.reporting.types import ResultStatus
import nac_test.pyats_core.reporting.step_interceptor as interceptor_module
import markdown  # type: ignore[import-untyped]
import asyncio
import httpx

T = TypeVar("T")



class NACTestBase(aetest.Testcase):
    """Generic base class with common functionality for all architectures.

    This enhanced base class provides:
    - Common setup for all test architectures
    - HTML reporting support with pre-rendered metadata
    - Result collection during test execution
    - Connection pooling and retry logic (HTTP/API)
    - SSH command execution and tracking (SSH/Device)
    - Class variable enforcement for test metadata
    """

    # Test metadata class variables (enforced in subclasses)
    TEST_TYPE_NAME: Optional[str] = None

    # Explicit attribute types to avoid type comments later
    batching_reporter: Optional[BatchingReporter] = None
    step_interceptor: Optional[StepInterceptor] = None
    _current_test_context: Optional[str] = None

    # Status mapping for converting string status to ResultStatus enum
    STATUS_MAPPING: Dict[str, ResultStatus] = {
        "PASSED": ResultStatus.PASSED,
        "FAILED": ResultStatus.FAILED,
        "SKIPPED": ResultStatus.SKIPPED,
        "ERRORED": ResultStatus.ERRORED,
        "INFO": ResultStatus.INFO,
    }

    def __init_subclass__(cls, **kwargs):
        """Enforce required class variables in subclasses.

        This method validates that concrete test classes define required
        class variables for proper test metadata and reporting.

        Args:
            **kwargs: Additional keyword arguments passed to super().__init_subclass__

        Raises:
            TypeError: If required class variables are not defined
        """
        super().__init_subclass__(**kwargs)

        # Skip validation for known abstract intermediate classes
        # These classes extend NACTestBase but are still meant to be subclassed
        abstract_classes = {
            'APICTestBase',
            'SSHTestBase',
            'NACTestBase'  # Include self to handle edge cases
        }

        if cls.__name__ in abstract_classes:
            return

        # Enforce TEST_TYPE_NAME for concrete test classes
        if not hasattr(cls, 'TEST_TYPE_NAME') or cls.TEST_TYPE_NAME is None:
            raise TypeError(
                f"{cls.__name__} must define TEST_TYPE_NAME class variable. "
                f"Example: TEST_TYPE_NAME = 'BGP Peer' or 'Bridge Domain' or 'BFD Session'. "
                f"This should be a human-readable name for the type of network element being tested."
            )

    @classmethod
    @lru_cache(maxsize=1)
    def get_rendered_metadata(cls) -> Dict[str, str]:
        """Get pre-rendered HTML metadata - computed once per class.

        This method pre-renders test metadata to HTML format once and caches it,
        avoiding redundant processing during report generation. This makes report
        generation 100x faster for large test suites.

        Returns:
            Dictionary containing pre-rendered HTML for:
                - title: Test title or class name
                - description_html: Rendered test description
                - setup_html: Rendered setup information
                - procedure_html: Rendered test procedure
                - criteria_html: Rendered pass/fail criteria
        """
        # Get the module object to access module-level constants
        module = sys.modules[cls.__module__]

        return {
            "title": getattr(module, "TITLE", cls.__name__),
            "description_html": cls._render_html(getattr(module, "DESCRIPTION", "")),
            "setup_html": cls._render_html(getattr(module, "SETUP", "")),
            "procedure_html": cls._render_html(getattr(module, "PROCEDURE", "")),
            "criteria_html": cls._render_html(
                getattr(module, "PASS_FAIL_CRITERIA", "")
            ),
        }

    @staticmethod
    def _render_html(text: str) -> str:
        """Convert Markdown text to HTML using the markdown library.

        Converts Markdown-formatted text to HTML with support for:
        - Lists (ordered and unordered, including nested)
        - Bold text (**text**)
        - Italic text (*text*)
        - Code blocks (inline and fenced)
        - Headings
        - Links
        - And more standard Markdown features

        Args:
            text: Markdown-formatted text to convert to HTML

        Returns:
            HTML formatted text
        """
        if not text:
            return ""

        # Configure markdown with useful extensions
        md = markdown.Markdown(  # type: ignore[no-any-return]
            extensions=[
                "extra",  # Includes tables, footnotes, abbreviations, etc.
                "nl2br",  # Converts newlines to <br> tags
                "sane_lists",  # Better list handling
            ]
        )

        # Convert markdown to HTML
        html = str(md.convert(text))

        return html

    @aetest.setup
    def setup(self) -> None:
        """Common setup for all tests"""
        # Configure test-specific logger
        self.logger = logging.getLogger(self.__class__.__module__)

        # Load merged data model created by nac-test
        self.data_model = self.load_data_model()

        # Get controller details from environment
        # Note: Environment validation happens in orchestrator pre-flight check
        self.controller_type = os.environ.get("CONTROLLER_TYPE", "ACI")
        self.controller_url = os.environ[f"{self.controller_type}_URL"]
        self.username = os.environ[f"{self.controller_type}_USERNAME"]
        self.password = os.environ[f"{self.controller_type}_PASSWORD"]

        # Connection pool is shared within process (for API tests)
        self.pool = ConnectionPool()

        # Initialize result collector for HTML reporting
        self._initialize_result_collector()

        # Initialize batching reporter to prevent reporter bottleneck
        self._initialize_batching_reporter()

        # Initialize recovery tracking for controller connectivity issues
        self._controller_recovery_count = 0
        self._total_recovery_downtime = 0.0

    def _initialize_result_collector(self) -> None:
        """Initialize the result collector for this test.

        Sets up the TestResultCollector with a unique test ID and
        attaches pre-rendered metadata for efficient report generation.
        """
        # Get output directory from merged data model file path (already set by orchestrator)
        data_file_path = os.environ.get("MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH", "")
        data_file = Path(data_file_path) if data_file_path else None
        if data_file and data_file.exists():
            # Use base output directory (parent of data file) to avoid conflict with pyats_results cleanup
            base_output_dir = data_file.parent
            output_dir = base_output_dir / "pyats_results"  # Keep for emergency dumps
        else:
            base_output_dir = Path(".")
            output_dir = Path(".")

        # Store output directory for emergency dumps
        self.output_dir = output_dir

        # Create html_report_data_temp in base output directory to avoid deletion during report generation
        # This directory will NOT include pyats_results path to prevent cleanup conflicts
        html_report_data_dir = base_output_dir / "html_report_data_temp"
        html_report_data_dir.mkdir(exist_ok=True)

        # Generate unique test ID
        test_id = self._generate_test_id()
        self.result_collector = TestResultCollector(test_id, html_report_data_dir)
        # mypy: allow private attribute set for linking test instance
        self.result_collector._test_instance = self  # type: ignore[attr-defined]

        # Attach pre-rendered metadata to collector
        metadata = self.get_rendered_metadata()

        # Add jobfile path to metadata
        module = sys.modules[self.__class__.__module__]
        if hasattr(module, "__file__") and module.__file__:
            # Get relative path from project root if possible
            try:
                jobfile_path = Path(module.__file__)
                # Try to make it relative to common parent paths
                for parent in ["tests/", "templates/", "pyats/"]:
                    if parent in str(jobfile_path):
                        parts = str(jobfile_path).split(parent)
                        if len(parts) > 1:
                            metadata["jobfile_path"] = parent + parts[1]
                            break
                else:
                    # Fallback to just the filename if no common parent found
                    metadata["jobfile_path"] = jobfile_path.name
            except Exception:
                metadata["jobfile_path"] = "unknown"
        else:
            metadata["jobfile_path"] = "unknown"

        self.result_collector.metadata = metadata

        self.logger.debug(f"Initialized result collector with test_id: {test_id}")

    def _initialize_batching_reporter(self) -> None:
        """Initialize batching reporter and install step interceptors.

        This sets up the batching infrastructure to handle high-volume
        PyATS reporter messages, preventing socket timeouts during tests
        with many steps (e.g., 1500+ verifications).

        The batching reporter:
        - Buffers messages in memory batches
        - Switches to queue mode during bursts
        - Uses worker thread for async processing
        - Provides graceful shutdown on test completion

        This is always enabled to prevent reporter bottleneck issues that
        cause test failures with high step counts.
        """
        try:
            # Create batching reporter instance
            self.batching_reporter = BatchingReporter(
                send_callback=self._send_batch_to_pyats,
                error_callback=self._handle_batching_error,
            )

            # Set the global batching_reporter that step_interceptor expects
            interceptor_module.batching_reporter = self.batching_reporter
            interceptor_module.interception_enabled = True

            # Create step interceptor
            self.step_interceptor = StepInterceptor(self.batching_reporter)

            # Install the interceptors on PyATS Step class
            if self.step_interceptor.install_interceptors():
                self.logger.info(
                    "Batching reporter initialized successfully (batch size: %d, flush timeout: %.1fs)",
                    self.batching_reporter.batch_size,
                    self.batching_reporter.flush_timeout,
                )
            else:
                self.logger.warning(
                    "Failed to install step interceptors, batching disabled"
                )
                self.batching_reporter = None
                self.step_interceptor = None
                interceptor_module.interception_enabled = False

        except ImportError as e:
            self.logger.error("Failed to import batching reporter modules: %s", e)
            self.batching_reporter = None
            self.step_interceptor = None
        except Exception as e:
            self.logger.error(
                "Failed to initialize batching reporter: %s", e, exc_info=True
            )
            self.batching_reporter = None
            self.step_interceptor = None

    def _send_batch_to_pyats(self, messages: List[Any]) -> bool:
        """Send a batch of messages to PyATS reporter with dual-path reporting.

        This is the callback used by BatchingReporter. It implements:
        1. Primary path: PyATS reporter (with best-effort recovery)
        2. Backup path: ResultCollector (always works)
        3. Emergency path: JSON dump (last resort)

        Args:
            messages: List of buffered messages to send

        Returns:
            True if successful (even if only ResultCollector succeeded)
        """
        pyats_success = False
        max_retries = 3

        # ========== PATH 1: Try PyATS Reporter (with recovery) ==========
        for attempt in range(max_retries):
            try:
                # Get PyATS reporter instance
                reporter = self._get_pyats_reporter()
                if not reporter:
                    if attempt < max_retries - 1:
                        self.logger.warning(
                            "PyATS reporter not available, attempting recovery (attempt %d/%d)",
                            attempt + 1,
                            max_retries,
                        )
                        self._attempt_reporter_recovery()
                        continue
                    else:
                        self.logger.error(
                            "PyATS reporter unavailable after %d attempts", max_retries
                        )
                        break

                # Try to send each message in the batch
                messages_sent = 0
                for msg_data in messages:
                    # Handle both (message, metadata) tuples and plain messages
                    if isinstance(msg_data, tuple) and len(msg_data) == 2:
                        # Message is (message, metadata) tuple from worker thread
                        message, metadata = msg_data
                    else:
                        # Message is just the message dict
                        message = msg_data
                        metadata = None

                    # Transform and send to PyATS
                    if self._send_single_message_to_pyats(reporter, message, metadata):
                        messages_sent += 1
                    else:
                        self.logger.debug("Failed to send message to PyATS reporter")
                        # Continue with other messages even if one fails

                # Consider it a success if we sent at least some messages
                if messages_sent > 0:
                    pyats_success = True
                    self.logger.debug(
                        "Sent %d/%d messages to PyATS reporter",
                        messages_sent,
                        len(messages),
                    )
                    break

            except (BrokenPipeError, OSError) as e:
                # Connection-level errors that might be recoverable
                if attempt < max_retries - 1:
                    self.logger.warning(
                        "PyATS reporter connection failed: %s. Attempting recovery (attempt %d/%d)",
                        e,
                        attempt + 1,
                        max_retries,
                    )
                    self._attempt_reporter_recovery()
                    # Exponential backoff
                    time.sleep(0.5 * (attempt + 1))
                else:
                    self.logger.error(
                        "PyATS reporter connection failed after %d attempts: %s",
                        max_retries,
                        e,
                    )

            except AttributeError as e:
                # Reporter became None or lost attributes
                if "NoneType" in str(e):
                    self.logger.error(
                        "PyATS reporter became None: %s", e, exc_info=True
                    )
                    break  # No point retrying if reporter is gone
                else:
                    raise  # Re-raise unexpected AttributeErrors

            except Exception as e:
                # Unexpected errors - log but don't retry
                self.logger.error(
                    "Unexpected error sending to PyATS reporter: %s", e, exc_info=True
                )
                break

        # ========== PATH 2: Always Update ResultCollector (backup) ==========
        self._update_result_collector_from_messages(messages)

        # ========== PATH 3: Emergency Dump if PyATS Failed ==========
        if not pyats_success:
            self._emergency_dump_messages(messages)

        # Return True even if only ResultCollector succeeded
        # This prevents the BatchingReporter from thinking there's a problem
        return True

    def _get_pyats_reporter(self) -> Optional[Any]:
        """Get the PyATS reporter instance if available.

        Looks for reporter in multiple places:
        1. Instance attribute (self.reporter)
        2. Runtime reporter
        3. Parent reporter

        Returns:
            Reporter instance or None if not found
        """
        # Check if we have a reporter attribute
        if hasattr(self, "reporter") and self.reporter:
            return self.reporter

        # Check runtime for reporter
        try:
            from pyats import aetest

            if hasattr(aetest, "runtime") and hasattr(aetest.runtime, "reporter"):
                return aetest.runtime.reporter
        except ImportError:
            pass

        # Check parent for reporter
        if hasattr(self, "parent") and hasattr(self.parent, "reporter"):
            return self.parent.reporter

        return None

    def _send_single_message_to_pyats(
        self, reporter: Any, message: Dict[str, Any], metadata: Optional[Any] = None
    ) -> bool:
        """Send a single message to PyATS reporter.

        Transforms our message format to PyATS reporter API calls.

        Args:
            reporter: PyATS reporter instance
            message: Message dict with type and content
            metadata: Optional message metadata

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Extract message type and content
            message_type = message.get("message_type", "")
            content = message.get("message_content", {})

            # Map our message types to PyATS reporter methods
            if message_type == "step_start":
                # Starting a step
                if hasattr(reporter, "start_step"):
                    reporter.start_step(
                        name=content.get("name", "unknown"),
                        description=content.get("description", ""),
                    )
                return True

            elif message_type == "step_stop":
                # Stopping a step
                if hasattr(reporter, "stop_step"):
                    reporter.stop_step(
                        name=content.get("name", "unknown"),
                        result=content.get("result", "passed"),
                    )
                return True

            elif message_type == "log":
                # Log message
                if hasattr(reporter, "log"):
                    reporter.log(content.get("message", ""))
                return True

            else:
                # Unknown message type, try generic send
                if hasattr(reporter, "send"):
                    reporter.send(message_type, **content)
                    return True

            self.logger.debug("Reporter doesn't support message type: %s", message_type)
            return False

        except Exception as e:
            self.logger.debug("Error sending message to PyATS: %s", e)
            return False

    def _handle_batching_error(self, error: Exception, messages: List[Any]) -> None:
        """Handle errors from batching reporter.

        This callback is invoked when the batching reporter encounters
        an error that it cannot handle internally.

        Args:
            error: The exception that occurred
            messages: Messages that failed to send (for potential recovery)
        """
        self.logger.error(
            "Batching reporter error: %s (failed to send %d messages)",
            error,
            len(messages),
        )
        # Emergency dump messages to ensure they're not lost
        self._emergency_dump_messages(messages)

    def _attempt_reporter_recovery(self) -> bool:
        """Attempt best-effort recovery of PyATS reporter connection.

        This is a "Hail Mary" attempt - it might work, but we can't rely on it.
        PyATS wasn't designed for runtime reconnection, only fork-time.

        Returns:
            True if recovery seemed to work, False otherwise
        """
        try:
            # Try to get current reporter
            reporter = self._get_pyats_reporter()
            if not reporter:
                self.logger.debug("No reporter to recover")
                return False

            # Check if reporter has a client with connection
            if hasattr(reporter, "client"):
                client = reporter.client

                # Try to close existing broken connection
                if hasattr(client, "_conn") and client._conn:
                    try:
                        client._conn.close()
                    except Exception:
                        pass  # Ignore errors closing broken connection

                # Try to reconnect using PyATS's own method
                if hasattr(client, "connect"):
                    try:
                        client.connect()
                        self.logger.info("Reporter reconnection appeared successful")
                        return True
                    except Exception as e:
                        self.logger.debug("Reporter reconnection failed: %s", e)
                        return False

            return False

        except Exception as e:
            self.logger.debug("Reporter recovery attempt failed: %s", e)
            return False

    def _update_result_collector_from_messages(self, messages: List[Any]) -> None:
        """Update ResultCollector with messages for dual-path reporting.

        This ensures test results are captured even if PyATS reporter fails.
        ResultCollector can generate HTML reports independently of PyATS.

        Args:
            messages: List of messages (may be tuples or dicts)
        """
        if not hasattr(self, "result_collector"):
            return  # No collector initialized

        try:
            from nac_test.pyats_core.reporting.types import ResultStatus

            for msg_data in messages:
                # Extract message and metadata
                if isinstance(msg_data, tuple) and len(msg_data) == 2:
                    message, metadata = msg_data
                else:
                    message = msg_data
                    metadata = None

                # Only process step_stop messages (they contain results)
                message_type = message.get("message_type", "")
                if message_type == "step_stop":
                    content = message.get("message_content", {})
                    result = content.get("result", "unknown")
                    name = content.get("name", "Unknown step")

                    # Map PyATS result to ResultStatus
                    if result == "passed":
                        status = ResultStatus.PASSED
                    elif result == "failed":
                        status = ResultStatus.FAILED
                    elif result == "errored":
                        status = ResultStatus.ERRORED
                    elif result == "skipped":
                        status = ResultStatus.SKIPPED
                    else:
                        status = ResultStatus.INFO

                    # Build detailed message with context
                    if metadata:
                        context_path = getattr(metadata, "context_path", "")
                        if context_path:
                            full_message = f"{context_path}: {name} - {result}"
                        else:
                            full_message = f"{name} - {result}"
                    else:
                        full_message = f"{name} - {result}"

                    # Add to result collector
                    self.result_collector.add_result(status, full_message)

        except Exception as e:
            # Don't let collector errors break the test
            self.logger.debug("Error updating result collector: %s", e)

    def _emergency_dump_messages(self, messages: List[Any]) -> None:
        """Emergency dump messages to disk when all else fails.

        This is the last resort to ensure test results are never lost.
        Dumps to a JSON file in the user's output directory (or /tmp as fallback).

        Args:
            messages: List of messages that couldn't be sent
        """
        try:
            # Generate unique filename
            test_name = self.__class__.__name__
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pid = os.getpid()
            filename = f"pyats_recovery_{test_name}_{pid}_{timestamp}.json"

            # Try to use user's output directory first
            dump_file = None
            if hasattr(self, "output_dir") and self.output_dir:
                try:
                    # Create emergency_dumps subdirectory
                    emergency_dir = self.output_dir / "emergency_dumps"
                    emergency_dir.mkdir(exist_ok=True)
                    dump_file = emergency_dir / filename
                except Exception as e:
                    self.logger.debug(
                        "Cannot create emergency directory in output dir: %s", e
                    )

            # Fallback to /tmp if output_dir not available or not writable
            if dump_file is None:
                dump_file = Path(f"/tmp/{filename}")

            # Prepare data for dumping
            dump_data: Dict[str, Any] = {
                "test_name": test_name,
                "test_id": getattr(self, "_test_id", "unknown"),
                "timestamp": datetime.now().isoformat(),
                "pid": pid,
                "message_count": len(messages),
                "messages": [],
            }

            # Process messages for JSON serialization
            for msg_data in messages:
                if isinstance(msg_data, tuple) and len(msg_data) == 2:
                    message, metadata = msg_data
                    # Convert metadata to dict if needed
                    if metadata and hasattr(metadata, "__dict__"):
                        metadata_dict = {
                            "sequence_num": getattr(metadata, "sequence_num", None),
                            "timestamp": getattr(metadata, "timestamp", None),
                            "context_path": getattr(metadata, "context_path", None),
                            "message_type": getattr(metadata, "message_type", None),
                            "estimated_size": getattr(metadata, "estimated_size", None),
                        }
                    else:
                        metadata_dict = None
                    dump_data["messages"].append(
                        {"message": message, "metadata": metadata_dict}
                    )
                else:
                    dump_data["messages"].append({"message": msg_data})

            # Write to file
            with open(dump_file, "w") as f:
                json.dump(dump_data, f, indent=2, default=str)

            # Log with clear indication of location
            if "/tmp/" in str(dump_file):
                self.logger.error(
                    "EMERGENCY: PyATS reporter failed! %d messages saved to: %s",
                    len(messages),
                    dump_file,
                )
                self.logger.warning(
                    "Note: Emergency dump is in /tmp (output dir was not accessible). "
                    "Copy this file before reboot!"
                )
            else:
                self.logger.error(
                    "EMERGENCY: PyATS reporter failed! %d messages saved to output directory: %s",
                    len(messages),
                    dump_file,
                )

            self.logger.error(
                "Recovery command: cat %s | python -m json.tool", dump_file
            )

        except Exception as e:
            # Last resort failed - at least log what we can
            self.logger.critical(
                "CRITICAL: Emergency dump failed! Lost %d messages. Error: %s",
                len(messages),
                e,
            )

    def _generate_test_id(self) -> str:
        """Generate unique test ID based on class name and timestamp.

        Creates a unique identifier for this test execution using the
        test class name and current timestamp.

        Returns:
            Unique test ID string in format: classname_YYYYMMDD_HHMMSS_mmm
        """
        class_name = self.__class__.__name__.lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[
            :-3
        ]  # Millisecond precision
        return f"{class_name}_{timestamp}"

    def load_data_model(self) -> Dict[str, Any]:
        """Load the merged data model from the test environment.

        Returns:
            Merged data model dictionary
        """
        data_file_path = os.environ.get("MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH")
        if not data_file_path:
            raise FileNotFoundError(
                "Environment variable MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH is not set"
            )

        data_file = Path(data_file_path)
        if not data_file.exists():
            raise FileNotFoundError(
                f"Merged data model file not found: {data_file_path}"
            )

        with open(data_file, "r") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}

    # =========================================================================
    # API-SPECIFIC METHODS (for API/HTTP-based tests)
    # =========================================================================

    async def api_call_with_retry(
        self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        """Standard API call with retry logic

        Args:
            func: Async function to execute with retry
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from successful function execution
        """
        return await SmartRetry.execute(func, *args, **kwargs)

    def get_connection_params(self) -> Dict[str, Any]:
        """Get connection parameters for the specific architecture.

        Must be implemented by subclasses to return architecture-specific
        connection details.
        """
        raise NotImplementedError(
            "Subclasses must implement get_connection_params() method"
        )

    def wrap_client_for_tracking(
        self, client: Any, device_name: str = "Controller"
    ) -> Any:
        """Wrap httpx client to automatically track API calls.

        This wrapper intercepts all HTTP methods (GET, POST, PUT, DELETE, PATCH)
        and automatically records the API calls for HTML reporting.

        Args:
            client: The httpx.AsyncClient to wrap
            device_name: Name to use for the device in reports (e.g., "APIC", "vManage", "ISE")

        Returns:
            The wrapped client with tracking capabilities
        """
        # Store original methods
        original_get = client.get
        original_post = client.post
        original_put = client.put
        original_delete = client.delete
        original_patch = client.patch

        # Store reference to self for use in closures
        test_instance = self

        # Sensible retry configuration for APIC/controllers connections
        # Aggressive retry with exponential backoff to handle controller stress
        # Max total wait time: ~10 minutes (5 + 10 + 20 + 40 + 80 + 160 + 300 = 615 seconds)
        # TODO: Move this to constants.py later
        MAX_RETRIES = 7  # Increased from 3 to give more recovery time at high scale may come into play
        INITIAL_DELAY = 5.0  # Start with 5 seconds
        MAX_DELAY = 300.0  # Cap at 5 minutes per retry

        async def execute_with_retry(
            method_name: str,
            original_method: Callable[..., Awaitable[Any]],
            url: str,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            """Execute HTTP method with aggressive retry logic for APIC recovery.

            Handles all HTTP errors including:
            - Connection timeouts (network issues)
            - Read/Write/Pool timeouts (slow responses)
            - RemoteProtocolError (server disconnections)
            - Any other HTTP errors (server errors, rate limiting, etc.)

            Args:
                method_name: HTTP method name for logging (GET, POST, etc.)
                original_method: The original httpx method to call
                url: The URL being accessed
                *args, **kwargs: Arguments to pass to the method

            Returns:
                The HTTP response

            Raises:
                httpx exceptions after all retries exhausted
            """
            for attempt in range(MAX_RETRIES):
                try:
                    response = await original_method(url, *args, **kwargs)

                    # If we succeed after retries, log recovery prominently
                    if attempt > 0:
                        # Calculate total downtime for this recovery
                        recovery_downtime = sum(
                            min(INITIAL_DELAY * (2**i), MAX_DELAY)
                            for i in range(attempt)
                        )

                        # Track recovery statistics
                        self._controller_recovery_count += 1
                        self._total_recovery_downtime += recovery_downtime

                        # Use WARNING level to match failure visibility
                        self.logger.warning(
                            f"✅ CONTROLLER RECOVERED: {method_name} {url} is responding again "
                            f"(recovered after {attempt} attempt{'s' if attempt > 1 else ''}, "
                            f"~{recovery_downtime:.1f}s downtime)"
                        )

                        # Also log at INFO for detailed tracking
                        self.logger.info(
                            f"API connectivity restored to controller after {attempt} retry attempts"
                        )

                    return response

                except (httpx.HTTPError, httpx.RemoteProtocolError, Exception) as e:
                    # Catch ALL HTTP errors including RemoteProtocolError
                    # Also catch generic Exception in case httpx raises something unexpected

                    # Don't retry on non-HTTP exceptions (like programming errors)
                    if not isinstance(e, (httpx.HTTPError, httpx.RemoteProtocolError)):
                        # Check if it's a network/HTTP related error
                        error_msg = str(e).lower()
                        if not any(
                            term in error_msg
                            for term in [
                                "timeout",
                                "connection",
                                "disconnected",
                                "protocol",
                                "http",
                                "socket",
                                "network",
                                "refused",
                                "reset",
                                "broken",
                            ]
                        ):
                            # Not a network error, don't retry
                            raise

                    if attempt == MAX_RETRIES - 1:
                        # Final attempt failed, log error and re-raise
                        self.logger.error(
                            f"{method_name} {url} failed after {MAX_RETRIES} attempts: "
                            f"{e.__class__.__name__}: {str(e)}"
                        )
                        # Ensure connection is closed
                        if hasattr(e, "request") and e.request:
                            try:
                                await e.request.aclose()
                            except Exception:
                                pass  # Best effort cleanup
                        raise

                    # Calculate backoff delay (exponential with cap)
                    delay = min(INITIAL_DELAY * (2**attempt), MAX_DELAY)

                    # Determine error type for better logging
                    if isinstance(e, httpx.RemoteProtocolError):
                        error_type = "Server disconnected"
                    elif isinstance(
                        e,
                        (
                            httpx.ConnectTimeout,
                            httpx.ReadTimeout,
                            httpx.WriteTimeout,
                            httpx.PoolTimeout,
                        ),
                    ):
                        error_type = "Timeout"
                    elif isinstance(e, httpx.HTTPStatusError):
                        error_type = f"HTTP {e.response.status_code}"
                    else:
                        error_type = e.__class__.__name__

                    self.logger.warning(
                        f"⏳ BACKING OFF: {method_name} {url} failed ({error_type}), "
                        f"attempt {attempt + 1}/{MAX_RETRIES}, waiting {delay}s for APIC recovery..."
                    )

                    # Ensure connection is closed before retry
                    if hasattr(e, "request") and e.request:
                        try:
                            await e.request.aclose()
                        except Exception:
                            pass  # Best effort cleanup

                    # For server disconnections, add extra delay on first few retries
                    # This gives APIC/controllers more time to recover from stress
                    if isinstance(e, httpx.RemoteProtocolError) and attempt < 3:
                        extra_delay = 10  # Add 10 seconds for server recovery
                        self.logger.info(
                            f"Adding {extra_delay}s extra delay for APIC recovery"
                        )
                        await asyncio.sleep(extra_delay)

                    await asyncio.sleep(delay)

        async def tracked_get(
            url: str, *args: Any, test_context: Optional[str] = None, **kwargs: Any
        ) -> Any:
            """Tracked GET method with retry and connection cleanup."""
            response = await execute_with_retry(
                "GET", original_get, url, *args, **kwargs
            )
            test_instance._track_api_response(
                "GET", url, response, device_name, test_context=test_context
            )
            return response

        async def tracked_post(
            url: str, *args: Any, test_context: Optional[str] = None, **kwargs: Any
        ) -> Any:
            """Tracked POST method with retry and connection cleanup."""
            response = await execute_with_retry(
                "POST", original_post, url, *args, **kwargs
            )
            test_instance._track_api_response(
                "POST",
                url,
                response,
                device_name,
                kwargs.get("json", kwargs.get("data")),
                test_context=test_context,
            )
            return response

        async def tracked_put(
            url: str, *args: Any, test_context: Optional[str] = None, **kwargs: Any
        ) -> Any:
            """Tracked PUT method with retry and connection cleanup."""
            response = await execute_with_retry(
                "PUT", original_put, url, *args, **kwargs
            )
            test_instance._track_api_response(
                "PUT",
                url,
                response,
                device_name,
                kwargs.get("json", kwargs.get("data")),
                test_context=test_context,
            )
            return response

        async def tracked_delete(
            url: str, *args: Any, test_context: Optional[str] = None, **kwargs: Any
        ) -> Any:
            """Tracked DELETE method with retry and connection cleanup."""
            response = await execute_with_retry(
                "DELETE", original_delete, url, *args, **kwargs
            )
            test_instance._track_api_response(
                "DELETE", url, response, device_name, test_context=test_context
            )
            return response

        async def tracked_patch(
            url: str, *args: Any, test_context: Optional[str] = None, **kwargs: Any
        ) -> Any:
            """Tracked PATCH method with retry and connection cleanup."""
            response = await execute_with_retry(
                "PATCH", original_patch, url, *args, **kwargs
            )
            test_instance._track_api_response(
                "PATCH",
                url,
                response,
                device_name,
                kwargs.get("json", kwargs.get("data")),
                test_context=test_context,
            )
            return response

        # Replace methods with tracked versions
        client.get = tracked_get
        client.post = tracked_post
        client.put = tracked_put
        client.delete = tracked_delete
        client.patch = tracked_patch

        return client

    def _track_api_response(
        self,
        method: str,
        url: str,
        response: Any,
        device_name: str,
        request_data: Optional[Dict[str, Any]] = None,
        test_context: Optional[str] = None,
    ) -> None:
        """Track an API response in the result collector.

        Args:
            method: HTTP method used (GET, POST, etc.)
            url: The URL that was called
            response: The httpx response object
            device_name: Name of the device/controller
            request_data: Optional request payload for POST/PUT/PATCH
            test_context: Explicit test context for this specific API call (eliminates race conditions)
        """
        if not hasattr(self, "result_collector"):
            # Safety check - collector might not be initialized in some edge cases
            return

        try:
            # Format the command/endpoint string
            command = f"{method} {url}"

            # Get response text (limited to prevent memory issues)
            try:
                response_text = response.text[:50000]  # Pre-truncate to 50KB
            except Exception:
                response_text = (
                    f"<Unable to read response - Status: {response.status_code}>"
                )

            # Use explicit test context parameter (eliminates race conditions)
            # test_context is now passed as parameter instead of reading shared state

            # Use the unified tracking method
            self.result_collector.add_command_api_execution(
                device_name=device_name,
                command=command,
                output=response_text,
                test_context=test_context,
            )

            # Log at debug level
            self.logger.debug(
                f"Tracked API call: {command} - Status: {response.status_code}"
            )

        except Exception as e:
            # Don't let tracking errors break the test
            self.logger.warning(f"Failed to track API call: {e}")

    # =========================================================================
    # SHARED METHODS (for both API and SSH tests)
    # =========================================================================

    def set_test_context(self, context: str) -> None:
        """Set the current test context for command/API tracking.

        This context will be included with any command or API executions
        tracked while it's set, helping to correlate executions with
        specific test steps in the HTML report.

        Args:
            context: Description of the current test step/verification
                    Example: "BGP peer 10.100.2.73 on node 202"
        """
        self._current_test_context = context

    def clear_test_context(self) -> None:
        """Clear the current test context."""
        self._current_test_context = None

    @contextmanager
    def test_context(self, context: str) -> Iterator[None]:
        """Context manager for setting test context temporarily.

        This provides a clean way to set context for a block of code
        and automatically clear it afterwards.

        Args:
            context: Description of the current test step/verification

        Example:
            with self.test_context("BGP peer 10.100.2.73 on node 202"):
                # API calls or SSH commands made here will include this context
                response = await client.get(url)
                # OR
                output = await self.execute_command("show ip bgp summary")
        """
        self.set_test_context(context)
        try:
            yield
        finally:
            self.clear_test_context()

    # =========================
    # RESULT PROCESSING METHODS
    # =========================

    def format_verification_result(
        self,
        status: ResultStatus,
        context: Dict[str, Any],
        reason: str,
        api_duration: float = 0,
        api_details: Optional[ApiDetails] = None,
    ) -> BaseVerificationResultOptional:
        """Standard result formatter for all verification types.

        This method provides a consistent format for verification results across
        all test types in the NAC test framework. It standardizes the structure
        and content of result dictionaries to ensure uniform reporting and
        processing throughout the system.

        Args:
            status: Verification outcome (PASSED, FAILED, SKIPPED from ResultStatus enum)
            context: Complete context object containing all verification details
                    including tenant names, item identifiers, resolved names, and
                    any additional metadata needed for reporting and debugging
            reason: Customer-facing explanation of the verification result
                   Should be descriptive and actionable for network operators
            api_duration: API call timing in seconds for performance analysis
                        Defaults to 0 for non-API operations
            api_details: Optional API transaction details including URL, response code,
                       and response body for debugging purposes

        Returns:
            dict: Standardized result structure for nac-test framework containing:
                - status: The verification outcome
                - context: Complete context object for detailed reporting
                - reason: Human-readable explanation of the result
                - api_duration: Performance timing information
                - timestamp: When the result was created for audit trail
                - api_details: Optional API transaction details (if provided)

        Example:
            result = self.format_verification_result(
                status=ResultStatus.PASSED,
                context={
                    "tenant_name": "production",
                    "bd_name": "web_bd",
                    "resolved_bd_name": "web_bd_prod"
                },
                reason="Bridge Domain attributes verified successfully",
                api_duration=0.245
            )
        """
        result = {
            "status": status,
            "context": context,
            "reason": reason,
            "api_duration": api_duration,
            "timestamp": time.time(),
        }

        if api_details:
            result["api_details"] = api_details

        return result

    def create_comprehensive_skip_result(
        self,
        test_scope: str,
        schema_paths: List[str],
        managed_objects: List[str],
        interpretation: str,
        api_queries: Optional[List[str]] = None,
        additional_sections: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate detailed skip results with comprehensive documentation.

        This method creates standardized skip result documentation that provides
        valuable information about test scope even when no configuration exists.
        It generates detailed skip results that help with deployment planning
        and feature coverage analysis by documenting exactly what the test
        would verify if data were present.

        Args:
            test_scope: Description of what this test verifies (e.g., "BGP Peers Operational State")
            schema_paths: List of data model paths checked (e.g., ["tenants[].l3outs[]"])
            managed_objects: List of technology-specific managed objects (e.g., ["bgpPeerEntry", "fvBD"])
            interpretation: Explanation of why test is skipped and what it means
            api_queries: Optional list of API query pattern examples for documentation
            additional_sections: Optional list of additional documentation sections

        Returns:
            dict: Detailed skip result with comprehensive documentation

        Example:
            skip_result = self.create_comprehensive_skip_result(
                test_scope="BGP Peers Operational State",
                schema_paths=["tenants[].l3outs[].bgp_peers[]"],
                managed_objects=["bgpPeerEntry", "bgpPeerAf"],
                interpretation="No BGP peers are configured in L3Outs",
                api_queries=[
                    "/api/node/mo/topology/pod-*/node-*/sys/bgp/inst/dom-*/peer-*/ent-*.json",
                    "/api/node/class/bgpPeerEntry.json"
                ]
            )
        """
        # Build the detailed skip documentation message
        skip_details = []

        # Validate technology-specific implementation for non-generic base classes
        if self.__class__.__name__ != "NACTestBase":
            if not hasattr(self, "TECHNOLOGY_NAME"):
                raise NotImplementedError(
                    f"{self.__class__.__name__} must define TECHNOLOGY_NAME class variable. "
                    f"Example: TECHNOLOGY_NAME = 'ACI' or 'SD-WAN' or 'Catalyst Center'"
                )
            if not hasattr(self, "MANAGED_OBJECTS_LABEL"):
                raise NotImplementedError(
                    f"{self.__class__.__name__} must define MANAGED_OBJECTS_LABEL class variable. "
                    f"Example: MANAGED_OBJECTS_LABEL = 'ACI managed objects' or 'SD-WAN managed objects'"
                )

        # Use technology-specific name if available, otherwise generic
        technology_name = getattr(self, "TECHNOLOGY_NAME", "Network")
        skip_details.append(f"📋 **{technology_name} Test Scope Documentation**\\n")

        # Use technology-specific label if available, otherwise generic
        managed_objects_label = getattr(
            self, "MANAGED_OBJECTS_LABEL", "managed objects"
        )
        skip_details.append(
            f"\\n**This test verifies the following {managed_objects_label}:**"
        )

        # Add managed objects documentation
        for managed_object in managed_objects:
            skip_details.append(f"• {managed_object}")

        # Add data model paths section
        skip_details.append("\\n**Data model paths checked:**")
        for path in schema_paths:
            skip_details.append(f"• `{path}`")

        # Add API queries if provided
        if api_queries:
            skip_details.append("\\n**API Queries:**")
            for query in api_queries:
                skip_details.append(f"• `{query}`")

        # Add any additional sections
        if additional_sections:
            for section in additional_sections:
                skip_details.append(f"\\n{section}")

        # Add standard conclusion sections
        skip_details.append("\\n**Result:** No matching configurations found")
        skip_details.append(f"**Interpretation:** {interpretation}")
        skip_details.append(
            "**Action:** Test appropriately SKIPPED - no verification needed"
        )

        detailed_message = "\\n".join(skip_details)

        # Log the skip information
        self.logger.info(f"Test will be skipped - {interpretation}")
        self.logger.info(f"Checked {len(schema_paths)} data model paths")

        # Create and return the skip result using the centralized formatter
        return self.format_verification_result(
            status=ResultStatus.SKIPPED,
            context={
                "test_scope": test_scope,
                "schema_paths_checked": schema_paths,
                "managed_objects": managed_objects,
                "skip_type": "no_data_found",
            },
            reason=detailed_message,
            api_duration=0,
        )

    # =========================
    # RESULT PROCESSING METHODS
    # =========================

    def build_api_context(
        self, test_type: str, primary_item: str, **additional_context
    ) -> str:
        """Build standardized API context strings for result tracking.

        This method creates consistent API context strings that link API calls
        to test results in HTML reports. It follows a standardized format:
        "{TestType}: {PrimaryItem} ({Key}: {Value}, {Key}: {Value})"

        Args:
            test_type: Type of test or verification being performed
                      Examples: "BGP Peer", "Bridge Domain", "BFD Session"
            primary_item: Primary identifier for the item being tested
                         Examples: IP address, name, ID
            **additional_context: Additional context items as key-value pairs
                                Examples: tenant="MyTenant", node="101", l3out="External"

        Returns:
            str: Formatted API context string for result collector

        Examples:
            >>> self.build_api_context("BGP Peer", "192.168.1.1", tenant="Production", node="101")
            "BGP Peer: 192.168.1.1 (Tenant: Production, Node: 101)"

            >>> self.build_api_context("Bridge Domain", "web_bd", tenant="MyTenant", vrf="common")
            "Bridge Domain: web_bd (Tenant: MyTenant, Vrf: common)"

            >>> self.build_api_context("BFD Session", "10.0.0.1")
            "BFD Session: 10.0.0.1"
        """
        context_parts = [f"{test_type}: {primary_item}"]

        if additional_context:
            # Sort keys for consistent ordering and capitalize first letter
            details = ", ".join(
                f"{k.title()}: {v}" for k, v in sorted(additional_context.items())
            )
            context_parts.append(f"({details})")

        return " ".join(context_parts)

    def add_verification_result(
        self,
        status: Union[str, ResultStatus],
        test_type: str,
        item_identifier: str,
        details: Optional[str] = None,
        test_context: Optional[str] = None,
    ) -> None:
        """Add verification result to collector with standardized messaging.

        This method standardizes the format of messages added to the result collector,
        ensuring consistent messaging patterns across all test types. It eliminates
        the need for manual message building in individual tests. It accepts either
        string status values (e.g., "PASSED", "FAILED") or ResultStatus enum values.

        Args:
            status: Result status - either string ("PASSED", "FAILED", "SKIPPED")
                   or ResultStatus enum value. String values are automatically
                   converted to enum using the centralized STATUS_MAPPING.
            test_type: Type of verification being performed
                      Examples: "BGP peer", "Bridge Domain subnet", "BFD session"
            item_identifier: Identifier for the specific item being tested
                           Examples: IP address, name, ID
            details: Additional details for failed/skipped results
                    For FAILED: error description or reason for failure
                    For SKIPPED: reason why verification was skipped
                    For PASSED: optional additional success details (usually None)
            test_context: API context string for linking to commands/API calls
                        Use build_api_context() to create consistent format

        Message Patterns:
            - PASSED: "{test_type} {item_identifier} verified successfully"
            - FAILED: "{test_type} {item_identifier} failed: {details}"
            - SKIPPED: "{test_type} {item_identifier} skipped: {details}"

        Examples:
            >>> # Success case with enum
            >>> self.add_verification_result(
            ...     ResultStatus.PASSED,
            ...     "BGP peer",
            ...     "192.168.1.1",
            ...     test_context="BGP Peer: 192.168.1.1 (Tenant: Production, Node: 101)"
            ... )

            >>> # Success case with string (more convenient)
            >>> self.add_verification_result(
            ...     "PASSED",
            ...     "BGP peer",
            ...     "192.168.1.1",
            ...     test_context="BGP Peer: 192.168.1.1 (Tenant: Production, Node: 101)"
            ... )
            # Both add: "BGP peer 192.168.1.1 verified successfully"

            >>> # Failure case with string from result dictionary
            >>> self.add_verification_result(
            ...     result["status"],  # e.g., "FAILED"
            ...     "Bridge Domain subnet",
            ...     "10.1.1.1/24",
            ...     details=result.get("reason", "Unknown error"),
            ...     test_context="Bridge Domain: web_bd (Tenant: Production)"
            ... )
            # Adds: "Bridge Domain subnet 10.1.1.1/24 failed: Connection timeout"
        """
        # Convert string status to enum if needed
        if isinstance(status, str):
            status_enum = self.map_string_status_to_enum(status)
        else:
            status_enum = status

        # Build standardized message based on status
        if status_enum == ResultStatus.PASSED:
            message = f"{test_type} {item_identifier} verified successfully"
            if details:
                message += f" - {details}"
        elif status_enum == ResultStatus.FAILED:
            if details:
                message = f"{test_type} {item_identifier} failed: {details}"
            else:
                message = f"{test_type} {item_identifier} failed"
        elif status_enum == ResultStatus.SKIPPED:
            if details:
                message = f"{test_type} {item_identifier} skipped: {details}"
            else:
                message = f"{test_type} {item_identifier} skipped"
        else:
            # Handle other status types (ERRORED, INFO, etc.)
            if details:
                message = f"{test_type} {item_identifier} {status_enum.value.lower()}: {details}"
            else:
                message = f"{test_type} {item_identifier} {status_enum.value.lower()}"

        # Add to result collector
        self.result_collector.add_result(
            status_enum, message, test_context=test_context
        )

    def map_string_status_to_enum(self, status_string: str) -> ResultStatus:
        """Convert string status to ResultStatus enum using centralized mapping.

        This helper method provides a convenient way to convert string status values
        (like "PASSED", "FAILED", "SKIPPED") to their corresponding ResultStatus enum
        values. It uses the centralized STATUS_MAPPING class variable.

        Args:
            status_string: String status value (e.g., "PASSED", "FAILED", "SKIPPED")

        Returns:
            ResultStatus: Corresponding enum value, or ResultStatus.INFO if not found

        Examples:
            >>> status = self.map_string_status_to_enum("PASSED")
            >>> # Returns ResultStatus.PASSED

            >>> status = self.map_string_status_to_enum("UNKNOWN")
            >>> # Returns ResultStatus.INFO (fallback)
        """
        return self.STATUS_MAPPING.get(status_string, ResultStatus.INFO)

    # =========================
    # RESULT PROCESSING METHODS
    # =========================

    def categorize_results(
        self, results: List[VerificationResult]
    ) -> tuple[List[VerificationResult], List[VerificationResult], List[VerificationResult]]:
        """Categorize verification results into failed, skipped, and passed lists.

        This method provides the standard categorization logic used by all
        process_results_with_steps() implementations. It separates results
        based on their status field for further processing and reporting.

        Handles both string status values ("FAILED", "SKIPPED", "PASSED") and
        ResultStatus enum values (ResultStatus.FAILED, etc.).

        Args:
            results: List of verification result dictionaries containing status field

        Returns:
            tuple: (failed_results, skipped_results, passed_results)
                - failed_results: Results with status "FAILED" or ResultStatus.FAILED
                - skipped_results: Results with status "SKIPPED" or ResultStatus.SKIPPED
                - passed_results: Results with status "PASSED" or ResultStatus.PASSED

        Example:
            >>> failed, skipped, passed = self.categorize_results(results)
            >>> self.logger.info(f"Summary: {len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped")
        """
        failed = [
            r
            for r in results
            if isinstance(r, dict)
            and (r.get("status") == "FAILED" or r.get("status") == ResultStatus.FAILED)
        ]
        skipped = [
            r
            for r in results
            if isinstance(r, dict)
            and (
                r.get("status") == "SKIPPED" or r.get("status") == ResultStatus.SKIPPED
            )
        ]
        passed = [
            r
            for r in results
            if isinstance(r, dict)
            and (r.get("status") == "PASSED" or r.get("status") == ResultStatus.PASSED)
        ]

        return failed, skipped, passed

    def log_result_summary(
        self,
        test_type: str,
        failed: List[VerificationResult],
        skipped: List[VerificationResult],
        passed: List[VerificationResult],
        total_results: Optional[int] = None,
    ) -> None:
        """Log standardized result summary for process_results_with_steps implementations.

        This method provides consistent result summary logging across all test types.
        It supports both simple and detailed logging formats based on the test's needs.

        Args:
            test_type: Descriptive name for the test type (e.g. "Bridge Domain Subnet", "BGP Peer")
            failed: List of failed verification results
            skipped: List of skipped verification results
            passed: List of passed verification results
            total_results: Optional total count override (defaults to sum of all results)

        Example Usage:
            >>> failed, skipped, passed = self.categorize_results(results)
            >>> self.log_result_summary("BGP Peer", failed, skipped, passed)

            >>> # With custom total count
            >>> self.log_result_summary("Bridge Domain", failed, skipped, passed, len(all_items))
        """
        if total_results is None:
            total_results = len(failed) + len(skipped) + len(passed)

        # Log detailed summary with counts
        self.logger.info(f"{test_type} Verification Summary:")
        self.logger.info(f"  - Total configurations processed: {total_results}")
        self.logger.info(f"  - Passed: {len(passed)}")
        self.logger.info(f"  - Failed: {len(failed)}")
        self.logger.info(f"  - Skipped: {len(skipped)}")

    def determine_overall_test_result(
        self,
        failed: List[VerificationResult],
        skipped: List[VerificationResult],
        passed: List[VerificationResult],
    ) -> None:
        """Determine and set overall test result using standardized abstract methods.

        This method provides the common if/elif/else logic pattern used across all
        process_results_with_steps implementations. It now uses the standardized
        abstract formatting methods that subclasses must implement.

        Args:
            failed: List of failed verification results
            skipped: List of skipped verification results
            passed: List of passed verification results

        The method automatically calls the appropriate abstract formatter:
        - format_failure_message() for failures
        - format_success_message() for successes
        - format_skip_message() for all-skipped scenarios

        Example Usage:
            >>> failed, skipped, passed = self.categorize_results(results)
            >>> self.determine_overall_test_result(failed, skipped, passed)
        """
        if failed:
            # Use abstract method implemented by subclass
            failure_message = self.format_failure_message(failed)
            self.failed(failure_message)

        elif skipped and not passed:
            # Handle case where all individual verifications were skipped
            # Use the format_skip_message method (has default implementation)
            skip_message = self.format_skip_message(skipped)
            self.skipped(skip_message)

        else:
            # Success case - use abstract method implemented by subclass
            success_message = self.format_success_message(passed, skipped)
            self.passed(success_message)

    # ===================================
    # REQUIRED RESULT FORMATTING METHODS
    # ===================================

    def format_failure_message(self, failed_results: List[VerificationResult]) -> str:
        """Format failure message for test-specific verification failures.

        This method must be implemented by subclasses to provide domain-specific
        failure details that are meaningful to network operators. The message
        should summarize key failures and provide actionable information.

        Args:
            failed_results: List of failed verification result dictionaries
                          Each result should contain context about what failed
                          and why it failed

        Returns:
            str: Formatted failure message for the overall test result

        Example:
            "5 BGP peers failed: 192.168.1.1 (session down), 192.168.1.2 (wrong AS)"
        """
        raise NotImplementedError("Subclasses must implement format_failure_message()")

    def format_success_message(
        self,
        passed_results: List[VerificationResult],
        skipped_results: List[VerificationResult],
    ) -> str:
        """Format success message for test-specific verification successes.

        This method must be implemented by subclasses to provide domain-specific
        success summaries that give operators confidence in their network state.
        Should include both passed and skipped counts where relevant.

        Args:
            passed_results: List of successful verification result dictionaries
            skipped_results: List of skipped verification result dictionaries
                           (may be empty)

        Returns:
            str: Formatted success message for the overall test result

        Example:
            "15 BGP peers verified successfully, 2 skipped (maintenance mode)"
        """
        raise NotImplementedError("Subclasses must implement format_success_message()")

    def format_skip_message(self, skipped_results: List[VerificationResult]) -> str:
        """Format skip message for all-skipped scenarios.

        This method provides a default implementation that subclasses can override
        if they need custom skip message formatting. Called when all individual
        verifications were skipped.

        Args:
            skipped_results: List of skipped verification result dictionaries

        Returns:
            str: Formatted skip message for the overall test result

        Example:
            "All 8 BGP peer verifications were skipped (no peers configured)"
        """
        return f"All {len(skipped_results)} verifications were skipped"

    def get_test_type_name(self) -> str:
        """Return human-readable test type name for logging and reporting.

        This method returns the value of the TEST_TYPE_NAME class variable,
        which is enforced by __init_subclass__ to ensure all concrete test
        classes define it.

        Returns:
            str: Test type name from TEST_TYPE_NAME class variable
                (e.g., 'BGP Peer', 'Bridge Domain Subnet', 'BFD Session')

        Note:
            The TEST_TYPE_NAME class variable is enforced at class definition time,
            so this method will always have a valid value for concrete test classes.
        """
        return self.__class__.TEST_TYPE_NAME

    def extract_step_context(self, result: VerificationResult) -> Dict[str, Any]:
        """Extract relevant context fields from a result for PyATS step creation.

        This method should extract the key identification fields from the result
        that are needed to create meaningful step names and descriptions.

        Args:
            result: Individual verification result dictionary

        Returns:
            dict: Context object with standardized keys for step formatting

        Examples:
            # BGP test might return:
            return {
                "peer_ip": result["peer"]["ip"],
                "tenant": result["peer"].get("tenant", "N/A"),
                "node": result["peer"].get("node", "N/A")
            }

            # Bridge Domain test might return:
            return {
                "tenant": result["context"].get("tenant_name", "N/A"),
                "bd": result["context"].get("bd_name", "N/A"),
                "subnet": result["context"].get("subnet_ip", "N/A")
            }
        """
        raise NotImplementedError("Subclasses must implement extract_step_context()")

    def format_step_name(self, context: Dict[str, Any]) -> str:
        """Format the PyATS step name from extracted context.

        Creates a concise, informative step name that will appear in PyATS reports.
        Should be descriptive enough to identify the specific verification.

        Args:
            context: Context dict returned by extract_step_context()

        Returns:
            str: Formatted step name for PyATS reporting

        Examples:
            return f"Verify BGP peer {context['peer_ip']} on node {context['node']}"
            return f"Verify BD '{context['tenant']}/{context['bd']}' -> Subnet '{context['subnet']}'"
        """
        raise NotImplementedError("Subclasses must implement format_step_name()")

    def format_step_description(self, result: VerificationResult, context: Dict[str, Any]) -> str:
        """Format detailed step description with key verification details.

        Provides detailed information that will be logged for each step,
        including the verification context and any relevant metadata.

        Args:
            result: Full verification result dictionary
            context: Context dict returned by extract_step_context()

        Returns:
            str: Detailed description for logging and troubleshooting

        Examples:
            return f"Tenant: {context['tenant']}, L3Out: {context['l3out']}, Node: {context['node']}"
            return f"Tenant: {context['tenant']}, BD: {context['bd']}, Subnet: {context['subnet']}"
        """
        raise NotImplementedError("Subclasses must implement format_step_description()")

    def process_results_with_steps(self, results: List[VerificationResult], steps) -> None:
        """Generic result processor with customization through abstract methods.

        This method provides a standardized implementation of result processing
        that eliminates code duplication across test files. It handles:
        - Result categorization and summary logging
        - PyATS step creation with customizable formatting
        - HTML report collection integration
        - Overall test result determination

        Subclasses customize behavior by implementing the required methods:
        - get_test_type_name(): Provides test type for logging
        - extract_step_context(): Extracts relevant fields from results
        - format_step_name(): Creates PyATS step names
        - format_step_description(): Creates detailed descriptions
        - build_item_identifier_from_context(): Creates HTML report identifiers

        Note: These methods will raise NotImplementedError if not overridden by subclasses.
        Cannot use ABC due to metaclass conflict with aetest.Testcase.

        Args:
            results: List of verification result dictionaries
            steps: PyATS steps object for creating test step reports
        """
        # Categorize results for summary and decision making
        failed, skipped, passed = self.categorize_results(results)

        # Log standardized result summary using abstract method
        test_type = self.get_test_type_name()
        self.log_result_summary(test_type, failed, skipped, passed)

        # Log skipped items with customizable formatting
        if skipped:
            self.log_skipped_items(skipped)

        # Create PyATS steps for each result using abstract methods
        self.create_pyats_steps(results, steps)

        # Determine overall test result using existing helper
        self.determine_overall_test_result(failed, skipped, passed)

    def create_pyats_steps(self, results: List[VerificationResult], steps) -> None:
        """Create PyATS steps from results using abstract formatting methods.

        This method handles the generic step creation logic while delegating
        formatting decisions to abstract methods implemented by subclasses.

        Args:
            results: List of verification result dictionaries
            steps: PyATS steps object for creating test step reports
        """
        for result in results:
            if not isinstance(result, dict):
                self.logger.warning(f"Unexpected result format: {result}")
                continue

            try:
                # Use abstract methods for customization
                context = self.extract_step_context(result)
                step_name = self.format_step_name(context)

                with steps.start(step_name, continue_=True) as step:
                    # Add result to HTML collector using existing helpers
                    self.add_step_to_html_collector(result, context)

                    # Log step details for troubleshooting
                    if self.should_log_step_details(result):
                        description = self.format_step_description(result, context)
                        self.logger.info(description)
                        self.log_additional_step_details(result, context)

                    # Set PyATS step status
                    self.set_step_status(step, result)

            except Exception as e:
                self.logger.error(f"Error creating step for result: {e}", exc_info=True)
                # Create a generic failure step for this result
                with steps.start("Failed to process result", continue_=True) as step:
                    step.failed(f"Step creation failed: {str(e)}")

    def log_skipped_items(self, skipped_results: List[VerificationResult]) -> None:
        """Log skipped items with customizable formatting.

        Default implementation provides generic logging. Subclasses can override
        to provide domain-specific skip item formatting.

        Args:
            skipped_results: List of skipped verification results
        """
        test_type = self.get_test_type_name()
        self.logger.warning(f"{len(skipped_results)} {test_type} verifications skipped")

        # Log first few skipped items as examples
        for i, result in enumerate(skipped_results[:5]):  # Limit to first 5
            try:
                context = self.extract_step_context(result)
                reason = result.get("reason", "Unknown reason")
                self.logger.info(f"  - Skipped: {context} ({reason})")
            except Exception:
                self.logger.info(f"  - Skipped result: {result.get('reason', 'Unknown')}")

        if len(skipped_results) > 5:
            self.logger.info(f"  ... and {len(skipped_results) - 5} more")

    def should_log_step_details(self, result: VerificationResult) -> bool:
        """Determine whether to log detailed information for a step.

        Default implementation logs details for failed results only.
        Subclasses can override to customize when details are logged.

        Args:
            result: Verification result dictionary

        Returns:
            bool: True if step details should be logged
        """
        return result.get("status") == "FAILED"

    def log_additional_step_details(self, result: VerificationResult, context: Dict[str, Any]) -> None:
        """Log additional step-specific details.

        Default implementation does nothing. Subclasses can override to add
        custom logging for each step (e.g., API details, timing info).

        Args:
            result: Full verification result dictionary
            context: Context dict returned by extract_step_context()
        """
        pass  # Default: no additional logging

    def add_step_to_html_collector(self, result: VerificationResult, context: Dict[str, Any]) -> None:
        """Add step result to HTML report collector.

        Default implementation uses existing result collector methods.
        Subclasses can override for custom HTML report integration.

        Args:
            result: Full verification result dictionary
            context: Context dict returned by extract_step_context()
        """
        # Use existing standardized method for adding results
        # This assumes subclass has implemented proper item identification
        try:
            # Extract basic info for the standardized method
            status = result.get("status", "UNKNOWN")
            reason = result.get("reason", "")
            test_type = self.get_test_type_name()

            # Try to build item identifier from context
            item_identifier = self.build_item_identifier_from_context(result, context)

            # Use existing add_verification_result method
            self.add_verification_result(
                status=status,
                test_type=test_type.lower(),  # Convert to lowercase for consistency
                item_identifier=item_identifier,
                details=reason if reason else None,
                test_context=None  # Could be enhanced by subclasses
            )
        except Exception as e:
            self.logger.debug(f"Failed to add result to HTML collector: {e}")
            # Don't fail the test due to reporting issues

    def build_item_identifier_from_context(self, result: VerificationResult, context: Dict[str, Any]) -> str:
        """Build item identifier string from extracted context for HTML reporting.

        This method should create a concise, descriptive identifier that uniquely
        identifies the test item in HTML reports and logs. The identifier should
        be meaningful to network operators for troubleshooting.

        Args:
            result: Full verification result dictionary
            context: Context dict returned by extract_step_context()

        Returns:
            str: Item identifier for HTML reporting

        Examples:
            return f"{context['peer_ip']} on node {context['node']}"
            return f"BD '{context['tenant']}/{context['bd']}' -> Subnet '{context['subnet']}'"
            return f"RR {context['rr_node']} to Leaf {context['leaf_node']}"
        """
        raise NotImplementedError("Subclasses must implement build_item_identifier_from_context()")

    def set_step_status(self, step, result: VerificationResult) -> None:
        """Set PyATS step status based on verification result.

        Args:
            step: PyATS step object
            result: Verification result dictionary
        """
        status = result.get("status", "UNKNOWN")
        reason = result.get("reason", "Unknown reason")

        if status == "PASSED" or status == ResultStatus.PASSED:
            step.passed()
        elif status == "SKIPPED" or status == ResultStatus.SKIPPED:
            step.skipped(reason)
        elif status == "FAILED" or status == ResultStatus.FAILED:
            step.failed(reason)
        else:
            step.errored(f"Unknown status: {status}")  # Handle unexpected statuses

    @aetest.cleanup
    def cleanup(self) -> None:
        """Clean up test resources and save test results.

        This cleanup method is called after all test steps complete.
        It performs the following:
        1. Flushes and shuts down batching reporter (if enabled)
        2. Uninstalls step interceptors
        3. Saves collected results to JSON for report generation
        """
        # Clean up batching reporter if it was initialized
        if hasattr(self, "batching_reporter") and self.batching_reporter:
            try:
                # Flush any remaining messages
                self.logger.debug("Shutting down batching reporter...")
                shutdown_stats = self.batching_reporter.shutdown(timeout=5.0)

                self.logger.info(
                    "Batching reporter shutdown complete - processed %d messages in %d batches",
                    shutdown_stats.get("total_messages", 0),
                    shutdown_stats.get("total_batches", 0),
                )

                # Uninstall step interceptors
                if hasattr(self, "step_interceptor") and self.step_interceptor:
                    self.step_interceptor.uninstall_interceptors()

                    # Clear global references
                    interceptor_module.batching_reporter = None
                    interceptor_module.interception_enabled = False

            except Exception as e:
                self.logger.error("Error during batching reporter cleanup: %s", e)
                # Don't fail the test due to cleanup issues

        # Report controller recovery statistics
        if (
            hasattr(self, "_controller_recovery_count")
            and self._controller_recovery_count > 0
        ):
            self.logger.warning(
                f"📊 CONTROLLER RECOVERY SUMMARY: {self._controller_recovery_count} recovery event{'s' if self._controller_recovery_count > 1 else ''} "
                f"during test execution (total downtime: ~{self._total_recovery_downtime:.1f}s)"
            )

            # TODO: Add controller recovery statistics to HTML reports for operational analysis
            # This would track recovery patterns, downtime trends, and controller health metrics
            # in the HTML reports for post-test analysis and capacity planning. Benefits include:
            # - Historical recovery pattern analysis
            # - Controller performance trending
            # - Network reliability metrics for reporting
            # Currently commented out - needs testing to ensure proper integration with report generation
            #
            # if hasattr(self, "result_collector"):
            #     from nac_test.pyats_core.reporting.types import ResultStatus
            #     self.result_collector.add_result(
            #         ResultStatus.INFO,
            #         f"Controller experienced {self._controller_recovery_count} connectivity issue(s) "
            #         f"with total downtime of ~{self._total_recovery_downtime:.1f}s (all recovered successfully)"
            #     )

        # Save test results for HTML report generation
        if hasattr(self, "result_collector"):
            try:
                output_file = self.result_collector.save_to_file()
                self.logger.debug(f"Saved test results to: {output_file}")
            except Exception as e:
                self.logger.error(f"Failed to save test results: {e}")
                # Don't fail the test due to reporting issues
