"""Type stubs for pyats.topology module."""

from pathlib import Path
from typing import Any, Dict, Union

class Device:
    """Represents a testbed device."""

    name: str
    hostname: str
    connections: Dict[str, Any]

    def connect(self, **kwargs: Any) -> None: ...
    def disconnect(self, **kwargs: Any) -> None: ...
    def execute(self, command: str, **kwargs: Any) -> str: ...
    def is_connected(self) -> bool: ...

class Testbed:
    """Represents a pyATS testbed."""

    devices: Dict[str, Device]
    name: str

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def connect(self, **kwargs: Any) -> None: ...
    def disconnect(self, **kwargs: Any) -> None: ...

class loader:
    """Testbed loader utilities."""

    @staticmethod
    def load(testbed_file: Union[str, Path], **kwargs: Any) -> Testbed: ...
