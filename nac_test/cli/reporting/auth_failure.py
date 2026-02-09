# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Auth failure HTML report generator.

This module generates HTML reports for pre-flight authentication failures.
The report is written to the output directory before exiting, ensuring
CI/CD pipelines that expect an HTML artifact don't fail with a confusing
"artifact not found" error on top of the auth failure.
"""

import logging
from datetime import datetime
from pathlib import Path

from nac_test.cli.validators.controller_auth import (
    CONTROLLER_REGISTRY,
    AuthCheckResult,
    AuthOutcome,
    extract_host,
)
from nac_test.pyats_core.reporting.templates import render_template

logger = logging.getLogger(__name__)

# Output filename for auth failure report
AUTH_FAILURE_REPORT_FILENAME = "auth_failure_report.html"


def _get_curl_example(controller_type: str, controller_url: str) -> str:
    """Generate a curl command example for manual auth testing.

    Args:
        controller_type: The controller type (ACI, SDWAN, CC).
        controller_url: The controller URL.

    Returns:
        A curl command string for the user to test authentication manually.
    """
    if controller_type == "ACI":
        return (
            f"{controller_url}/api/aaaLogin.json \\\n"
            '            -X POST -H "Content-Type: application/json" \\\n'
            '            -d \'{"aaaUser":{"attributes":{"name":"USERNAME","pwd":"PASSWORD"}}}\''
        )
    elif controller_type == "SDWAN":
        return (
            f"{controller_url}/j_security_check \\\n"
            "            -X POST \\\n"
            '            -d "j_username=USERNAME&j_password=PASSWORD"'
        )
    elif controller_type == "CC":
        return (
            f"{controller_url}/dna/system/api/v1/auth/token \\\n"
            "            -X POST \\\n"
            '            -u "USERNAME:PASSWORD"'
        )
    else:
        return f"{controller_url}"


def generate_auth_failure_report(
    auth_result: AuthCheckResult,
    output_dir: Path,
) -> Path:
    """Generate a minimal HTML report for pre-flight auth failure.

    Creates the output directory if needed and writes a single HTML file
    so CI/CD artifact collection still finds a report.

    Args:
        auth_result: The AuthCheckResult from the pre-flight check.
        output_dir: The output directory path.

    Returns:
        The path to the generated HTML report file.
    """
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine failure type for template rendering
    failure_type = (
        "unreachable" if auth_result.reason == AuthOutcome.UNREACHABLE else "auth"
    )

    # Check if this is a 403 error (for special callout in template)
    is_403 = "403" in auth_result.detail or "Forbidden" in auth_result.detail

    # Get display name and env var prefix
    config = CONTROLLER_REGISTRY.get(auth_result.controller_type)
    display_name = config.display_name if config else auth_result.controller_type
    env_var_prefix = config.env_var_prefix if config else auth_result.controller_type

    # Extract host from URL
    host = extract_host(auth_result.controller_url)

    # Get curl example for manual testing
    curl_example = _get_curl_example(
        auth_result.controller_type, auth_result.controller_url
    )

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Render template
    html_content = render_template(
        "auth_failure/report.html.j2",
        failure_type=failure_type,
        is_403=is_403,
        controller_type=auth_result.controller_type,
        controller_url=auth_result.controller_url,
        display_name=display_name,
        detail=auth_result.detail,
        env_var_prefix=env_var_prefix,
        host=host,
        curl_example=curl_example,
        timestamp=timestamp,
    )

    # Write report to file
    report_path = output_dir / AUTH_FAILURE_REPORT_FILENAME
    report_path.write_text(html_content, encoding="utf-8")

    logger.info("Auth failure report written to: %s", report_path)
    return report_path
