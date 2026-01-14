# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Test that comments and strings don't interfere with detection.

This fixture validates that the AST-based parser correctly ignores:
- Class definitions in comments
- Class definitions in docstrings
- Class definitions in string literals

Only the actual code should be analyzed.
"""

from nac_test.pyats_core.common.ssh_base_test import SSHTestBase

# This comment mentions NACTestBase but shouldn't affect detection
# class FakeTest(NACTestBase):
#     pass

"""
This docstring also contains a fake class that should be ignored:

    class AnotherFake(NACTestBase):
        '''This is in a docstring'''
        pass

The parser should NOT detect NACTestBase from this docstring.
"""

example_code = """
class StringTest(NACTestBase):
    '''This is inside a string literal and should be ignored'''
    pass
"""


class RealTest(SSHTestBase):
    """The only real test class - should detect as D2D."""

    def test_real_method(self) -> None:
        """Test that only real classes are detected."""
        # Comment with NACTestBase shouldn't matter
        fake_base = "NACTestBase"  # String with base name shouldn't matter
        pass
