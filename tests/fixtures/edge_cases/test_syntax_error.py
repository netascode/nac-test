# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Test file with syntax error for graceful handling.

This fixture has intentional syntax errors to verify the resolver
handles malformed Python files gracefully and falls back to
directory-based detection.
"""

from nac_test.pyats_core.common.base_test import NACTestBase

class TestBroken(NACTestBase  # Missing closing parenthesis
    """This file has a syntax error."""

    def test_broken(self) -> None:
        pass
