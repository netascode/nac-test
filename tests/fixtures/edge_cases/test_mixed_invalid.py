"""Invalid test file with both API and D2D classes.

This fixture is intentionally invalid - it contains classes that inherit from
both API (NACTestBase) and D2D (SSHTestBase) base classes. The resolver should
raise a ValueError when encountering this file.

This is an error case that users should avoid - tests should not mix API and
D2D test classes in the same file.
"""

from nac_test.pyats_core.common.base_test import NACTestBase
from nac_test.pyats_core.common.ssh_base_test import SSHTestBase


class TestAPI(NACTestBase):
    """API test class."""

    def test_api_method(self) -> None:
        """Test API method."""
        pass


class TestSSH(SSHTestBase):
    """SSH test class in same file - INVALID."""

    def test_ssh_method(self) -> None:
        """Test SSH method."""
        pass
