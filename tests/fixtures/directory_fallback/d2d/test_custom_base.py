# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Test in /d2d/ directory with custom base for fallback testing.

This fixture has a class with a custom base class but is located
in a directory with '/d2d/' in its path. The resolver should:
1. Fail AST-based detection (custom base not in mapping)
2. Fall back to directory detection
3. Return 'd2d' based on the /d2d/ directory path
"""


class MyCustomDeviceTest:
    """Custom base not in BASE_CLASS_MAPPING."""

    pass


class TestDeviceCustom(MyCustomDeviceTest):
    """Should be detected as 'd2d' via directory fallback."""

    def test_device(self) -> None:
        """Test directory fallback to D2D."""
        pass
