# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Utility modules for nac-test framework."""

from nac_test.utils.asyncio_utils import get_or_create_event_loop
from nac_test.utils.cleanup import (
    cleanup_pyats_output_dir,
    cleanup_pyats_runtime,
)
from nac_test.utils.controller import detect_controller_type
from nac_test.utils.device_validation import (
    REQUIRED_DEVICE_FIELDS,
    validate_device_inventory,
)
from nac_test.utils.environment import EnvironmentValidator
from nac_test.utils.file_discovery import find_data_file
from nac_test.utils.logging import VerbosityLevel, configure_logging
from nac_test.utils.system_resources import SystemResourceCalculator
from nac_test.utils.terminal import terminal

__all__ = [
    "terminal",
    "SystemResourceCalculator",
    "EnvironmentValidator",
    "cleanup_pyats_runtime",
    "cleanup_pyats_output_dir",
    "configure_logging",
    "VerbosityLevel",
    # Asyncio utilities (cross-version compatibility)
    "get_or_create_event_loop",
    # Device validation utilities (SSH/D2D architecture)
    "REQUIRED_DEVICE_FIELDS",
    "validate_device_inventory",
    # File discovery utilities (SSH/D2D architecture)
    "find_data_file",
    # Controller detection utilities (SSH/D2D architecture)
    "detect_controller_type",
]
