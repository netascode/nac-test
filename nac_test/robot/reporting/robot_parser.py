# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Robot Framework result parser using ResultVisitor API.

This module parses Robot Framework's output.xml files to extract test statistics
and individual test results for report generation.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from robot.api import ExecutionResult
from robot.result import ResultVisitor

logger = logging.getLogger(__name__)


class TestDataCollector(ResultVisitor):
    """Visitor that collects test data from Robot Framework results.

    This class implements Robot Framework's ResultVisitor pattern to traverse
    the test result tree and collect individual test data and statistics.

    Attributes:
        tests: List of test result dictionaries
        stats: Dictionary with aggregated statistics
    """

    def __init__(self) -> None:
        """Initialize the collector with empty data structures."""
        self.tests: list[dict[str, Any]] = []
        self.stats = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "success_rate": 0.0,
        }

    def visit_test(self, test: Any) -> None:
        """Called for each test case in the result tree.

        Extracts test data including name, status, duration, timestamps, and
        generates a test_id for deep linking.

        Args:
            test: Robot Framework test object
        """
        # Map Robot status to our convention
        status_map = {"PASS": "PASS", "FAIL": "FAIL", "SKIP": "SKIP", "NOT RUN": "SKIP"}
        status = status_map.get(test.status, "FAIL")

        # Calculate duration in seconds
        duration_seconds = test.elapsedtime / 1000.0 if test.elapsedtime else 0.0

        # Parse start time
        start_time = self._parse_timestamp(test.starttime) if test.starttime else None
        start_time_str = start_time.isoformat() if start_time else ""

        # Get parent suite name
        suite_name = test.parent.name if test.parent else "Unknown Suite"

        # Collect test data
        test_data = {
            "name": test.name,
            "status": status,
            "duration": duration_seconds,
            "start_time": start_time_str,
            "message": test.message.strip() if test.message else "",
            "test_id": test.id,  # e.g., 's1-s2-t3' for suite1.suite2.test3
            "suite_name": suite_name,
        }

        self.tests.append(test_data)

        # Update statistics
        self.stats["total_tests"] += 1
        if status == "PASS":
            self.stats["passed_tests"] += 1
        elif status == "FAIL":
            self.stats["failed_tests"] += 1
        elif status == "SKIP":
            self.stats["skipped_tests"] += 1

    def end_suite(self, suite: Any) -> None:
        """Called when suite ends - calculate final statistics.

        We calculate success rate at the root suite level (when parent is None).
        Also sort tests to put failed tests first.

        Args:
            suite: Robot Framework suite object
        """
        if suite.parent is None:
            # This is the root suite - finalize statistics
            total = self.stats["total_tests"]
            skipped = self.stats["skipped_tests"]
            passed = self.stats["passed_tests"]

            tests_with_results = total - skipped
            if tests_with_results > 0:
                self.stats["success_rate"] = (passed / tests_with_results) * 100

            # Sort tests: failed first, then by name
            self.tests.sort(key=lambda t: (t["status"] != "FAIL", t["name"]))

            logger.debug(
                f"Collected {total} tests: {passed} passed, "
                f"{self.stats['failed_tests']} failed, {skipped} skipped"
            )

    @staticmethod
    def _parse_timestamp(timestamp_str: str) -> datetime | None:
        """Parse Robot Framework timestamp format.

        Robot Framework uses format: '20250131 12:34:56.789' or '20250131 12:34:56'

        Args:
            timestamp_str: Timestamp string from Robot Framework

        Returns:
            datetime object or None if parsing fails
        """
        if not timestamp_str:
            return None
        try:
            # Try with milliseconds first
            return datetime.strptime(timestamp_str, "%Y%m%d %H:%M:%S.%f")
        except ValueError:
            try:
                # Try without milliseconds
                return datetime.strptime(timestamp_str, "%Y%m%d %H:%M:%S")
            except ValueError:
                logger.warning(f"Failed to parse timestamp: {timestamp_str}")
                return None


class RobotResultParser:
    """Parser for Robot Framework output.xml files.

    Uses Robot Framework's ExecutionResult API with a custom ResultVisitor
    to extract test statistics and individual test results.

    Example:
        >>> parser = RobotResultParser(Path("output.xml"))
        >>> data = parser.parse()
        >>> print(data["aggregated_stats"])
        {'total_tests': 100, 'passed_tests': 97, 'failed_tests': 3, ...}
    """

    def __init__(self, output_xml_path: Path):
        """Initialize parser with path to output.xml.

        Args:
            output_xml_path: Path to Robot Framework's output.xml file
        """
        self.output_xml_path = output_xml_path

    def parse(self) -> dict[str, Any]:
        """Parse output.xml and extract all data.

        Returns:
            Dictionary containing:
                - aggregated_stats: Overall statistics dict with keys:
                    - total_tests, passed_tests, failed_tests, skipped_tests, success_rate
                - tests: List of individual test result dicts with keys:
                    - name, status, duration, start_time, message, test_id, suite_name

        Raises:
            FileNotFoundError: If output.xml doesn't exist
            Exception: If parsing fails
        """
        if not self.output_xml_path.exists():
            raise FileNotFoundError(f"output.xml not found: {self.output_xml_path}")

        try:
            # Use Robot Framework's ExecutionResult API
            logger.info(f"Parsing Robot results from {self.output_xml_path}")
            result = ExecutionResult(str(self.output_xml_path))

            # Visit the result tree with our custom collector
            collector = TestDataCollector()
            result.visit(collector)

            logger.info(
                f"Parsed {collector.stats['total_tests']} tests "
                f"({collector.stats['passed_tests']} passed, "
                f"{collector.stats['failed_tests']} failed, "
                f"{collector.stats['skipped_tests']} skipped)"
            )

            return {
                "aggregated_stats": collector.stats,
                "tests": collector.tests,
            }

        except Exception as e:
            logger.error(f"Failed to parse {self.output_xml_path}: {e}")
            raise
