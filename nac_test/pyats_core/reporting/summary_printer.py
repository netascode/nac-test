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

    def __init__(self):
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

        # Calculate combined statistics (matching original format exactly)
        # PyATS returns lowercase status values: 'passed', 'failed', 'skipped', 'errored'
        passed = sum(1 for t in all_test_status.values() if t.get("status") == "passed")
        failed = sum(1 for t in all_test_status.values() if t.get("status") == "failed")
        skipped = sum(
            1 for t in all_test_status.values() if t.get("status") == "skipped"
        )
        errored = sum(
            1 for t in all_test_status.values() if t.get("status") == "errored"
        )
        total = len(all_test_status)

        # Include errored tests in the failed count for the summary
        failed_total = failed + errored

        print("\n" + "=" * 80)
        if errored > 0:
            # If we have errored tests, show them separately
            print(
                f"{total} tests, {passed} passed, {failed} failed, {errored} errored, {skipped} skipped."
            )
        else:
            # Otherwise show combined failed count
            print(
                f"{total} tests, {passed} passed, {failed_total} failed, {skipped} skipped."
            )
        print("=" * 80)

        # Print archive paths if output_dir is provided
        if output_dir:
            self.print_archive_info(output_dir)

        # Color the timing information
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
