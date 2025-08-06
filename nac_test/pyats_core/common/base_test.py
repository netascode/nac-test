# -*- coding: utf-8 -*-

"""Generic base test class for all architectures."""

from pyats import aetest
import os
import sys
import yaml
import logging
from pathlib import Path
from typing import Any, Dict, TypeVar, Callable, Awaitable, Optional
from functools import lru_cache
from datetime import datetime
from contextlib import contextmanager

from nac_test.pyats_core.common.connection_pool import ConnectionPool
from nac_test.pyats_core.common.retry_strategy import SmartRetry
from nac_test.pyats_core.reporting.collector import TestResultCollector
import markdown

T = TypeVar("T")


class NACTestBase(aetest.Testcase):
    """Generic base class with common functionality for all architectures.

    This enhanced base class provides:
    - Common setup for all test architectures
    - HTML reporting support with pre-rendered metadata
    - Result collection during test execution
    - Connection pooling and retry logic (HTTP/API)
    - SSH command execution and tracking (SSH/Device)
    """

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
        md = markdown.Markdown(
            extensions=[
                "extra",  # Includes tables, footnotes, abbreviations, etc.
                "nl2br",  # Converts newlines to <br> tags
                "sane_lists",  # Better list handling
            ]
        )

        # Convert markdown to HTML
        html = md.convert(text)

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

    def _initialize_result_collector(self) -> None:
        """Initialize the result collector for this test.

        Sets up the TestResultCollector with a unique test ID and
        attaches pre-rendered metadata for efficient report generation.
        """
        # Get output directory from DATA_FILE path (already set by orchestrator)
        data_file = Path(os.environ.get("DATA_FILE", ""))
        output_dir = data_file.parent if data_file else Path(".")

        # Create html_report_data subdirectory inside pyats_results/html_reports
        # Note: pyats_results doesn't exist yet during test execution, so we use a temp location
        # The orchestrator will move these files to the correct location after extraction
        html_report_data_dir = output_dir / "html_report_data_temp"
        html_report_data_dir.mkdir(exist_ok=True)

        # Generate unique test ID
        test_id = self._generate_test_id()
        self.result_collector = TestResultCollector(test_id, html_report_data_dir)

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
        data_file = Path(os.environ.get("DATA_FILE", "merged_data_model.yaml"))
        with open(data_file, "r") as f:
            data = yaml.safe_load(f)
            # Ensure we always return a dict
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

        async def tracked_get(url, *args, **kwargs):
            """Tracked GET method"""
            response = await original_get(url, *args, **kwargs)
            test_instance._track_api_response("GET", url, response, device_name)
            return response

        async def tracked_post(url, *args, **kwargs):
            """Tracked POST method"""
            response = await original_post(url, *args, **kwargs)
            test_instance._track_api_response(
                "POST",
                url,
                response,
                device_name,
                kwargs.get("json", kwargs.get("data")),
            )
            return response

        async def tracked_put(url, *args, **kwargs):
            """Tracked PUT method"""
            response = await original_put(url, *args, **kwargs)
            test_instance._track_api_response(
                "PUT",
                url,
                response,
                device_name,
                kwargs.get("json", kwargs.get("data")),
            )
            return response

        async def tracked_delete(url, *args, **kwargs):
            """Tracked DELETE method"""
            response = await original_delete(url, *args, **kwargs)
            test_instance._track_api_response("DELETE", url, response, device_name)
            return response

        async def tracked_patch(url, *args, **kwargs):
            """Tracked PATCH method"""
            response = await original_patch(url, *args, **kwargs)
            test_instance._track_api_response(
                "PATCH",
                url,
                response,
                device_name,
                kwargs.get("json", kwargs.get("data")),
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
        request_data: Optional[Dict] = None,
    ) -> None:
        """Track an API response in the result collector.

        Args:
            method: HTTP method used (GET, POST, etc.)
            url: The URL that was called
            response: The httpx response object
            device_name: Name of the device/controller
            request_data: Optional request payload for POST/PUT/PATCH
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

            # Try to parse JSON response if successful
            parsed_data = None
            if response.status_code == 200:
                try:
                    parsed_data = response.json()
                except Exception:
                    # Not JSON or parsing failed
                    parsed_data = None

            # Add request data to parsed_data if available
            if request_data:
                parsed_data = {"request": request_data, "response": parsed_data}

            # Get current test context if available
            test_context = getattr(self, "_current_test_context", None)

            # Use the unified tracking method
            self.result_collector.add_command_api_execution(
                device_name=device_name,
                command=command,
                output=response_text,
                data=parsed_data,
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
    def test_context(self, context: str):
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

    @aetest.cleanup
    def cleanup(self) -> None:
        """Save test results to file for report generation.

        This cleanup method is called after all test steps complete.
        It saves the collected results to a JSON file for later HTML
        report generation by the orchestrator.
        """
        if hasattr(self, "result_collector"):
            try:
                output_file = self.result_collector.save_to_file()
                self.logger.debug(f"Saved test results to: {output_file}")
            except Exception as e:
                self.logger.error(f"Failed to save test results: {e}")
                # Don't fail the test due to reporting issues
