"""Simple API test with direct NACTestBase inheritance.

This fixture tests the most basic API test detection scenario - a single class
inheriting directly from NACTestBase (the generic API test base class).
"""

from nac_test.pyats_core.common.base_test import NACTestBase


class TestTenant(NACTestBase):
    """Test tenant configuration using API."""

    def test_tenant_exists(self) -> None:
        """Verify tenant exists in controller."""
        pass
