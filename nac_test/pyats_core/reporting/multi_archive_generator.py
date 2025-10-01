# -*- coding: utf-8 -*-

"""Multi-archive report generator for PyATS test results.

This module handles generation of HTML reports from multiple PyATS archives,
supporting different test types (API, D2D) and creating combined summaries.
"""

import asyncio
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from typing import cast

from nac_test.pyats_core.reporting.generator import ReportGenerator
from nac_test.pyats_core.reporting.templates import get_jinja_environment, TEMPLATES_DIR
from nac_test.pyats_core.reporting.types import ResultStatus
from nac_test.pyats_core.reporting.utils.archive_inspector import ArchiveInspector
from nac_test.pyats_core.reporting.utils.archive_extractor import ArchiveExtractor

logger = logging.getLogger(__name__)


class MultiArchiveReportGenerator:
    """Handles report generation for multiple PyATS archives.

    This class extracts multiple archives, delegates to ReportGenerator for
    individual report generation, and creates a combined summary when needed.
    It maintains single responsibility by focusing only on multi-archive coordination.

    Attributes:
        output_dir: Base output directory for all reports
        pyats_results_dir: Directory where archives will be extracted
        env: Jinja2 environment for template rendering
    """

    def __init__(self, output_dir: Path, minimal_reports: bool = False) -> None:
        """Initialize the multi-archive report generator.

        Args:
            output_dir: Base output directory for all operations
            minimal_reports: Only include command outputs for failed/errored tests
        """
        self.output_dir = output_dir
        self.pyats_results_dir = output_dir / "pyats_results"
        self.minimal_reports = minimal_reports

        # Initialize Jinja2 environment for combined summary
        self.env = get_jinja_environment(TEMPLATES_DIR)

    async def generate_reports_from_archives(
        self, archive_paths: List[Path]
    ) -> Dict[str, Any]:
        """Generate reports from multiple PyATS archives.

        This is the main entry point that coordinates the entire process:
        1. Extracts each archive to its appropriate subdirectory
        2. Runs ReportGenerator on each extracted archive
        3. Generates combined summary if multiple archives exist

        Args:
            archive_paths: List of paths to PyATS archive files

        Returns:
            Dictionary containing:
                - status: 'success', 'partial', or 'failed'
                - results: Dict mapping archive type to generation results
                - combined_summary: Path to combined summary (if generated)
                - duration: Total time taken
        """
        start_time = datetime.now()

        if not archive_paths:
            logger.warning("No archive paths provided")
            return {
                "status": "failed",
                "results": {},
                "combined_summary": None,
                "duration": 0,
            }

        # Clean and prepare results directory
        if self.pyats_results_dir.exists():
            shutil.rmtree(self.pyats_results_dir)
        self.pyats_results_dir.mkdir(parents=True)

        # Process each archive
        results: Dict[str, Dict[str, Any]] = {}
        tasks = []

        for archive_path in archive_paths:
            if not archive_path.exists():
                logger.warning(f"Archive not found: {archive_path}")
                continue

            archive_type = ArchiveInspector.get_archive_type(archive_path)
            task = self._process_single_archive(archive_type, archive_path)
            tasks.append((archive_type, task))

        # Execute all archive processing in parallel
        if tasks:
            task_results = await asyncio.gather(
                *[task for _, task in tasks], return_exceptions=True
            )

            # Map results back to archive types
            for idx, (archive_type, _) in enumerate(tasks):
                if isinstance(task_results[idx], Exception):
                    logger.error(
                        f"Failed to process {archive_type} archive: {task_results[idx]}"
                    )
                    results[archive_type] = {
                        "status": "error",
                        "error": str(task_results[idx]),
                    }
                else:
                    results[archive_type] = cast(Dict[str, Any], task_results[idx])

        # Generate combined summary if we have multiple successful archives
        combined_summary_path = None
        successful_archives = [
            k for k, v in results.items() if v.get("status") == "success"
        ]

        if len(successful_archives) > 1:
            combined_summary_path = await self._generate_combined_summary(results)

        # Determine overall status
        if not results:
            overall_status = "failed"
        elif all(r.get("status") == "success" for r in results.values()):
            overall_status = "success"
        elif any(r.get("status") == "success" for r in results.values()):
            overall_status = "partial"
        else:
            overall_status = "failed"

        return {
            "status": overall_status,
            "duration": (datetime.now() - start_time).total_seconds(),
            "results": results,
            "combined_summary": str(combined_summary_path)
            if combined_summary_path
            else None,
        }

    async def _process_single_archive(
        self, archive_type: str, archive_path: Path
    ) -> Dict[str, Any]:
        """Process a single archive by extracting and generating reports.

        Args:
            archive_type: Type of archive ('api' or 'd2d')
            archive_path: Path to the archive file

        Returns:
            Result dictionary from ReportGenerator
        """
        logger.info(f"Processing {archive_type} archive: {archive_path.name}")

        # Create type-specific extraction directory
        extract_dir = self.pyats_results_dir / archive_type
        extract_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Extract archive
            await self._extract_archive(archive_path, extract_dir)

            # Run ReportGenerator on extracted contents
            generator = ReportGenerator(
                self.output_dir, extract_dir, minimal_reports=self.minimal_reports
            )
            result = await generator.generate_all_reports()

            # Add archive info to result
            result["archive_path"] = str(archive_path)
            result["archive_type"] = archive_type
            result["report_dir"] = str(extract_dir / "html_reports")

            return result

        except Exception as e:
            logger.error(f"Failed to process {archive_type} archive: {e}")
            return {
                "status": "error",
                "error": str(e),
                "archive_path": str(archive_path),
                "archive_type": archive_type,
            }

    async def _extract_archive(self, archive_path: Path, target_dir: Path) -> None:
        """Extract a PyATS archive to the target directory using ArchiveExtractor.

        This method uses ArchiveExtractor to handle:
        - Clearing previous results
        - Preserving HTML reports in previous archives
        - Proper error handling

        Args:
            archive_path: Path to the archive file
            target_dir: Directory to extract contents to
        """
        loop = asyncio.get_event_loop()

        def extract() -> None:
            # The target_dir already contains the full path like output_dir/pyats_results/api
            # So we just need to get the relative path from output_dir
            target_subdir = str(target_dir.relative_to(self.output_dir))

            # Use ArchiveExtractor for proper extraction with HTML preservation
            extraction_path = ArchiveExtractor.extract_archive_to_directory(
                archive_path, self.output_dir, target_subdir
            )

            if not extraction_path:
                raise RuntimeError(f"Failed to extract archive {archive_path}")

        await loop.run_in_executor(None, extract)
        logger.debug(
            f"Extracted {archive_path.name} to {target_dir} with HTML report preservation"
        )

    async def _generate_combined_summary(
        self, results: Dict[str, Dict[str, Any]]
    ) -> Optional[Path]:
        """Generate a combined summary report for multiple archive types.

        Creates an aggregated view of all test types (API, D2D) showing overall
        statistics and links to individual detailed reports.

        Args:
            results: Dictionary mapping archive types to their results

        Returns:
            Path to the combined summary file, or None if generation fails
        """
        try:
            # Calculate overall statistics
            overall_stats = {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "skipped_tests": 0,
                "success_rate": 0.0,
            }

            # Prepare test type specific statistics
            test_type_stats = {}

            for archive_type, result in results.items():
                if result.get("status") != "success":
                    continue

                # Read JSON files from the archive's html_report_data directory
                archive_dir = self.pyats_results_dir / archive_type
                json_dir = archive_dir / "html_reports" / "html_report_data"

                stats = {
                    "title": "API"
                    if archive_type == "api"
                    else "Device-to-Device (D2D)",
                    "total_tests": 0,
                    "passed_tests": 0,
                    "failed_tests": 0,
                    "skipped_tests": 0,
                    "success_rate": 0.0,
                    "report_path": f"{archive_type}/html_reports/summary_report.html",
                }

                # Read all JSON files to calculate statistics
                if json_dir.exists():
                    for json_file in json_dir.glob("*.json"):
                        try:
                            test_data = json.loads(json_file.read_text())
                            status = test_data.get(
                                "overall_status", ResultStatus.SKIPPED.value
                            )

                            stats["total_tests"] = int(stats.get("total_tests", 0)) + 1

                            if status == ResultStatus.PASSED.value:
                                stats["passed_tests"] = (
                                    int(stats.get("passed_tests", 0)) + 1
                                )
                            elif status in [
                                ResultStatus.FAILED.value,
                                ResultStatus.ERRORED.value,
                            ]:
                                stats["failed_tests"] = (
                                    int(stats.get("failed_tests", 0)) + 1
                                )
                            elif status == ResultStatus.SKIPPED.value:
                                stats["skipped_tests"] = (
                                    int(stats.get("skipped_tests", 0)) + 1
                                )

                        except Exception as e:
                            logger.warning(
                                f"Failed to read test data from {json_file}: {e}"
                            )

                # Calculate success rate for this test type
                total_tests = int(stats.get("total_tests", 0))
                skipped_tests = int(stats.get("skipped_tests", 0))
                passed_tests = int(stats.get("passed_tests", 0))

                tests_with_results = total_tests - skipped_tests
                if tests_with_results > 0:
                    stats["success_rate"] = (passed_tests / tests_with_results) * 100

                # Add to overall stats
                overall_stats["total_tests"] = (
                    int(overall_stats.get("total_tests", 0)) + total_tests
                )
                overall_stats["passed_tests"] = (
                    int(overall_stats.get("passed_tests", 0)) + passed_tests
                )
                overall_stats["failed_tests"] = int(
                    overall_stats.get("failed_tests", 0)
                ) + int(stats.get("failed_tests", 0))
                overall_stats["skipped_tests"] = (
                    int(overall_stats.get("skipped_tests", 0)) + skipped_tests
                )

                test_type_stats[archive_type.upper()] = stats

            # Calculate overall success rate
            overall_total_tests = int(overall_stats.get("total_tests", 0))
            overall_skipped_tests = int(overall_stats.get("skipped_tests", 0))
            overall_passed_tests = int(overall_stats.get("passed_tests", 0))

            overall_tests_with_results = overall_total_tests - overall_skipped_tests
            if overall_tests_with_results > 0:
                overall_stats["success_rate"] = (
                    overall_passed_tests / overall_tests_with_results
                ) * 100

            # Render the combined summary template
            template = self.env.get_template("summary/combined_report.html.j2")
            html_content = template.render(
                generation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                overall_stats=overall_stats,
                test_type_stats=test_type_stats,
            )

            # Write the combined summary file
            combined_summary_path = self.pyats_results_dir / "combined_summary.html"
            combined_summary_path.write_text(html_content)

            logger.info(f"Generated combined summary report: {combined_summary_path}")
            return combined_summary_path

        except Exception as e:
            logger.error(f"Failed to generate combined summary: {e}")
            return None
