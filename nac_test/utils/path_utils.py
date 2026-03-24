# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Path utilities for PyATS test name computation."""

from pathlib import Path


def derive_test_name(testscript_path: Path, test_dir: Path, fallback: str) -> str:
    """Derive a dot-notation test name from a testscript path relative to test_dir.

    Converts a testscript path such as ``/tests/api/tenants/verify.py`` to a
    dot-notation name like ``api.tenants.verify`` by computing the path relative
    to *test_dir* and joining all parts (without the file extension) with dots.

    Args:
        testscript_path: Absolute path to the test script file.
        test_dir: Root test directory used as the base for relative computation.
        fallback: Value to return when the path cannot be made relative to test_dir.

    Returns:
        Dot-notation test name, or *fallback* if testscript_path is not under test_dir.
    """
    try:
        relative_path = testscript_path.absolute().relative_to(test_dir.absolute())
        return ".".join((*relative_path.parts[:-1], relative_path.stem))
    except ValueError:
        return fallback
