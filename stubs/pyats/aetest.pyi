"""Type stubs for pyats.aetest module."""

from abc import ABC
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

class Testcase(ABC):
    """Base class for test cases."""

    parent: Any  # Parent test object

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def passed(self, reason: str = "", *args: Any, **kwargs: Any) -> None: ...
    def failed(self, reason: str = "", *args: Any, **kwargs: Any) -> None: ...
    def skipped(self, reason: str = "", *args: Any, **kwargs: Any) -> None: ...
    def errored(self, reason: str = "", *args: Any, **kwargs: Any) -> None: ...
    def blocked(self, reason: str = "", *args: Any, **kwargs: Any) -> None: ...
    def aborted(self, reason: str = "", *args: Any, **kwargs: Any) -> None: ...
    def passx(self, reason: str = "", *args: Any, **kwargs: Any) -> None: ...

class CommonSetup(Testcase):
    """Common setup class."""

    pass

class CommonCleanup(Testcase):
    """Common cleanup class."""

    pass

def setup(f: F) -> F:
    """Setup decorator."""
    ...

def cleanup(f: F) -> F:
    """Cleanup decorator."""
    ...

def test(f: F) -> F:
    """Test decorator."""
    ...

def subsection(f: F) -> F:
    """Subsection decorator."""
    ...

def skip(reason: str) -> Callable[[F], F]:
    """Skip decorator."""
    ...
