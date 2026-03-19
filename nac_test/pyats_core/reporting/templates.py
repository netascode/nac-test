# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Utility functions for working with Jinja2 templates.

This module provides Jinja2 environment configuration and custom filters
for rendering HTML reports in the nac-test PyATS framework.

Adapted from BRKXAR-2032-test-automation for use in nac-test.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import BaseLoader, Environment, FileSystemLoader, StrictUndefined

from nac_test.pyats_core.reporting.types import ResultStatus

# Get the absolute path to the templates directory
TEMPLATES_DIR = Path(__file__).parent / "templates"


def format_datetime(dt_str: str | datetime) -> str:
    """Format an ISO datetime string to a human-readable format with milliseconds.

    Args:
        dt_str: Either an ISO format datetime string or a datetime object.

    Returns:
        Formatted datetime string in "YYYY-MM-DD HH:MM:SS.mmm" format.

    Example:
        >>> format_datetime("2024-01-15T14:30:45.123456")
        "2024-01-15 14:30:45.123"
    """
    if isinstance(dt_str, str):
        dt = datetime.fromisoformat(dt_str)
    else:
        dt = dt_str
    # Include milliseconds (first 3 digits of microseconds)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def format_duration(duration_seconds: float | int | None) -> str:
    """Format a duration in seconds to a human-readable format.

    Uses smart formatting to display durations in the most readable way:
    - Less than 1 second: "< 1s"
    - 1-59 seconds: "X.Xs" (e.g., "2.5s", "45.2s")
    - 1-59 minutes: "Xm XXs" (e.g., "1m 23s", "15m 8s")
    - 1+ hours: "Xh Xm" (e.g., "1h 5m", "2h 45m")

    Args:
        duration_seconds: Duration in seconds as a float or int, or None.

    Returns:
        Formatted duration string, or "N/A" if duration is None.

    Examples:
        >>> format_duration(0.5)
        "< 1s"
        >>> format_duration(2.456)
        "2.5s"
        >>> format_duration(83.2)
        "1m 23s"
        >>> format_duration(3725.8)
        "1h 2m"
    """
    if duration_seconds is None:
        return "N/A"

    # Convert to float for calculations
    duration = float(duration_seconds)

    # Less than 1 second
    if duration < 1.0:
        return "< 1s"

    # 1-59 seconds: show one decimal place
    if duration < 60:
        return f"{duration:.1f}s"

    # 1-59 minutes: show minutes and seconds
    if duration < 3600:
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        return f"{minutes}m {seconds}s"

    # 1+ hours: show hours and minutes (drop seconds for brevity)
    hours = int(duration // 3600)
    minutes = int((duration % 3600) // 60)
    return f"{hours}h {minutes}m"


def get_status_style(status: ResultStatus | str) -> dict[str, str]:
    """Get the CSS class and display text for a result status.

    This function maps ResultStatus enum values to their corresponding
    CSS classes and display text for consistent styling in HTML reports.

    Args:
        status: A ResultStatus enum value or string representation.

    Returns:
        Dictionary with keys:
            - css_class: CSS class name for styling (e.g., "pass-status")
            - display_text: Human-readable status text (e.g., "PASSED")

    Example:
        >>> get_status_style(ResultStatus.PASSED)
        {"css_class": "pass-status", "display_text": "PASSED"}
    """
    if isinstance(status, str):
        # Try to convert string to enum
        try:
            status = ResultStatus(status)
        except ValueError:
            # If not a valid enum value, use a default
            return {"css_class": "neutral-status", "display_text": status}

    # Handle each possible ResultStatus value
    if status == ResultStatus.PASSED:
        return {"css_class": "pass-status", "display_text": "PASSED"}
    elif status == ResultStatus.FAILED:
        return {"css_class": "fail-status", "display_text": "FAILED"}
    elif status == ResultStatus.SKIPPED:
        return {"css_class": "skip-status", "display_text": "SKIPPED"}
    elif status == ResultStatus.ABORTED:
        return {"css_class": "abort-status", "display_text": "ABORTED"}
    elif status == ResultStatus.ERRORED:
        return {"css_class": "error-status", "display_text": "ERROR"}
    elif status == ResultStatus.BLOCKED:
        return {"css_class": "block-status", "display_text": "BLOCKED"}
    elif status == ResultStatus.INFO:
        return {"css_class": "info-status", "display_text": "INFO"}
    else:
        return {"css_class": "neutral-status", "display_text": str(status)}


def format_result_message(message: str) -> str:
    """Format result messages with rich content for all result types.

    This universal filter formats messages containing markdown-like formatting
    (bullet points, bold text, code blocks, line breaks) into proper HTML.
    Works for PASSED, FAILED, SKIPPED, and all other result types.

    The formatter detects and handles:
    - Multiple newlines (paragraph breaks)
    - Single newlines (line breaks)
    - Bullet points (•) into HTML lists
    - Bold text (**text**) into <strong> tags
    - Code snippets (`code`) into <code> tags
    - Special emoji markers for enhanced display

    Args:
        message: Result message potentially containing markdown-like formatting

    Returns:
        HTML-formatted message with proper styling

    Example:
        >>> format_result_message("Error occurred\\n\\nPlease verify:\\n• Item 1\\n• Item 2")
        "<p>Error occurred</p>\\n<p>Please verify:</p>\\n<ul>...</ul>"
    """
    if not message:
        return message

    import re

    html = message

    # Replace common emoji markers with styled spans
    html = html.replace("📋", '<span style="font-size: 1.2em;">📋</span>')
    html = html.replace("✓", '<span style="color: var(--success);">✓</span>')
    html = html.replace("✗", '<span style="color: var(--danger);">✗</span>')
    html = html.replace("⚠", '<span style="color: var(--warning);">⚠</span>')

    # Convert bold text (**text** -> <strong>)
    html = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html)

    # Convert bullet points to HTML lists
    lines = html.split("\n")
    formatted_lines = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Handle bullet points
        if stripped.startswith("•"):
            if not in_list:
                formatted_lines.append('<ul class="result-detail-list">')
                in_list = True
            # Extract content after bullet
            content = stripped[1:].strip()
            # Convert inline code (`code` -> <code>)
            if "`" in content:
                content = re.sub(r"`([^`]+)`", r"<code>\1</code>", content)
            formatted_lines.append(f"<li>{content}</li>")
        else:
            # Close list if we were in one
            if in_list:
                formatted_lines.append("</ul>")
                in_list = False

            # Handle non-bullet lines
            if stripped:
                # Convert inline code in regular lines too
                if "`" in stripped:
                    stripped = re.sub(r"`([^`]+)`", r"<code>\1</code>", stripped)
                formatted_lines.append(f"<p>{stripped}</p>")
            elif formatted_lines:  # Preserve intentional blank lines between content
                # Only add blank paragraph if there's already content
                # This creates visual spacing between sections
                formatted_lines.append('<p class="spacer"></p>')

    # Close list if still open at end
    if in_list:
        formatted_lines.append("</ul>")

    return "\n".join(formatted_lines)


def get_jinja_environment(directory: str | Path | None = None) -> Environment:
    """Create a Jinja2 environment for rendering templates.

    Creates a configured Jinja2 environment with custom filters and settings
    optimized for HTML report generation.

    Args:
        directory: Directory containing the templates. If None, creates
                  an environment with no file loader (for string templates).
                  Defaults to None.

    Returns:
        Configured Jinja2 Environment instance with:
            - Custom filters registered (format_datetime, status_style, format_result_message)
            - Strict undefined handling
            - Whitespace trimming enabled
            - 'do' extension for template logic

    Example:
        >>> env = get_jinja_environment(TEMPLATES_DIR)
        >>> template = env.get_template("test_case/report.html.j2")
    """
    loader: FileSystemLoader | BaseLoader
    if directory is not None:
        loader = FileSystemLoader(str(directory))
    else:
        loader = BaseLoader()

    environment = Environment(
        loader=loader,
        extensions=["jinja2.ext.do"],
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
    )
    environment.filters["format_datetime"] = format_datetime
    environment.filters["format_duration"] = format_duration
    environment.filters["status_style"] = get_status_style
    environment.filters["format_result_message"] = (
        format_result_message  # Universal formatter for all result types
    )

    return environment


def render_template(template_path: str, **context: Any) -> str:
    """Render a template file with the given context.

    Loads and renders a template from the templates directory using
    the provided context variables.

    Args:
        template_path: Path to the template relative to the templates directory
                      (e.g., "test_case/report.html.j2").
        **context: Keyword arguments passed as variables to the template.

    Returns:
        Rendered template as a string.

    Example:
        >>> html = render_template(
        ...     "test_case/report.html.j2",
        ...     title="My Test",
        ...     status=ResultStatus.PASSED,
        ...     results=[{"message": "Test passed"}]
        ... )
    """
    env = get_jinja_environment(TEMPLATES_DIR)
    template = env.get_template(template_path)
    return template.render(**context)  # type: ignore[no-any-return]


def render_string_template(template_string: str, **context: Any) -> str:
    """Render a string template with the given context.

    Renders a Jinja2 template provided as a string, useful for
    dynamic template generation or testing.

    Args:
        template_string: The Jinja2 template as a string.
        **context: Keyword arguments passed as variables to the template.

    Returns:
        Rendered template as a string.

    Example:
        >>> html = render_string_template(
        ...     "<h1>{{ title }}</h1><p>Status: {{ status }}</p>",
        ...     title="Test Result",
        ...     status="PASSED"
        ... )
    """
    env = get_jinja_environment()
    template = env.from_string(template_string)
    return template.render(**context)  # type: ignore[no-any-return]
