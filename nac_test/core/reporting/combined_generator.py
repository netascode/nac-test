# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Combined report generator for all test frameworks.

Orchestrates report generation across PyATS, Robot Framework, and future frameworks,
creating a unified dashboard at the root level.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from nac_test.pyats_core.reporting.templates import TEMPLATES_DIR, get_jinja_environment
from nac_test.robot.reporting.robot_generator import RobotReportGenerator

logger = logging.getLogger(__name__)


class CombinedReportGenerator:
    """Generates combined dashboard across all test frameworks.

    Coordinates:
    - PyATS API results (stats from MultiArchiveReportGenerator)
    - PyATS D2D results (stats from MultiArchiveReportGenerator)
    - Robot Framework results (via RobotReportGenerator)

    Creates root-level combined_summary.html with up to 3 blocks (Robot, API, D2D).
    Shows blocks with 0 tests (user can hide via Jinja2 conditionals if desired).

    Attributes:
        output_dir: Base output directory for all test results
        env: Jinja2 environment (shared with PyATS)
    """

    def __init__(self, output_dir: Path):
        """Initialize combined report generator.

        Args:
            output_dir: Base output directory for all test results
        """
        self.output_dir = Path(output_dir)
        self.env = get_jinja_environment(TEMPLATES_DIR)

    def generate_combined_summary(
        self, pyats_stats: dict[str, dict[str, Any]] | None = None
    ) -> Path | None:
        """Generate combined summary dashboard.

        Args:
            pyats_stats: Optional dict of PyATS statistics by archive type.
                         Populated by MultiArchiveReportGenerator._collect_pyats_stats()
                         Format: {"API": {...stats...}, "D2D": {...stats...}}
                         If None or empty, no PyATS blocks will be shown.

        Returns:
            Path to combined_summary.html at root level, or None if generation fails
        """
        try:
            # Initialize overall stats
            overall_stats = {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "skipped_tests": 0,
                "success_rate": 0.0,
            }

            test_type_stats = {}

            # Add PyATS results if available
            if pyats_stats:
                for archive_type, stats in pyats_stats.items():
                    # Skip if stats is None (shouldn't happen, but defensive)
                    if stats is None:
                        continue  # type: ignore[unreachable]

                    # Add to test_type_stats (will be shown as blocks)
                    test_type_stats[archive_type] = stats

                    # Accumulate to overall stats
                    overall_stats["total_tests"] += stats["total_tests"]
                    overall_stats["passed_tests"] += stats["passed_tests"]
                    overall_stats["failed_tests"] += stats["failed_tests"]
                    overall_stats["skipped_tests"] += stats["skipped_tests"]

            # Add Robot Framework results if available
            robot_output_xml = self.output_dir / "robot_results" / "output.xml"
            if robot_output_xml.exists():
                robot_generator = RobotReportGenerator(self.output_dir)
                robot_stats = robot_generator.get_aggregated_stats()

                # Always add Robot block (even if 0 tests)
                # User can add Jinja2 conditionals later to hide empty blocks if desired
                test_type_stats["ROBOT"] = {
                    "title": "Robot Framework",
                    "total_tests": robot_stats["total_tests"],
                    "passed_tests": robot_stats["passed_tests"],
                    "failed_tests": robot_stats["failed_tests"],
                    "skipped_tests": robot_stats["skipped_tests"],
                    "success_rate": robot_stats["success_rate"],
                    "report_path": "robot_results/summary_report.html",
                }

                # Accumulate to overall stats
                overall_stats["total_tests"] += robot_stats["total_tests"]
                overall_stats["passed_tests"] += robot_stats["passed_tests"]
                overall_stats["failed_tests"] += robot_stats["failed_tests"]
                overall_stats["skipped_tests"] += robot_stats["skipped_tests"]

            # Calculate overall success rate
            total = overall_stats["total_tests"]
            skipped = overall_stats["skipped_tests"]
            passed = overall_stats["passed_tests"]

            tests_with_results = total - skipped
            if tests_with_results > 0:
                overall_stats["success_rate"] = (passed / tests_with_results) * 100

            # Render combined summary template
            template = self.env.get_template("summary/combined_report.html.j2")
            html_content = template.render(
                generation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                overall_stats=overall_stats,
                test_type_stats=test_type_stats,
            )

            # Write to root-level combined_summary.html
            combined_summary_path = self.output_dir / "combined_summary.html"
            combined_summary_path.write_text(html_content)

            frameworks_included = ", ".join(test_type_stats.keys())
            logger.info(f"Generated combined dashboard: {combined_summary_path}")
            logger.info(f"  Total tests across all frameworks: {total}")
            logger.info(f"  Frameworks included: {frameworks_included or 'none'}")

            return combined_summary_path

        except Exception as e:
            logger.error(f"Failed to generate combined summary: {e}")
            return None
