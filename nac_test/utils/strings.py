# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""String utility functions for nac-test framework."""

import re

import markdown  # type: ignore[import-untyped]


def markdown_to_html(text: str | None) -> str:
    """Convert Markdown text to HTML.

    Converts Markdown-formatted text to HTML with support for:
    - Lists (ordered and unordered, including nested)
    - Bold text (**text**)
    - Italic text (*text*)
    - Code blocks (inline and fenced)
    - Headings
    - Links
    - Tables, footnotes, abbreviations (via 'extra' extension)
    - Newlines converted to <br> tags (via 'nl2br' extension)

    Args:
        text: Markdown-formatted text to convert.

    Returns:
        HTML formatted text, or empty string if input is empty.
    """
    if not text:
        return ""
    md = markdown.Markdown(extensions=["extra", "nl2br", "sane_lists"])
    return str(md.convert(text))


def sanitize_hostname(hostname: str) -> str:
    """Sanitize a hostname for use in filenames and identifiers.

    Replaces any character that is not alphanumeric or underscore with an underscore,
    then converts to lowercase. This ensures the resulting string is safe for use in
    filenames, task IDs, and other identifiers across different platforms.

    Args:
        hostname: The hostname to sanitize (e.g., "sd-dc-c8kv-01").

    Returns:
        Sanitized hostname suitable for filenames (e.g., "sd_dc_c8kv_01").

    Examples:
        >>> sanitize_hostname("sd-dc-c8kv-01")
        'sd_dc_c8kv_01'
        >>> sanitize_hostname("Router.Corp")
        'router_corp'
        >>> sanitize_hostname("device_name")
        'device_name'
    """
    return re.sub(r"[^a-zA-Z0-9_]", "_", hostname).lower()
