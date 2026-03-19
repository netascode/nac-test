"""Test file with no recognized base class.

This fixture contains classes that do not inherit from any recognized
test base classes. The resolver should raise NoRecognizedBaseError and
fall back to directory-based detection.
"""


class CustomBase:
    """Custom base class - not in BASE_CLASS_MAPPING."""

    pass


class TestUnknown(CustomBase):
    """Inherits from custom base - no detection possible via AST."""

    def test_unknown(self) -> None:
        """Test unknown base handling."""
        pass


class StandaloneTest:
    """A class with no inheritance at all."""

    def test_standalone(self) -> None:
        """Test no inheritance handling."""
        pass
