"""Utility functions for working with Jinja2 templates.

This module provides Jinja2 environment configuration and custom filters
for rendering HTML reports in the nac-test PyATS framework.

Adapted from BRKXAR-2032-test-automation for use in nac-test.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

from jinja2 import BaseLoader, Environment, FileSystemLoader, StrictUndefined
from nac_test.pyats_core.reporting.types import ResultStatus

# Get the absolute path to the templates directory
TEMPLATES_DIR = Path(__file__).parent / "templates"


def format_datetime(dt_str: Union[str, datetime]) -> str:
    """Format an ISO datetime string to a human-readable format.

    Args:
        dt_str: Either an ISO format datetime string or a datetime object.

    Returns:
        Formatted datetime string in "YYYY-MM-DD HH:MM" format.

    Example:
        >>> format_datetime("2024-01-15T14:30:45.123456")
        "2024-01-15 14:30"
    """
    if isinstance(dt_str, str):
        dt = datetime.fromisoformat(dt_str)
    else:
        dt = dt_str
    return dt.strftime("%Y-%m-%d %H:%M")


def get_status_style(status: Union[ResultStatus, str]) -> Dict[str, str]:
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


def format_skip_message(message: str) -> str:
    """Format enhanced skip messages with rich content.
    
    This filter formats skip messages that contain markdown-like formatting
    (bullet points, bold text, code blocks) into proper HTML.
    
    Args:
        message: Skip message potentially containing markdown-like formatting
        
    Returns:
        HTML-formatted message with proper styling
    """
    if not message or '📋' not in message:
        # Not an enhanced skip message, return as-is
        return message
    
    # Convert markdown-like formatting to HTML
    html = message
    
    # Replace emoji
    html = html.replace('📋', '<span style="font-size: 1.2em;">📋</span>')
    
    # Convert bold text
    import re
    html = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', html)
    
    # Convert bullet points to list items
    lines = html.split('\n')
    formatted_lines = []
    in_list = False
    
    for line in lines:
        if line.strip().startswith('•'):
            if not in_list:
                formatted_lines.append('<ul class="skip-detail-list">')
                in_list = True
            # Extract the content after the bullet
            content = line.strip()[1:].strip()
            # Check if it's a code item (contains backticks)
            if '`' in content:
                content = re.sub(r'`([^`]+)`', r'<code>\1</code>', content)
            formatted_lines.append(f'<li>{content}</li>')
        else:
            if in_list:
                formatted_lines.append('</ul>')
                in_list = False
            if line.strip():
                formatted_lines.append(f'<p>{line}</p>')
    
    if in_list:
        formatted_lines.append('</ul>')
    
    return '\n'.join(formatted_lines)


def format_json_output(output: str) -> str:
    """Format output as JSON if possible, otherwise return as-is.

    This filter attempts to parse and pretty-print JSON output.
    If the output is not valid JSON, it returns the original string.

    Args:
        output: Command output string that might be JSON

    Returns:
        Pretty-printed JSON string or original output
    """
    import json

    if not output or not output.strip():
        return output

    try:
        # Try to parse the entire output first
        parsed = json.loads(output.strip())
        # Ensure it's structured data (dict or list)
        if isinstance(parsed, (dict, list)):
            return json.dumps(parsed, indent=2, sort_keys=False)
    except json.JSONDecodeError:
        # If that fails, try to find JSON within the output
        # (e.g., after command echo or other prefix text)
        for i, char in enumerate(output):
            if char in "{[":
                try:
                    json_content = output[i:]
                    parsed = json.loads(json_content)
                    if isinstance(parsed, (dict, list)):
                        # Preserve any prefix text
                        prefix = output[:i]
                        return prefix + json.dumps(parsed, indent=2, sort_keys=False)
                except json.JSONDecodeError:
                    continue

    # Not valid JSON or not structured data, return as-is
    return output


def get_jinja_environment(directory: Optional[Union[str, Path]] = None) -> Environment:
    """Create a Jinja2 environment for rendering templates.

    Creates a configured Jinja2 environment with custom filters and settings
    optimized for HTML report generation.

    Args:
        directory: Directory containing the templates. If None, creates
                  an environment with no file loader (for string templates).
                  Defaults to None.

    Returns:
        Configured Jinja2 Environment instance with:
            - Custom filters registered (format_datetime, status_style)
            - Strict undefined handling
            - Whitespace trimming enabled
            - 'do' extension for template logic

    Example:
        >>> env = get_jinja_environment(TEMPLATES_DIR)
        >>> template = env.get_template("test_case/report.html.j2")
    """
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
    environment.filters["status_style"] = get_status_style
    environment.filters["format_json_output"] = format_json_output
    environment.filters["format_skip_message"] = format_skip_message

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
    return template.render(**context)


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
    return template.render(**context)
