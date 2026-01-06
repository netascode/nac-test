"""Test in /api/ directory with unknown base for fallback testing.

This fixture has a class with an unknown base class but is located
in a directory with '/api/' in its path. The resolver should:
1. Fail AST-based detection (unknown base)
2. Fall back to directory detection
3. Return 'api' based on the /api/ directory path
"""


class CompletelyCustomBase:
    """Not a recognized base class."""

    pass


class TestUnknownInApiDir(CompletelyCustomBase):
    """Should be detected as 'api' via directory fallback."""

    def test_something(self) -> None:
        """Test directory fallback to API."""
        pass
