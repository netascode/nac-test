# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Combined report generator for all test frameworks.

Generates a unified dashboard at the root level, rendering statistics
passed in from the orchestrators.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from nac_test.core.constants import (
    COMBINED_SUMMARY_FILENAME,
    HTML_REPORTS_DIRNAME,
    HTTP_FORBIDDEN_CODE,
    PRE_FLIGHT_FAILURE_FILENAME,
    PYATS_RESULTS_DIRNAME,
    REPORT_TIMESTAMP_FORMAT,
    ROBOT_RESULTS_DIRNAME,
    SUMMARY_REPORT_FILENAME,
)
from nac_test.core.types import (
    CombinedResults,
    ControllerTypeKey,
    PreFlightFailure,
)
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


@dataclass
class FrameworkRenderData:
    """Per-framework data passed to the combined dashboard template.

    Attributes:
        title: Human-readable framework name shown in the dashboard.
        stats: Test result counts, or None when pre-flight failed for this framework.
        report_path: Relative path to the framework's detail report.
        is_pre_flight_failure: True when the framework was skipped due to pre-flight failure.
        has_report: True if a detailed report with test results exists for this framework.
    """

    title: str
    stats: object  # TestResults | None — kept as object to avoid circular imports
    report_path: str
    is_pre_flight_failure: bool
    has_report: bool


class _CurlTemplate(NamedTuple):
    """Curl command template for manual auth testing.

    Attributes:
        endpoint: URL path appended to the controller URL.
        options: Curl command-line options (method, headers, data).
    """

    endpoint: str
    options: str


# Curl command templates for manual auth testing, keyed by controller type.
_CURL_TEMPLATES: dict[ControllerTypeKey, _CurlTemplate] = {
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


def _get_curl_example(controller_type: ControllerTypeKey, controller_url: str) -> str:
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
        - If pre_flight_failure is set with no other results, generates child report
          and hard-links it to combined_summary.html
        - If pre_flight_failure is set and Robot results exist, includes pre-flight in
          the combined dashboard with a link to the child report
        - Otherwise, renders the normal combined dashboard template

        Args:
            results: CombinedResults with test data or pre-flight failure.
                If None, an empty dashboard will be generated.

        Returns:
            Path to combined_summary.html, or None if generation fails.
        """
        pre_flight_report_path: Path | None = None

        if results is not None and results.pre_flight_failure is not None:
            pre_flight_report_path = self._generate_pre_flight_failure_report(
                results.pre_flight_failure
            )

            # If only pre-flight failed (no test results), hard-link to combined_summary
            if not results.has_any_results:
                if pre_flight_report_path:
                    combined_path = self.output_dir / COMBINED_SUMMARY_FILENAME
                    try:
                        # we shouldn't need to cleanup, see #639
                        combined_path.unlink(missing_ok=True)

                        combined_path.hardlink_to(pre_flight_report_path)
                        logger.info(
                            "Hard-linked pre-flight report to combined dashboard: %s",
                            combined_path,
                        )
                        return combined_path
                    except OSError as e:
                        logger.warning(
                            "Failed to hard-link pre-flight report: %s",
                            e,
                        )
                        # In a rare case of failure, let combined orchestrator
                        # print the link to the pyats_results/pre-flight page
                        # instead of the root-level dashboard
                        return pre_flight_report_path
                return None

        try:
            test_type_stats: dict[str, FrameworkRenderData] = {}

            # Build per-framework stats for template rendering
            if results is not None:
                # If pre-flight failed, mark API/D2D with link to pre-flight report
                if results.pre_flight_failure is not None and pre_flight_report_path:
                    relative_path = str(
                        pre_flight_report_path.relative_to(self.output_dir)
                    )
                    for framework_key in ("API", "D2D"):
                        metadata = FRAMEWORK_METADATA.get(framework_key, {})
                        test_type_stats[framework_key] = FrameworkRenderData(
                            title=metadata.get("title", framework_key),
                            stats=None,
                            report_path=relative_path,
                            is_pre_flight_failure=True,
                            has_report=False,
                        )

                # Map CombinedResults attributes to framework keys
                framework_mapping = [
                    ("API", results.api),
                    ("D2D", results.d2d),
                    ("ROBOT", results.robot),
                ]

                for framework_key, test_results in framework_mapping:
                    if framework_key in test_type_stats:
                        continue  # Already handled by pre-flight
                    if test_results is None:
                        continue

                    metadata = FRAMEWORK_METADATA.get(framework_key, {})
                    test_type_stats[framework_key] = FrameworkRenderData(
                        title=metadata.get("title", framework_key),
                        stats=test_results,
                        report_path=metadata.get("report_path", "#"),
                        is_pre_flight_failure=False,
                        has_report=not test_results.is_empty,
                    )

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
        pyats_results/pre_flight_failure.html as a child report.

        Args:
            failure: The pre-flight failure details.

        Returns:
            Path to pre_flight_failure.html, or None if generation fails.
        """
        try:
            failure_report_path = (
                self.output_dir / PYATS_RESULTS_DIRNAME / PRE_FLIGHT_FAILURE_FILENAME
            )
            failure_report_path.parent.mkdir(parents=True, exist_ok=True)

            is_403 = failure.status_code == HTTP_FORBIDDEN_CODE

            display_name = (
                get_display_name(failure.controller_type)
                if failure.controller_type
                else None
            )
            env_var_prefix = (
                get_env_var_prefix(failure.controller_type)
                if failure.controller_type
                else None
            )
            host = (
                extract_host(failure.controller_url) if failure.controller_url else None
            )
            curl_example = (
                _get_curl_example(failure.controller_type, failure.controller_url)
                if failure.controller_type and failure.controller_url
                else None
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

            failure_report_path.write_text(html_content, encoding="utf-8")

            logger.info("Generated pre-flight failure report: %s", failure_report_path)
            return failure_report_path

        except Exception as e:
            logger.error("Failed to generate pre-flight failure report: %s", e)
            return None
