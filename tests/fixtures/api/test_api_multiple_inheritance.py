"""Test multiple inheritance with mixin classes.

This fixture validates that the resolver correctly detects the test type
when multiple inheritance is used, regardless of base class order.
"""

from nac_test.pyats_core.common.base_test import NACTestBase


class LoggingMixin:
    """Helper mixin for logging - not a test base class."""

    def log_info(self, msg: str) -> None:
        """Log an info message."""
        print(f"INFO: {msg}")


class TestWithMixinFirst(LoggingMixin, NACTestBase):
    """Test with mixin first, base class second."""

    def test_with_mixin(self) -> None:
        """Test that detection works when mixin comes first."""
        pass


class TestBaseFirst(NACTestBase, LoggingMixin):
    """Test with base class first, mixin second."""

    def test_base_first(self) -> None:
        """Test that detection works when base comes first."""
        pass
