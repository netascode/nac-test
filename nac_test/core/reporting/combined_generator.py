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
from typing import Any, NamedTuple

from nac_test.core.constants import (
    COMBINED_SUMMARY_FILENAME,
    HTML_REPORTS_DIRNAME,
    HTTP_FORBIDDEN_CODE,
    PYATS_RESULTS_DIRNAME,
    REPORT_TIMESTAMP_FORMAT,
    ROBOT_RESULTS_DIRNAME,
    SUMMARY_REPORT_FILENAME,
)
from nac_test.core.types import CombinedResults, PreFlightFailure
from nac_test.pyats_core.reporting.templates import TEMPLATES_DIR, get_jinja_environment
from nac_test.utils.controller import get_display_name, get_env_var_prefix
from nac_test.utils.url import extract_host

logger = logging.getLogger(__name__)

# Framework display metadata - maps framework keys to dashboard display info
FRAMEWORK_METADATA: dict[str, dict[str, str]] = {
    "API": {
        "title": "PyATS API",
        "report_path": f"{PYATS_RESULTS_DIRNAME}/api/{HTML_REPORTS_DIRNAME}/{SUMMARY_REPORT_FILENAME}",
    },
    "D2D": {
        "title": "PyATS Direct-to-Device (D2D)",
        "report_path": f"{PYATS_RESULTS_DIRNAME}/d2d/{HTML_REPORTS_DIRNAME}/{SUMMARY_REPORT_FILENAME}",
    },
    "ROBOT": {
        "title": "Robot Framework",
        "report_path": f"{ROBOT_RESULTS_DIRNAME}/{SUMMARY_REPORT_FILENAME}",
    },
}


class _CurlTemplate(NamedTuple):
    """Curl command template for manual auth testing.

    Attributes:
        endpoint: URL path appended to the controller URL.
        options: Curl command-line options (method, headers, data).
    """

    endpoint: str
    options: str


# Curl command templates for manual auth testing, keyed by controller type.
_CURL_TEMPLATES: dict[str, _CurlTemplate] = {
    "ACI": _CurlTemplate(
        endpoint="/api/aaaLogin.json",
        options='-X POST -H "Content-Type: application/json" \\\n'
        '            -d \'{"aaaUser":{"attributes":{"name":"USERNAME","pwd":"PASSWORD"}}}\'',
    ),
    "SDWAN": _CurlTemplate(
        endpoint="/j_security_check",
        options='-X POST \\\n            -d "j_username=USERNAME&j_password=PASSWORD"',
    ),
    "CC": _CurlTemplate(
        endpoint="/dna/system/api/v1/auth/token",
        options='-X POST \\\n            -u "USERNAME:PASSWORD"',
    ),
}


def _get_curl_example(controller_type: str, controller_url: str) -> str:
    """Generate a curl command example for manual auth testing.

    Args:
        controller_type: The controller type (ACI, SDWAN, CC).
        controller_url: The controller URL.

    Returns:
        A curl command string for the user to test authentication manually.
    """
    template = _CURL_TEMPLATES.get(controller_type)
    if template is None:
        logger.debug(
            "No curl template for controller type %s, returning URL only",
            controller_type,
        )
        return controller_url
    return f"{controller_url}{template.endpoint} \\\n            {template.options}"


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

        Dispatches to the appropriate renderer based on the results state:
        - If pre_flight_failure is set, renders the auth failure template
        - Otherwise, renders the normal combined dashboard template

        Args:
            results: CombinedResults with test data or pre-flight failure.
                If None, an empty dashboard will be generated.

        Returns:
            Path to combined_summary.html, or None if generation fails.
        """
        if results is not None and results.pre_flight_failure is not None:
            return self._generate_pre_flight_failure_report(results.pre_flight_failure)

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
                        "stats": test_results,
                        "report_path": metadata.get("report_path", "#"),
                    }

            overall_stats = results if results is not None else CombinedResults()

            # Render combined summary template
            template = self.env.get_template("summary/combined_report.html.j2")
            html_content = template.render(
                generation_time=datetime.now().strftime(REPORT_TIMESTAMP_FORMAT),
                overall_stats=overall_stats,
                test_type_stats=test_type_stats,
            )

            # Write to root-level combined_summary.html
            combined_summary_path = self.output_dir / COMBINED_SUMMARY_FILENAME
            combined_summary_path.write_text(html_content, encoding="utf-8")

            frameworks_included = ", ".join(test_type_stats.keys())
            logger.info("Generated combined dashboard: %s", combined_summary_path)
            logger.info("  Total tests across all frameworks: %d", overall_stats.total)
            logger.info("  Frameworks included: %s", frameworks_included or "none")

            return combined_summary_path

        except Exception as e:
            logger.error("Failed to generate combined summary: %s", e)
            return None

    def _generate_pre_flight_failure_report(
        self, failure: PreFlightFailure
    ) -> Path | None:
        """Generate HTML report for a pre-flight failure.

        Renders the auth_failure/report.html.j2 template with context
        derived from the PreFlightFailure dataclass. Writes to
        combined_summary.html (not auth_failure_report.html).

        Args:
            failure: The pre-flight failure details.

        Returns:
            Path to combined_summary.html, or None if generation fails.
        """
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)

            is_403 = failure.status_code == HTTP_FORBIDDEN_CODE
            display_name = get_display_name(failure.controller_type)
            env_var_prefix = get_env_var_prefix(failure.controller_type)
            host = extract_host(failure.controller_url)
            curl_example = _get_curl_example(
                failure.controller_type, failure.controller_url
            )
            timestamp = datetime.now().strftime(REPORT_TIMESTAMP_FORMAT)

            template = self.env.get_template("auth_failure/report.html.j2")
            html_content = template.render(
                failure_type=failure.failure_type,
                is_403=is_403,
                controller_type=failure.controller_type,
                controller_url=failure.controller_url,
                display_name=display_name,
                detail=failure.detail,
                env_var_prefix=env_var_prefix,
                host=host,
                curl_example=curl_example,
                timestamp=timestamp,
            )

            combined_summary_path = self.output_dir / COMBINED_SUMMARY_FILENAME
            combined_summary_path.write_text(html_content, encoding="utf-8")

            logger.info(
                "Generated pre-flight failure report: %s", combined_summary_path
            )
            return combined_summary_path

        except Exception as e:
            logger.error("Failed to generate pre-flight failure report: %s", e)
            return None
