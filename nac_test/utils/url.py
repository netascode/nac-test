# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""URL parsing utilities for nac-test framework.

This module provides generic URL manipulation utilities used throughout
the codebase for extracting components from URLs.
"""

from urllib.parse import urlparse, urlsplit, urlunsplit


def sanitize_url_for_display(url: str) -> str:
    """Sanitize a URL for display and command construction.

    Strips embedded credentials (userinfo), trailing slashes, and whitespace
    while preserving scheme, host, port, path, query parameters, and fragments.
    Returns empty string for empty or whitespace-only input.

    Args:
        url: A URL string (e.g., "https://user:pass@apic.example.com:8443/").

    Returns:
        Cleaned URL without credentials or trailing slashes
        (e.g., "https://apic.example.com:8443").
    """
    if not url:
        return ""
    cleaned = url.strip()
    if not cleaned:
        return ""

    if "://" in cleaned:
        parsed = urlsplit(cleaned)
        host = parsed.hostname or ""
        if ":" in host:  # IPv6 literal
            netloc = f"[{host}]"
        else:
            netloc = host
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"
        cleaned = urlunsplit(
            (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
        )
    elif cleaned.startswith("//"):
        parsed = urlsplit(cleaned)
        host = parsed.hostname or ""
        if ":" in host:
            netloc = f"[{host}]"
        else:
            netloc = host
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"
        cleaned = urlunsplit(("", netloc, parsed.path, parsed.query, parsed.fragment))
    elif "@" in cleaned:
        cleaned = cleaned.split("@", 1)[1]

    return cleaned.rstrip("/")


def extract_host(url: str) -> str:
    """Extract the hostname from a URL (without port).

    Uses Python's standard library urlparse for robust parsing.
    Handles URLs with or without scheme prefixes.
    IPv6 literals have their brackets stripped (brackets are URL syntax).
    Port numbers are excluded from the result.

    Args:
        url: A URL string (e.g., "https://apic.example.com:443/path").

    Returns:
        The hostname portion of the URL (e.g., "apic.example.com").
        Returns empty string for empty input.

    Examples:
        extract_host("https://apic.example.com:443/api/v1")
        # Returns: 'apic.example.com'

        extract_host("http://10.1.2.3")
        # Returns: '10.1.2.3'

        extract_host("https://[2001:db8::1]:8443")
        # Returns: '2001:db8::1'

        extract_host("controller.local")
        # Returns: 'controller.local'
    """
    if not url:
        return ""

    parsed = urlparse(url)
    if parsed.netloc:
        # Use hostname to strip IPv6 brackets and exclude port
        return parsed.hostname or ""

    # Handle URLs without scheme (urlparse puts them in path)
    # e.g., "apic.example.com/path" -> path="apic.example.com/path"
    # Strip port if present (e.g., "host:8080/path" -> "host")
    host_part = parsed.path.split("/")[0]
    return host_part.split(":")[0]
