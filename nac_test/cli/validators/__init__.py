# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""CLI input validators for nac-test.

This package contains architecture-specific validators that check prerequisites
before expensive operations (e.g., data merging). Validators should validate
only - UI/presentation concerns belong in the ui/ package.

Note:
    Display functions (banners, etc.) should be imported directly from
    nac_test.cli.ui, not from this package.
"""

from nac_test.cli.validators.aci_defaults import validate_aci_defaults
from nac_test.cli.validators.common import is_architecture_active

__all__ = ["is_architecture_active", "validate_aci_defaults"]
