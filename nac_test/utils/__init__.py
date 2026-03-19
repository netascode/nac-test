# -*- coding: utf-8 -*-

"""Utility modules for nac-test framework."""

from nac_test.utils.terminal import terminal
from nac_test.utils.system_resources import SystemResourceCalculator
from nac_test.utils.environment import EnvironmentValidator
from nac_test.utils.cleanup import cleanup_pyats_runtime, cleanup_old_test_outputs
from nac_test.utils.logging import configure_logging, VerbosityLevel
from nac_test.utils.device_validation import (
    REQUIRED_DEVICE_FIELDS,
    validate_device_inventory,
)
from nac_test.utils.file_discovery import find_data_file
from nac_test.utils.controller import detect_controller_type

__all__ = [
    "terminal",
    "SystemResourceCalculator",
    "EnvironmentValidator",
    "cleanup_pyats_runtime",
    "cleanup_old_test_outputs",
    "configure_logging",
    "VerbosityLevel",
    # Device validation utilities (SSH/D2D architecture)
    "REQUIRED_DEVICE_FIELDS",
    "validate_device_inventory",
    # File discovery utilities (SSH/D2D architecture)
    "find_data_file",
    # Controller detection utilities (SSH/D2D architecture)
    "detect_controller_type",
]
