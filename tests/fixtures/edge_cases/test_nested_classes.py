"""Test nested class handling.

This fixture validates that the resolver only examines top-level classes
(using tree.body) and does not detect nested classes inside other classes.
"""

from nac_test.pyats_core.common.base_test import NACTestBase
from nac_test.pyats_core.common.ssh_base_test import SSHTestBase


class OuterTest(NACTestBase):
    """Outer test class - should be detected as API."""

    class InnerSSHTest(SSHTestBase):
        """Nested class with D2D base - should be IGNORED.

        The resolver only looks at tree.body (top-level), so this nested
        class definition should not affect the test type detection.
        """

        pass

    def test_outer(self) -> None:
        """Test outer class detection."""
        pass
