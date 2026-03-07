# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""CLI user interface components for nac-test.

This module is structured as a package (rather than single file) to support
future expansion of CLI UI functionality across multiple architectures.

Currently contains:
    - banners.py: Terminal banner display for validation errors

Design Note:
    The ui/ package was created to separate presentation concerns from
    validation logic (SRP). Future additions may include architecture-specific
    banners, progress indicators, or table formatters.
"""

from nac_test.cli.ui.banners import (
    display_aci_defaults_banner,
    display_auth_failure_banner,
    display_unreachable_banner,
)

__all__ = [
    "display_aci_defaults_banner",
    "display_auth_failure_banner",
    "display_unreachable_banner",
]
