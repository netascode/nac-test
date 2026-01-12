# -*- coding: utf-8 -*-

"""Summary and archive information printing for PyATS test execution."""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from nac_test.utils.terminal import terminal
from nac_test.pyats_core.reporting.utils.archive_inspector import ArchiveInspector

logger = logging.getLogger(__name__)


class SummaryPrinter:
    """Handles printing of test execution summaries and archive information."""

    def __init__(self) -> None:
        """Initialize the SummaryPrinter."""
        pass  # No dependencies needed currently

    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format duration like Robot Framework does.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string (e.g., "1 minute 23.456 seconds")
        """
        if seconds < 60:
            return f"{seconds:.2f} seconds"
        else:
            minutes = int(seconds / 60)
            secs = seconds % 60
            return f"{minutes} minutes {secs:.2f} seconds"

    def _format_test_line(
        self,
        total: int,
        passed: int,
        failed: int,
        errored: int,
        skipped: int,
        prefix: Optional[str] = None,
    ) -> str:
        """Format a single test summary line with optional prefix.

        Formats test statistics into a human-readable summary line. If errored
        count is greater than 0, it's shown separately. Otherwise, errored tests
        are combined with failed tests in the output.

        Args:
            total: Total number of tests
            passed: Number of passed tests
            failed: Number of failed tests
            errored: Number of errored tests
            skipped: Number of skipped tests
            prefix: Optional prefix string to add before the summary line

        Returns:
            Formatted summary string containing test statistics
        """
        # Build the prefix if provided
        prefix_str = f"{prefix} " if prefix else ""

        # Include errored tests in the failed count for display
        failed_total = failed + errored

        if errored > 0:
            # If we have errored tests, show them separately
            return (
                f"{prefix_str}{total} tests, {passed} passed, "
                f"{failed} failed, {errored} errored, {skipped} skipped."
            )
        else:
            # Otherwise show combined failed count
            return (
                f"{prefix_str}{total} tests, {passed} passed, "
                f"{failed_total} failed, {skipped} skipped."
            )

    def _calculate_test_stats(
        self, test_status: Dict[str, Any]
    ) -> tuple[int, int, int, int, int]:
        """Calculate test statistics from status dictionary.

        Processes a test status dictionary to count tests by their status.
        PyATS returns lowercase status values: 'passed', 'failed', 'skipped', 'errored'.

        Args:
            test_status: Dictionary mapping test names to test result dictionaries.
                Each test result should contain a 'status' key with one of the
                following values: 'passed', 'failed', 'skipped', 'errored'.

        Returns:
            A tuple containing:
                - total: Total number of tests
                - passed: Number of passed tests
                - failed: Number of failed tests
                - errored: Number of errored tests
                - skipped: Number of skipped tests
        """
        # PyATS returns lowercase status values: 'passed', 'failed', 'skipped', 'errored'
        passed = sum(1 for t in test_status.values() if t.get("status") == "passed")
        failed = sum(1 for t in test_status.values() if t.get("status") == "failed")
        skipped = sum(1 for t in test_status.values() if t.get("status") == "skipped")
        errored = sum(1 for t in test_status.values() if t.get("status") == "errored")
        total = len(test_status)

        return total, passed, failed, errored, skipped

    def print_summary(
        self,
        test_status: Dict[str, Any],
        start_time: datetime,
        output_dir: Optional[Path] = None,
        archive_path: Optional[Path] = None,
        api_test_status: Optional[Dict[str, Any]] = None,
        d2d_test_status: Optional[Dict[str, Any]] = None,
        overall_start_time: Optional[datetime] = None,
    ) -> None:
        """Print execution summary matching Robot format.

        Args:
            test_status: Combined test status dictionary
            start_time: When the test run started
            output_dir: Optional output directory for archive info
            archive_path: Optional path to the archive (kept for compatibility)
            api_test_status: Optional API test results
            d2d_test_status: Optional D2D test results
            overall_start_time: Overall start time for combined runs
        """
        # Delegate to print_summary_with_breakdown if both API and D2D test statuses are provided
        # This encapsulates the presentation decision within SummaryPrinter, maintaining clean
        # separation of concerns so the orchestrator doesn't need to know which method to call
        if api_test_status and d2d_test_status:
            self.print_summary_with_breakdown(
                api_test_status=api_test_status,
                d2d_test_status=d2d_test_status,
                start_time=start_time,
                overall_start_time=overall_start_time,
                output_dir=output_dir,
            )
            return

        # Use overall_start_time if available (for combined runs), otherwise use start_time
        actual_start_time = overall_start_time if overall_start_time else start_time
        wall_time = (datetime.now() - actual_start_time).total_seconds()

        # Combine test status from both API and D2D if available
        all_test_status = {}

        # Add API test results if available
        if api_test_status:
            all_test_status.update(api_test_status)

        # Add D2D test results if available
        if d2d_test_status:
            all_test_status.update(d2d_test_status)

        # Fall back to test_status if no separate tracking (backward compatibility)
        if not all_test_status:
            all_test_status = test_status

        # Calculate total test time (sum of all individual test durations)
        total_test_time = sum(
            test.get("duration", 0)
            for test in all_test_status.values()
            if "duration" in test
        )

        # Calculate statistics using helper method
        total, passed, failed, errored, skipped = self._calculate_test_stats(
            all_test_status
        )

        # Format and print summary line using helper method
        print("\n" + "=" * 80)
        print(self._format_test_line(total, passed, failed, errored, skipped))
        print("=" * 80)

        # Print archive paths if output_dir is provided
        if output_dir:
            self.print_archive_info(output_dir)

        # Color the timing information
        print(
            f"\n{terminal.info('Total testing:')} {self.format_duration(total_test_time)}"
        )
        print(f"{terminal.info('Elapsed time:')}  {self.format_duration(wall_time)}")

    def print_summary_with_breakdown(
        self,
        api_test_status: Dict[str, Any],
        d2d_test_status: Dict[str, Any],
        start_time: datetime,
        overall_start_time: Optional[datetime] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        """Print test execution summary with separate API and D2D breakdowns.

        This method provides a detailed breakdown of test results, showing
        API and D2D test statistics separately before presenting the combined
        totals. It calculates wall time from the overall start time (if provided)
        or from the start time, displays test statistics for each category,
        and optionally shows archive information.

        Args:
            api_test_status: Dictionary containing API test results. Each key is
                a test name and each value is a dictionary with 'status' and
                optionally 'duration' keys.
            d2d_test_status: Dictionary containing D2D test results. Each key is
                a test name and each value is a dictionary with 'status' and
                optionally 'duration' keys.
            start_time: The datetime when the tests started execution.
            overall_start_time: Optional overall start time for more accurate
                elapsed time calculation. If not provided, start_time is used.
            output_dir: Optional path to the output directory for displaying
                archive information. If provided, archive paths will be printed.

        Returns:
            None

        Example:
            >>> printer = SummaryPrinter()
            >>> api_results = {
            ...     "test_api_1": {"status": "passed", "duration": 1.5},
            ...     "test_api_2": {"status": "failed", "duration": 2.0}
            ... }
            >>> d2d_results = {
            ...     "test_d2d_1": {"status": "passed", "duration": 3.0},
            ...     "test_d2d_2": {"status": "skipped", "duration": 0.0}
            ... }
            >>> printer.print_summary_with_breakdown(
            ...     api_results, d2d_results, datetime.now()
            ... )
        """
        # Calculate wall time from overall_start_time or start_time
        actual_start_time = overall_start_time if overall_start_time else start_time
        wall_time = (datetime.now() - actual_start_time).total_seconds()

        # Calculate statistics for API tests
        api_total, api_passed, api_failed, api_errored, api_skipped = (
            self._calculate_test_stats(api_test_status)
        )

        # Calculate statistics for D2D tests
        d2d_total, d2d_passed, d2d_failed, d2d_errored, d2d_skipped = (
            self._calculate_test_stats(d2d_test_status)
        )

        # Combine both dictionaries for combined statistics
        combined_test_status = {}
        combined_test_status.update(api_test_status)
        combined_test_status.update(d2d_test_status)

        # Calculate combined statistics
        (
            combined_total,
            combined_passed,
            combined_failed,
            combined_errored,
            combined_skipped,
        ) = self._calculate_test_stats(combined_test_status)

        # Calculate total test time (sum of all individual test durations)
        total_test_time = sum(
            test.get("duration", 0)
            for test in combined_test_status.values()
            if "duration" in test
        )

        # Print the breakdown with clear separation
        print("\n" + "=" * 80)
        print("Test Execution Summary")
        print("=" * 80)

        # Format and print API test line
        api_line = self._format_test_line(
            api_total,
            api_passed,
            api_failed,
            api_errored,
            api_skipped,
            prefix="API Tests:",
        )
        print(api_line)

        # Format and print D2D test line
        d2d_line = self._format_test_line(
            d2d_total,
            d2d_passed,
            d2d_failed,
            d2d_errored,
            d2d_skipped,
            prefix="D2D Tests:",
        )
        print(d2d_line)

        print("-" * 80)

        # Format and print combined line
        combined_line = self._format_test_line(
            combined_total,
            combined_passed,
            combined_failed,
            combined_errored,
            combined_skipped,
            prefix="Combined:",
        )
        print(combined_line)

        print("=" * 80)

        # Print archive info if output_dir provided
        if output_dir:
            self.print_archive_info(output_dir)

        # Print timing information at the end
        print(
            f"\n{terminal.info('Total testing:')} {self.format_duration(total_test_time)}"
        )
        print(f"{terminal.info('Elapsed time:')}  {self.format_duration(wall_time)}")

    def print_archive_info(self, output_dir: Path) -> None:
        """Print information about generated archives and their contents.

        Args:
            output_dir: Directory containing the archives
        """
        print(f"\n{terminal.info('PyATS Output Files:')}")
        print("=" * 80)

        # Use ArchiveInspector to find all archives
        archives = ArchiveInspector.find_archives(output_dir)

        displayed_any = False

        # Display API results if available
        if archives["api"]:
            archive_path = archives["api"][0]
            results_dir = output_dir / "pyats_results" / "api"

            # Print standard PyATS output files
            results_json = results_dir / "results.json"
            results_xml = results_dir / "ResultsDetails.xml"
            summary_xml = results_dir / "ResultsSummary.xml"

            if results_json.exists():
                print(f"Results JSON:    {results_json}")
            if results_xml.exists():
                print(f"Results XML:     {results_xml}")
            if summary_xml.exists():
                print(f"Summary XML:     {summary_xml}")

            # Find and print report file
            for report_file in results_dir.glob("*.report"):
                print(f"Report:          {report_file}")
                break

            print(f"Archive:         {archive_path}")
            displayed_any = True

        # Display D2D results if available
        if archives["d2d"]:
            if displayed_any:
                print()  # Add spacing between sections

            archive_path = archives["d2d"][0]
            results_dir = output_dir / "pyats_results" / "d2d"

            # Print standard PyATS output files
            results_json = results_dir / "results.json"
            results_xml = results_dir / "ResultsDetails.xml"
            summary_xml = results_dir / "ResultsSummary.xml"

            if results_json.exists():
                print(f"Results JSON:    {results_json}")
            if results_xml.exists():
                print(f"Results XML:     {results_xml}")
            if summary_xml.exists():
                print(f"Summary XML:     {summary_xml}")

            # Find and print report file
            for report_file in results_dir.glob("*.report"):
                print(f"Report:          {report_file}")
                break

            print(f"Archive:         {archive_path}")
            displayed_any = True

        # Display legacy results if no typed archives
        if archives["legacy"] and not (archives["api"] or archives["d2d"]):
            archive_path = archives["legacy"][0]
            results_dir = output_dir / "pyats_results"

            # Print standard PyATS output files
            results_json = results_dir / "results.json"
            results_xml = results_dir / "ResultsDetails.xml"
            summary_xml = results_dir / "ResultsSummary.xml"

            if results_json.exists():
                print(f"Results JSON:    {results_json}")
            if results_xml.exists():
                print(f"Results XML:     {results_xml}")
            if summary_xml.exists():
                print(f"Summary XML:     {summary_xml}")

            # Find and print report file
            for report_file in results_dir.glob("*.report"):
                print(f"Report:          {report_file}")
                break

            print(f"Archive:         {archive_path}")
            displayed_any = True

        if not displayed_any:
            print("No PyATS archives found.")
