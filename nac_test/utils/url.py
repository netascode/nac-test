# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""URL parsing utilities for nac-test framework.

This module provides generic URL manipulation utilities used throughout
the codebase for extracting components from URLs.
"""

import re
from urllib.parse import SplitResult, urlsplit, urlunsplit

_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


def _split_url(url: str) -> tuple[SplitResult, bool]:
    """Parse a URL so the authority always lands in the netloc field.

    If the URL does not start with a recognized scheme or `//`, a `//` sentinel
    is temporarily prepended before parsing with `urlsplit`.

    Args:
        url: URL string to parse.

    Returns:
        A tuple of (parsed SplitResult, sentinel_added: bool).
    """
    if _SCHEME_RE.match(url) or url.startswith("//"):
        return urlsplit(url), False
    return urlsplit("//" + url), True


def _safe_port(parsed: SplitResult) -> str | None:
    """Safely extract the port as a string without raising ValueError on malformed ports.

    Standard library `urlsplit().port` raises `ValueError` if the port cannot be
    cast to an integer (e.g., 'notaport' or out-of-range like 99999). For display
    sanitization, we preserve whatever string was provided after the host/bracketed-IPv6.

    Args:
        parsed: The SplitResult from urlsplit.

    Returns:
        Port string if present, or None.
    """
    try:
        port = parsed.port
        return str(port) if port is not None else None
    except ValueError:
        # Port is invalid integer or out of range. Extract raw port substring from netloc.
        _, _, tail = parsed.netloc.rpartition("@")
        if tail.startswith("["):
            _, _, tail = tail.rpartition("]")
        _, sep, cand = tail.rpartition(":")
        return cand if sep and cand else None


def sanitize_url_for_display(url: str) -> str:
    """Sanitize a URL for display and command construction.

    Strips embedded credentials (userinfo, stripped rather than redacted), trailing
    slashes, and surrounding whitespace while preserving scheme, host, port, path,
    query parameters, and fragments. Hostnames are normalized to lowercase.
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

    parsed, sentinel_added = _split_url(cleaned)
    host = parsed.hostname or ""
    netloc = f"[{host}]" if ":" in host else host
    port = _safe_port(parsed)
    if port:
        netloc = f"{netloc}:{port}"

    cleaned = urlunsplit(
        (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
    )
    if sentinel_added and cleaned.startswith("//"):
        cleaned = cleaned[2:]

    return cleaned.rstrip("/")


def extract_host(url: str) -> str:
    """Extract the hostname from a URL (without port or embedded userinfo).

    Uses Python's standard library urlsplit for robust parsing.
    Handles URLs with or without scheme prefixes, stripping embedded credentials.
    IPv6 literals have their brackets stripped (brackets are URL syntax).
    Hostnames are normalized to lowercase. Port numbers and paths are excluded.

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

        extract_host("host:8080/path")
        # Returns: 'host'
    """
    if not url:
        return ""

    parsed, _ = _split_url(url.strip())
    return parsed.hostname or ""
