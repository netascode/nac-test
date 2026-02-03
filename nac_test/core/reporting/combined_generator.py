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
    from nac_test.core.types import CombinedResults

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

    This is a pure renderer - it takes CombinedResults from the orchestrator
    and generates HTML. It does not discover or parse test results itself.

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
        self, results: CombinedResults | None = None
    ) -> Path | None:
        """Generate combined summary dashboard.

        Args:
            results: CombinedResults with .api, .d2d, .robot attributes.
                If None, an empty dashboard will be generated.

        Returns:
            Path to combined_summary.html at root level, or None if generation fails
        """
        try:
            test_type_stats: dict[str, dict[str, Any]] = {}

            # Build per-framework stats for template rendering
            if results is not None:
                # Map CombinedResults attributes to framework keys
                framework_mapping = [
                    ("API", results.api),
                    ("D2D", results.d2d),
                    ("ROBOT", results.robot),
                ]

                for framework_key, test_results in framework_mapping:
                    if test_results is None:
                        continue

                    metadata = FRAMEWORK_METADATA.get(framework_key, {})
                    test_type_stats[framework_key] = {
                        "title": metadata.get("title", framework_key),
                        "total_tests": test_results.total,
                        "passed_tests": test_results.passed,
                        "failed_tests": test_results.failed,
                        "skipped_tests": test_results.skipped,
                        "success_rate": test_results.success_rate,
                        "report_path": metadata.get("report_path", "#"),
                    }

            # Use CombinedResults computed properties for overall stats
            overall_stats = {
                "total_tests": results.total if results else 0,
                "passed_tests": results.passed if results else 0,
                "failed_tests": results.failed if results else 0,
                "skipped_tests": results.skipped if results else 0,
                "success_rate": results.success_rate if results else 0.0,
            }

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
            logger.info(
                f"  Total tests across all frameworks: {overall_stats['total_tests']}"
            )
            logger.info(f"  Frameworks included: {frameworks_included or 'none'}")

            return combined_summary_path

        except Exception as e:
            logger.error(f"Failed to generate combined summary: {e}")
            return None
