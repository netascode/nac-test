# -*- coding: utf-8 -*-

"""Generic base test class for all architectures."""

from pyats import aetest
import os
import sys
import yaml
import logging
from pathlib import Path
from typing import Any, Dict, TypeVar, Callable, Awaitable
from functools import lru_cache
from datetime import datetime

from nac_test.pyats.common.connection_pool import ConnectionPool
from nac_test.pyats.common.retry_strategy import SmartRetry
from nac_test.pyats.reporting.collector import TestResultCollector
import markdown

T = TypeVar("T")


class NACTestBase(aetest.Testcase):
    """Generic base class with common functionality for all architectures.
    
    This enhanced base class provides:
    - Common setup for all test architectures
    - HTML reporting support with pre-rendered metadata
    - Result collection during test execution
    - Connection pooling and retry logic
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
            "title": getattr(module, 'TITLE', cls.__name__),
            "description_html": cls._render_html(getattr(module, 'DESCRIPTION', '')),
            "setup_html": cls._render_html(getattr(module, 'SETUP', '')),
            "procedure_html": cls._render_html(getattr(module, 'PROCEDURE', '')),
            "criteria_html": cls._render_html(getattr(module, 'PASS_FAIL_CRITERIA', ''))
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
            return ''
        
        
        # Configure markdown with useful extensions
        md = markdown.Markdown(extensions=[
            'extra',  # Includes tables, footnotes, abbreviations, etc.
            'nl2br',  # Converts newlines to <br> tags
            'sane_lists',  # Better list handling
        ])
        
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

        # Connection pool is shared within process
        self.pool = ConnectionPool()
        
        # Initialize result collector for HTML reporting
        self._initialize_result_collector()

    def _initialize_result_collector(self) -> None:
        """Initialize the result collector for this test.
        
        Sets up the TestResultCollector with a unique test ID and
        attaches pre-rendered metadata for efficient report generation.
        """
        # Get output directory from DATA_FILE path (already set by orchestrator)
        data_file = Path(os.environ.get('DATA_FILE', ''))
        output_dir = data_file.parent if data_file else Path('.')
        
        # Create html_report_data subdirectory inside pyats_results/html_reports
        # Note: pyats_results doesn't exist yet during test execution, so we use a temp location
        # The orchestrator will move these files to the correct location after extraction
        html_report_data_dir = output_dir / 'html_report_data_temp'
        html_report_data_dir.mkdir(exist_ok=True)
        
        # Generate unique test ID
        test_id = self._generate_test_id()
        self.result_collector = TestResultCollector(test_id, html_report_data_dir)
        
        # Attach pre-rendered metadata to collector
        metadata = self.get_rendered_metadata()
        
        # Add jobfile path to metadata
        module = sys.modules[self.__class__.__module__]
        if hasattr(module, '__file__') and module.__file__:
            # Get relative path from project root if possible
            try:
                jobfile_path = Path(module.__file__)
                # Try to make it relative to common parent paths
                for parent in ['tests/', 'templates/', 'pyats/']:
                    if parent in str(jobfile_path):
                        parts = str(jobfile_path).split(parent)
                        if len(parts) > 1:
                            metadata['jobfile_path'] = parent + parts[1]
                            break
                else:
                    # Fallback to just the filename if no common parent found
                    metadata['jobfile_path'] = jobfile_path.name
            except Exception:
                metadata['jobfile_path'] = 'unknown'
        else:
            metadata['jobfile_path'] = 'unknown'
        
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
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Millisecond precision
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

    @aetest.cleanup
    def cleanup(self) -> None:
        """Save test results to file for report generation.
        
        This cleanup method is called after all test steps complete.
        It saves the collected results to a JSON file for later HTML
        report generation by the orchestrator.
        """
        if hasattr(self, 'result_collector'):
            try:
                output_file = self.result_collector.save_to_file()
                self.logger.debug(f"Saved test results to: {output_file}")
            except Exception as e:
                self.logger.error(f"Failed to save test results: {e}")
                # Don't fail the test due to reporting issues
