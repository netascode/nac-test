# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Test attribute-style base class references.

This fixture validates detection of qualified/attribute-style inheritance
where the base class is referenced as module.ClassName rather than just ClassName.
"""

import nac_test.pyats_core.common.base_test


class TestWithAttribute(nac_test.pyats_core.common.base_test.NACTestBase):
    """Uses fully qualified attribute reference."""

    def test_attribute_style(self) -> None:
        """Test that attribute-style inheritance is detected."""
        pass
