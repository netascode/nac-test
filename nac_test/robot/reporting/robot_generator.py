# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Robot Framework HTML report generator.

Generates summary report following PyATS dashboard pattern for visual consistency.
"""

import logging
from datetime import datetime
from pathlib import Path

from nac_test.core.types import TestResults
from nac_test.pyats_core.reporting.templates import TEMPLATES_DIR, get_jinja_environment
from nac_test.robot.reporting.robot_output_parser import RobotResultParser

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

        # Initialize Jinja2 environment (reuse PyATS templates)
        self.env = get_jinja_environment(TEMPLATES_DIR)

    def generate_summary_report(self) -> tuple[Path | None, TestResults]:
        """Generate Robot summary report.

        Creates robot_results/summary_report.html with:
        - List of all Robot tests (failed at top)
        - Columns: Test Name, Status, Duration, Date, Action
        - Sortable/filterable (JavaScript from PyATS template)
        - Links to log.html#test-id for detailed view
        - Same styling as PyATS summaries for consistency

        Returns:
            Tuple of (path to generated summary report, TestResults with stats).
            Returns (None, empty TestResults) if generation fails or no tests found.
        """
        try:
            # Check if output.xml exists
            if not self.output_xml_path.exists():
                logger.warning(f"No Robot results found at {self.output_xml_path}")
                return None, TestResults.from_error(
                    f"Robot output.xml not found at {self.output_xml_path}"
                )

            # Parse output.xml using ResultVisitor
            logger.info(f"Parsing Robot results from {self.output_xml_path}")
            parser = RobotResultParser(self.output_xml_path)
            data = parser.parse()

            # Get aggregated stats (TestResults object)
            stats: TestResults = data["aggregated_stats"]

            # If no tests, don't generate report
            if stats.total == 0:
                logger.info("No Robot tests found, skipping summary report")
                return None, TestResults.empty()

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
                stats=stats,
                results=results,
                breadcrumb_link="../combined_summary.html",  # 1 level up from robot_results/
                report_type="Robot Framework",
            )

            # Write summary report
            summary_path = self.robot_results_dir / "summary_report.html"
            summary_path.write_text(html_content)

            logger.info(f"Generated Robot summary report: {summary_path}")
            logger.info(
                f"  Tests: {stats.total} total, "
                f"{stats.passed} passed, {stats.failed} failed"
            )

            return summary_path, stats

        except Exception as e:
            logger.error(f"Failed to generate Robot summary report: {e}")
            return None, TestResults.from_error(f"Failed to parse output.xml: {e}")
