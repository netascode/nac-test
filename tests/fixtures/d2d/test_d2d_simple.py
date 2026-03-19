"""Simple D2D test with direct SSHTestBase inheritance.

This fixture tests the most basic D2D/SSH test detection scenario - a single
class inheriting directly from SSHTestBase.
"""

from nac_test.pyats_core.common.ssh_base_test import SSHTestBase


class TestShowVersion(SSHTestBase):
    """Test device version via SSH."""

    def test_version_output(self) -> None:
        """Verify show version command output."""
        pass
