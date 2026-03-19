"""Test import aliasing - falls back to directory detection.

This fixture tests the documented limitation where import aliasing
(renaming classes on import) prevents AST detection. The resolver
should fall back to directory-based detection in this case.

Note: This is a known limitation documented in the PRD.
"""

from nac_test.pyats_core.common.base_test import NACTestBase as BaseTest


class TestAliased(BaseTest):
    """Uses aliased import - detection should NOT work via AST.

    The resolver will not find 'BaseTest' in BASE_CLASS_MAPPING because
    the mapping only contains 'NACTestBase'. This will trigger fallback
    to directory-based detection.
    """

    def test_aliased(self) -> None:
        """Test aliased import handling."""
        pass
