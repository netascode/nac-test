# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Common utilities for architecture-specific validators.

This module provides shared helper functions used across multiple
architecture validators (ACI, SD-WAN, Catalyst Center, etc.).
"""

import os


def is_architecture_active(arch: str) -> bool:
    """Check if specific architecture credentials are present in environment.

    This provides a lightweight check to determine if a particular controller
    architecture is configured, without requiring full credential validation.

    Args:
        arch: Architecture name in uppercase (ACI, SDWAN, CC, MERAKI, FMC, ISE).

    Returns:
        True if the architecture's URL environment variable is set and non-empty.
        False otherwise.

    Example:
        >>> import os
        >>> os.environ["ACI_URL"] = "https://apic.local"
        >>> is_architecture_active("ACI")
        True
        >>> is_architecture_active("SDWAN")
        False

    Note:
        This only checks for the presence of the URL variable. It does not
        validate credentials or test connectivity. For full credential
        validation, use the detect_controller_type() function from
        nac_test.utils.controller instead.
    """
    url_var = f"{arch}_URL"
    value = os.environ.get(url_var)
    return bool(value and value.strip())
