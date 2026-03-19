"""Test multi-line D2D class definition parsing.

This fixture validates that AST parsing correctly handles D2D test class
definitions that span multiple lines.
"""

from nac_test.pyats_core.common.ssh_base_test import SSHTestBase


class TestComplexDevice(
    SSHTestBase,
):
    """D2D test class definition spans multiple lines."""

    def test_complex_device(self) -> None:
        """Test multi-line D2D class detection."""
        pass
