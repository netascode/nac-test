# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Test multi-line class definition parsing.

This fixture validates that AST parsing correctly handles class definitions
that span multiple lines with various formatting styles.
"""

from nac_test.pyats_core.common.base_test import NACTestBase


class TestComplexInheritance(
    NACTestBase,
    dict,  # type: ignore[type-arg]
):
    """Class definition spans multiple lines with multiple bases."""

    def test_multiline_parsing(self) -> None:
        """Test that multi-line definitions are parsed correctly."""
        pass


class TestWithParentheses(NACTestBase):
    """Single inheritance with parentheses on multiple lines."""

    pass
