# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""String utility functions for nac-test framework."""

import re


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
