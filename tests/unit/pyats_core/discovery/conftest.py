# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Shared helpers for discovery tests."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

# Fixtures directory: tests/fixtures/ (relative to tests/unit/pyats_core/discovery/)
FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures"


def create_mock_path(path_str: str, content: str = "") -> Any:
    """Create a mock Path object for testing.

    Args:
        path_str: The path string to return from as_posix() and __str__()
        content: The file content to return from read_text()

    Returns:
        A MagicMock configured to behave like a Path object
    """
    mock = MagicMock()
    mock.absolute.return_value = mock
    mock.as_posix.return_value = path_str
    mock.read_text.return_value = content
    mock.__str__ = MagicMock(return_value=path_str)  # type: ignore[method-assign]
    mock.name = Path(path_str).name
    return mock
