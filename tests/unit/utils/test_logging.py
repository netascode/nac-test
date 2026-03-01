# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for nac_test.utils.logging module.

This module tests the logging utilities, covering:
- VERBOSITY_TO_LOGLEVEL mapping from VerbosityLevel to Python logging levels
- Completeness of the mapping for all VerbosityLevel enum values
"""

import logging

import pytest

from nac_test.utils.logging import VERBOSITY_TO_LOGLEVEL, VerbosityLevel


@pytest.mark.parametrize(
    "verbosity,expected_loglevel",
    [
        (VerbosityLevel.DEBUG, logging.DEBUG),
        (VerbosityLevel.INFO, logging.INFO),
        (VerbosityLevel.WARNING, logging.WARNING),
        (VerbosityLevel.ERROR, logging.ERROR),
        (VerbosityLevel.CRITICAL, logging.CRITICAL),
    ],
)
def test_verbosity_to_loglevel_mapping(
    verbosity: VerbosityLevel, expected_loglevel: int
) -> None:
    """Test that VERBOSITY_TO_LOGLEVEL maps all VerbosityLevel values correctly."""
    assert VERBOSITY_TO_LOGLEVEL[verbosity] == expected_loglevel


def test_all_verbosity_levels_mapped() -> None:
    """Test that all VerbosityLevel enum values have a mapping."""
    for verbosity in VerbosityLevel:
        assert verbosity in VERBOSITY_TO_LOGLEVEL
