# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Async HTML report generator for nac-test PyATS framework.

This module provides asynchronous report generation capabilities that are
10x faster than synchronous generation through parallel I/O operations.

Adapted from BRKXAR-2032-test-automation with significant improvements:
- Async I/O for parallel report generation
- Pre-rendered HTML metadata (no markdown conversion)
- Robust error handling for individual failures
- Memory-efficient output truncation
- Debug mode support

Environment Variables:
    PYATS_DEBUG: If set, keeps JSON result files and may enable verbose output
    KEEP_HTML_REPORT_DATA: If set, keeps JSON result files without debug verbosity
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles  # type: ignore[import-untyped]

from nac_test.pyats_core.reporting.templates import get_jinja_environment
from nac_test.pyats_core.reporting.types import ResultStatus

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Async HTML report generator with robust error handling.

    This class generates HTML reports from test results collected during
    PyATS test execution. It uses async I/O for parallel processing of
    multiple test results, significantly improving performance for large
    test suites.

    Attributes:
        output_dir: Base output directory containing test results
        report_dir: Directory where HTML reports will be generated
        test_results_dir: Directory containing JSON test result files
        max_concurrent: Maximum number of concurrent report generations
        failed_reports: List of report paths that failed to generate
    """

    def __init__(
        self,
        output_dir: Path,
        pyats_results_dir: Path,
        max_concurrent: int = 10,
        minimal_reports: bool = False,
        archive_type: str | None = None,
    ) -> None:
        """Initialize the report generator.

        Args:
            output_dir: Base output directory containing test results
            pyats_results_dir: Directory where PyATS results are extracted
            max_concurrent: Maximum number of concurrent report generations.
                           Defaults to 10.
            minimal_reports: Only include command outputs for failed/errored tests
            archive_type: Type of archive being processed ("api" or "d2d")
        """
        self.output_dir = output_dir
        self.pyats_results_dir = pyats_results_dir
        self.report_dir = pyats_results_dir / "html_reports"
        self.report_dir.mkdir(exist_ok=True)
        self.html_report_data_dir = self.report_dir / "html_report_data"
        self.html_report_data_dir.mkdir(exist_ok=True)
        # Temporary location where tests write their JSON files
        self.temp_data_dir = output_dir / "html_report_data_temp"
        self.max_concurrent = max_concurrent
        self.minimal_reports = minimal_reports
        self.archive_type = archive_type
        self.failed_reports: list[str] = []

        # Initialize Jinja2 environment using our templates module
        from nac_test.pyats_core.reporting.templates import TEMPLATES_DIR

        self.env = get_jinja_environment(TEMPLATES_DIR)

    async def generate_all_reports(self) -> dict[str, Any]:
        """Generate all reports with parallelization and error handling.

        This method finds all test result JSON files and generates HTML
        reports for each one in parallel. It also generates a summary
        report and optionally cleans up the JSON files.

        Returns:
            Dictionary containing:
                - status: "success" or "no_results"
                - duration: Total generation time in seconds
                - total_tests: Number of test results found
                - successful_reports: Number of successfully generated reports
                - failed_reports: Number of failed report generations
                - summary_report: Path to the summary report (if generated)
        """
        start_time = datetime.now()

        # Move files from temp location to final location
        if self.temp_data_dir.exists():
            # Debug the number of jsonl files in the temp directory
            logger.debug(
                f"Found {len(list(self.temp_data_dir.glob('*.jsonl')))} jsonl files in the temp directory"
            )
            for jsonl_file in self.temp_data_dir.glob("*.jsonl"):
                jsonl_file.rename(self.html_report_data_dir / jsonl_file.name)
            # Clean up temp directory
            self.temp_data_dir.rmdir()
        else:
            logger.warning("No temp data directory found at %s", self.temp_data_dir)

        # Find all test result files in html_report_data directory
        result_files = list(self.html_report_data_dir.glob("*.jsonl"))

        if not result_files:
            logger.warning("No test results found to generate reports")
            return {"status": "no_results", "duration": 0}

        logger.info(f"Found {len(result_files)} test results to process")

        # Generate reports concurrently with semaphore control
        semaphore = asyncio.Semaphore(self.max_concurrent)
        tasks = [self._generate_report_safe(file, semaphore) for file in result_files]

        report_paths = await asyncio.gather(*tasks)
        successful_reports = [p for p in report_paths if p is not None]

        logger.info(f"Successfully generated {len(successful_reports)} reports")

        # Generate summary report
        summary_path = await self._generate_summary_report(
            successful_reports, result_files
        )

        # Note: JSONL cleanup is handled by the caller (MultiArchiveReportGenerator)
        # after stats collection to ensure data is available for metrics.

        duration = (datetime.now() - start_time).total_seconds()

        return {
            "status": "success",
            "duration": duration,
            "total_tests": len(result_files),
            "successful_reports": len(successful_reports),
            "failed_reports": len(self.failed_reports),
            "summary_report": str(summary_path) if summary_path else None,
        }

    async def _read_jsonl_results(self, jsonl_path: Path) -> dict[str, Any]:
        """Read JSONL file asynchronously with robust error handling.

        Reads a streaming JSONL file produced by TestResultCollector and reconstructs
        the expected data structure for HTML template generation.

        Args:
            jsonl_path: Path to the JSONL result file.

        Returns:
            Dictionary containing test data in expected format for templates.

        Raises:
            Exception: If file cannot be read or is completely malformed.
        """
        results = []
        command_executions = []
        metadata = {}
        summary = {}

        try:
            async with aiofiles.open(jsonl_path) as f:
                async for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        record = json.loads(line)
                        record_type = record.get("type")

                        if record_type == "metadata":
                            metadata = record
                        elif record_type == "result":
                            results.append(record)
                        elif record_type == "command_execution":
                            command_executions.append(record)
                        elif record_type == "summary":
                            summary = record
                        elif record_type == "emergency_close":
                            # Log but continue processing - emergency close indicates crash recovery
                            logger.debug(
                                f"Found emergency close record in {jsonl_path}"
                            )

                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Skipping malformed JSONL line in {jsonl_path}: {e}"
                        )
                        continue

        except Exception as e:
            logger.error(f"Failed to read JSONL file {jsonl_path}: {e}")
            raise

        # Filter command executions if minimal_reports is enabled and test passed
        # Only include commands for failed or errored tests
        overall_status = summary.get("overall_status")
        if self.minimal_reports and overall_status not in ["failed", "errored"]:
            # Clear command executions for passed/skipped tests to save space
            command_count = len(command_executions)
            command_executions = []
            logger.debug(
                f"Minimal reports mode: Excluded {command_count} command executions for {overall_status} test"
            )

        # Return in expected format for existing templates
        return {
            "test_id": metadata.get("test_id") or summary.get("test_id"),
            "start_time": metadata.get("start_time") or summary.get("start_time"),
            "end_time": summary.get("end_time"),
            "duration": summary.get("duration"),
            "results": results,
            "command_executions": command_executions,
            "overall_status": overall_status,
            "metadata": summary.get("metadata", {}),
        }

    async def _generate_report_safe(
        self, result_file: Path, semaphore: asyncio.Semaphore
    ) -> Path | None:
        """Generate a single report with error handling.

        This method wraps the actual report generation with error handling
        to ensure that a single failure doesn't stop the entire process.

        Args:
            result_file: Path to the JSON result file
            semaphore: Semaphore for controlling concurrency

        Returns:
            Path to the generated report, or None if generation failed
        """
        async with semaphore:
            try:
                return await self._generate_single_report(result_file)
            except Exception as e:
                logger.error(f"Failed to generate report for {result_file}: {e}")
                self.failed_reports.append(str(result_file))
                return None

    async def _generate_single_report(self, result_file: Path) -> Path:
        """Generate a single test report asynchronously.

        Reads a JSONL test result file and generates an HTML report using
        the test_case template. Command outputs are truncated for display.

        Args:
            result_file: Path to the JSONL result file

        Returns:
            Path to the generated HTML report
        """
        # Read test results from JSONL format
        test_data = await self._read_jsonl_results(result_file)

        # Get metadata (now included in the same file)
        metadata = test_data.get("metadata", {})

        # Truncate command outputs for HTML display
        for execution in test_data.get("command_executions", []):
            execution["output"] = self._truncate_output(execution["output"])

        # Use pre-rendered HTML from metadata
        template = self.env.get_template("test_case/report.html.j2")
        html_content = template.render(
            title=metadata.get("title", test_data["test_id"]),
            description_html=metadata.get("description_html", ""),
            setup_html=metadata.get("setup_html", ""),
            procedure_html=metadata.get("procedure_html", ""),
            criteria_html=metadata.get("criteria_html", ""),
            results=test_data.get("results", []),
            command_executions=test_data.get("command_executions", []),
            status=test_data.get("overall_status", "unknown"),
            generation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            jobfile_path=metadata.get("jobfile_path", ""),
            hostname=metadata.get("hostname"),  # Device name for D2D tests
        )

        # Write HTML report
        report_path = self.report_dir / f"{test_data['test_id']}.html"
        async with aiofiles.open(report_path, "w") as f:
            await f.write(html_content)

        logger.debug(f"Generated report: {report_path}")
        return report_path

    def _truncate_output(self, output: str, max_lines: int = 1000) -> str:
        """Truncate output with a note.

        Truncates long command outputs to prevent HTML reports from
        becoming too large. A note is added indicating how many lines
        were omitted.

        Args:
            output: The output string to truncate
            max_lines: Maximum number of lines to keep. Defaults to 1000.

        Returns:
            Truncated output string with omission note if truncated
        """
        lines = output.split("\n")
        if len(lines) <= max_lines:
            return output

        return (
            "\n".join(lines[:max_lines])
            + f"\n\n... truncated ({len(lines) - max_lines} lines omitted) ..."
        )

    async def _generate_summary_report(
        self, report_paths: list[Path], result_files: list[Path]
    ) -> Path | None:
        """Generate summary report from individual reports.

        Creates an aggregated summary report showing all test results
        with links to individual reports. Reads the original JSON files
        to get accurate status and metadata.

        Args:
            report_paths: List of successfully generated report paths
            result_files: List of all result JSON files (for reading metadata)

        Returns:
            Path to the summary report, or None if generation failed
        """
        try:
            # Read the original JSONL files for accurate data

            all_results = []

            # Create a mapping of test_id to report_path for successful reports
            report_map = {path.stem: path for path in report_paths}

            # Read all JSONL files to get complete test information
            for result_file in result_files:
                try:
                    test_data = await self._read_jsonl_results(result_file)

                    test_id = test_data["test_id"]
                    metadata = test_data.get("metadata", {})

                    # Only include tests that have successfully generated reports
                    if test_id in report_map:
                        all_results.append(
                            {
                                "test_id": test_id,
                                "title": metadata.get("title", test_id),
                                "hostname": metadata.get(
                                    "hostname"
                                ),  # Pass hostname separately
                                "status": test_data.get(
                                    "overall_status", ResultStatus.SKIPPED.value
                                ),
                                "timestamp": test_data.get(
                                    "start_time", datetime.now().isoformat()
                                ),
                                "duration": test_data.get("duration"),
                                "result_file_path": report_map[
                                    test_id
                                ].name,  # Just the filename since they're in the same directory
                            }
                        )
                except Exception as e:
                    logger.warning(f"Failed to read metadata from {result_file}: {e}")

            # Sort results by status priority (failed first), then timestamp
            # Priority: Failed/Errored → Blocked → Passed → Skipped → Aborted
            status_priority = {
                "failed": 0,
                "errored": 0,
                "blocked": 1,
                "passed": 2,
                "skipped": 3,
                "aborted": 4,
            }
            all_results.sort(
                key=lambda x: (
                    status_priority.get(x["status"], 99),  # Unknown statuses go to end
                    x["timestamp"],
                )
            )

            # Calculate statistics
            total_tests = len(all_results)
            passed_tests = sum(
                1 for r in all_results if r["status"] == ResultStatus.PASSED.value
            )
            failed_tests = sum(
                1
                for r in all_results
                if r["status"]
                in [ResultStatus.FAILED.value, ResultStatus.ERRORED.value]
            )
            skipped_tests = sum(
                1 for r in all_results if r["status"] == ResultStatus.SKIPPED.value
            )

            # Success rate excludes skipped tests from the calculation
            tests_with_results = total_tests - skipped_tests
            success_rate = (
                (passed_tests / tests_with_results * 100)
                if tests_with_results > 0
                else 0
            )

            # Determine report type title based on archive type
            report_type = None
            if self.archive_type == "api":
                report_type = "PyATS API"
            elif self.archive_type == "d2d":
                report_type = "PyATS Direct-to-Device (D2D)"

            # Render summary
            template = self.env.get_template("summary/report.html.j2")
            html_content = template.render(
                generation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                total_tests=total_tests,
                passed_tests=passed_tests,
                failed_tests=failed_tests,
                skipped_tests=skipped_tests,
                success_rate=success_rate,
                results=all_results,
                breadcrumb_link="../../../combined_summary.html",  # 3 levels up from pyats_results/{type}/html_reports/
                report_type=report_type,
            )

            summary_file = self.report_dir / "summary_report.html"
            async with aiofiles.open(summary_file, "w") as f:
                await f.write(html_content)

            logger.info(f"Generated summary report: {summary_file}")
            return summary_file

        except Exception as e:
            logger.error(f"Failed to generate summary report: {e}")
            return None
