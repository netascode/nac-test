# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Robot Framework HTML report generator.

Generates summary report following PyATS dashboard pattern for visual consistency.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from nac_test.pyats_core.reporting.templates import TEMPLATES_DIR, get_jinja_environment
from nac_test.robot.reporting.robot_parser import RobotResultParser

logger = logging.getLogger(__name__)


class RobotReportGenerator:
    """Generates HTML summary report for Robot Framework tests.

    Follows the same pattern as PyATS ReportGenerator for consistency:
    - Reuses PyATS Jinja2 templates and styling
    - Creates summary_report.html with test list and sortable columns
    - Links to log.html with deep linking to specific tests (log.html#test-id)
    - Failed tests highlighted at top

    Attributes:
        output_dir: Base output directory
        robot_results_dir: robot_results subdirectory
        output_xml_path: Path to output.xml
        log_html_path: Path to log.html
        env: Jinja2 environment (shared with PyATS)
    """

    def __init__(self, output_dir: Path):
        """Initialize Robot report generator.

        Args:
            output_dir: Base output directory where robot_results/ exists
        """
        self.output_dir = output_dir
        self.robot_results_dir = output_dir / "robot_results"
        self.output_xml_path = self.robot_results_dir / "output.xml"
        self.log_html_path = self.robot_results_dir / "log.html"

        # Initialize Jinja2 environment (reuse PyATS templates)
        self.env = get_jinja_environment(TEMPLATES_DIR)

    def generate_summary_report(self) -> Path | None:
        """Generate Robot summary report.

        Creates robot_results/summary_report.html with:
        - List of all Robot tests (failed at top)
        - Columns: Test Name, Status, Duration, Date, Action
        - Sortable/filterable (JavaScript from PyATS template)
        - Links to log.html#test-id for detailed view
        - Same styling as PyATS summaries for consistency

        Returns:
            Path to generated summary report, or None if generation fails or no tests found
        """
        try:
            # Check if output.xml exists
            if not self.output_xml_path.exists():
                logger.warning(f"No Robot results found at {self.output_xml_path}")
                return None

            # Parse output.xml using ResultVisitor
            logger.info(f"Parsing Robot results from {self.output_xml_path}")
            parser = RobotResultParser(self.output_xml_path)
            data = parser.parse()

            # Get aggregated stats
            stats = data["aggregated_stats"]

            # If no tests, don't generate report
            if stats["total_tests"] == 0:
                logger.info("No Robot tests found, skipping summary report")
                return None

            # Prepare results for template (match PyATS format)
            results = []
            for test in data["tests"]:
                # Map Robot status (PASS/FAIL/SKIP) to PyATS format (passed/failed/skipped)
                # This allows reusing PyATS template's status_style filter
                status_map = {"PASS": "passed", "FAIL": "failed", "SKIP": "skipped"}
                status = status_map.get(test["status"], "skipped")

                results.append(
                    {
                        "title": test["name"],
                        "status": status,
                        "duration": test["duration"],
                        "timestamp": test["start_time"],
                        # Deep link to Robot's log.html with test ID anchor
                        "result_file_path": f"log.html#{test['test_id']}",
                        "hostname": None,  # Robot tests don't have per-device structure
                    }
                )

            # Render template (reuse PyATS summary template)
            template = self.env.get_template("summary/report.html.j2")
            html_content = template.render(
                generation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                total_tests=stats["total_tests"],
                passed_tests=stats["passed_tests"],
                failed_tests=stats["failed_tests"],
                skipped_tests=stats["skipped_tests"],
                success_rate=stats["success_rate"],
                results=results,
            )

            # Write summary report
            summary_path = self.robot_results_dir / "summary_report.html"
            summary_path.write_text(html_content)

            logger.info(f"Generated Robot summary report: {summary_path}")
            logger.info(
                f"  Tests: {stats['total_tests']} total, "
                f"{stats['passed_tests']} passed, {stats['failed_tests']} failed"
            )

            return summary_path

        except Exception as e:
            logger.error(f"Failed to generate Robot summary report: {e}")
            return None

    def get_aggregated_stats(self) -> dict[str, Any]:
        """Get aggregated statistics without generating full report.

        Used by combined dashboard to show Robot block stats.
        This is more efficient than generating the full HTML report.

        Returns:
            Dictionary with aggregated statistics:
                - total_tests, passed_tests, failed_tests, skipped_tests, success_rate
            Returns zeros if output.xml doesn't exist or parsing fails.
        """
        try:
            if not self.output_xml_path.exists():
                logger.debug(f"No Robot results found at {self.output_xml_path}")
                return {
                    "total_tests": 0,
                    "passed_tests": 0,
                    "failed_tests": 0,
                    "skipped_tests": 0,
                    "success_rate": 0.0,
                }

            parser = RobotResultParser(self.output_xml_path)
            data = parser.parse()
            return cast(dict[str, Any], data["aggregated_stats"])

        except Exception as e:
            logger.warning(f"Failed to get Robot stats: {e}")
            return {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "skipped_tests": 0,
                "success_rate": 0.0,
            }
