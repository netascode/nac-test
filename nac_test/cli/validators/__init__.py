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
from nac_test.cli.validators.controller_auth import (
    AuthCheckResult,
    preflight_auth_check,
)
from nac_test.core.error_classification import AuthOutcome
from nac_test.utils.controller import CONTROLLER_REGISTRY, ControllerConfig
from nac_test.utils.url import extract_host

__all__ = [
    "AuthCheckResult",
    "AuthOutcome",
    "CONTROLLER_REGISTRY",
    "ControllerConfig",
    "extract_host",
    "is_architecture_active",
    "preflight_auth_check",
    "validate_aci_defaults",
]
