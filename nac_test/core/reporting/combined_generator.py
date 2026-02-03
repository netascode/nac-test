# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Combined report generator for all test frameworks.

Generates a unified dashboard at the root level, rendering statistics
passed in from the orchestrators.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nac_test.pyats_core.reporting.templates import TEMPLATES_DIR, get_jinja_environment

if TYPE_CHECKING:
    from nac_test.core.types import TestResults

logger = logging.getLogger(__name__)

# Framework display metadata - maps framework keys to dashboard display info
FRAMEWORK_METADATA: dict[str, dict[str, str]] = {
    "API": {
        "title": "PyATS API",
        "report_path": "pyats_results/api/html_reports/summary_report.html",
    },
    "D2D": {
        "title": "PyATS Direct-to-Device (D2D)",
        "report_path": "pyats_results/d2d/html_reports/summary_report.html",
    },
    "ROBOT": {
        "title": "Robot Framework",
        "report_path": "robot_results/summary_report.html",
    },
}


class CombinedReportGenerator:
    """Generates combined dashboard across all test frameworks.

    This is a pure renderer - it takes TestResults objects from the
    orchestrators and generates HTML. It does not discover or parse test
    results itself.

    The orchestrators are responsible for:
    - Running tests and collecting results as TestResults
    - Populating by_framework with per-framework TestResults
    - Passing by_framework dict to this generator

    Creates root-level combined_summary.html with blocks for each framework.

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
        self, framework_results: dict[str, TestResults | Any] | None = None
    ) -> Path | None:
        """Generate combined summary dashboard.

        Args:
            framework_results: Dict mapping framework key to TestResults.
                Keys should be: "API", "D2D", "ROBOT"
                Values: TestResults objects with test statistics
                If None or empty, an empty dashboard will be generated.

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

            test_type_stats: dict[str, dict[str, Any]] = {}

            # Process all framework results passed in
            if framework_results:
                for framework_key, results in framework_results.items():
                    # Skip if results is None
                    if results is None:
                        continue

                    # Get display metadata for this framework
                    key_upper = framework_key.upper()
                    metadata = FRAMEWORK_METADATA.get(key_upper, {})

                    # Convert TestResults to template-expected format
                    stats = {
                        "title": metadata.get("title", framework_key),
                        "total_tests": results.total,
                        "passed_tests": results.passed,
                        "failed_tests": results.failed,
                        "skipped_tests": results.skipped,
                        "success_rate": results.success_rate,
                        "report_path": metadata.get("report_path", "#"),
                    }

                    # Add to test_type_stats (will be shown as blocks)
                    test_type_stats[key_upper] = stats

                    # Accumulate to overall stats
                    overall_stats["total_tests"] += results.total
                    overall_stats["passed_tests"] += results.passed
                    overall_stats["failed_tests"] += results.failed
                    overall_stats["skipped_tests"] += results.skipped

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
