# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Shared fixtures for integration tests."""

import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def temp_relative_output_dir() -> Generator[str, None, None]:
    """Create a temporary directory under the current working directory.

    Yields a *relative* path string (relative to cwd). Integration tests use
    this alongside ``tmp_path`` (which yields an absolute path) to exercise
    that the CLI handles both absolute and relative ``-o`` arguments correctly.

    Yields:
        str: Relative path string to the created directory.
    """
    cwd = Path.cwd()
    temp_dir = Path(tempfile.mkdtemp(dir=cwd, prefix="__nac_tmp_"))
    try:
        yield str(temp_dir.relative_to(cwd))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
