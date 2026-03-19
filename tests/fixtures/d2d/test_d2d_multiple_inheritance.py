"""Test D2D multiple inheritance with mixin classes.

This fixture validates that the resolver correctly detects D2D test type
when multiple inheritance is used with mixins.
"""

from nac_test.pyats_core.common.ssh_base_test import SSHTestBase


class DeviceLogMixin:
    """Helper mixin for device logging - not a test base class."""

    def log_command(self, cmd: str) -> None:
        """Log a device command."""
        print(f"COMMAND: {cmd}")


class TestWithMixin(DeviceLogMixin, SSHTestBase):
    """D2D test with mixin first, base class second."""

    def test_with_mixin(self) -> None:
        """Test that D2D detection works when mixin comes first."""
        pass
