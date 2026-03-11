# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""URL parsing utilities for nac-test framework.

This module provides generic URL manipulation utilities used throughout
the codebase for extracting components from URLs.
"""

from urllib.parse import urlparse


def extract_host(url: str) -> str:
    """Extract the host (and optional port) from a URL.

    Uses Python's standard library urlparse for robust parsing.
    Handles URLs with or without scheme prefixes.

    Args:
        url: A URL string (e.g., "https://apic.example.com:443/path").

    Returns:
        The host portion of the URL (e.g., "apic.example.com:443").
        Returns empty string for empty input.

    Examples:
        extract_host("https://apic.example.com:443/api/v1")
        # Returns: 'apic.example.com:443'

        extract_host("http://10.1.2.3")
        # Returns: '10.1.2.3'

        extract_host("controller.local")
        # Returns: 'controller.local'
    """
    if not url:
        return ""

    parsed = urlparse(url)
    if parsed.netloc:
        return parsed.netloc

    # Handle URLs without scheme (urlparse puts them in path)
    # e.g., "apic.example.com/path" -> path="apic.example.com/path"
    return parsed.path.split("/")[0]
