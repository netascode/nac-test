# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Archive security utilities for PyATS reporting.

This module provides shared security functions for archive operations,
including Zip Slip vulnerability protection.
"""

import zipfile
from pathlib import Path


def validate_archive_paths(zip_file: zipfile.ZipFile, extract_dir: Path) -> None:
    """Validate archive paths to prevent Zip Slip vulnerability.

    Zip Slip is a vulnerability that allows attackers to write files outside
    the intended extraction directory using path traversal sequences like
    "../" in archive member names.

    This function validates that all archive members will be extracted to
    paths within the intended extraction directory.

    Args:
        zip_file: The opened zip file to validate.
        extract_dir: Target extraction directory.

    Raises:
        ValueError: If any archive member contains path traversal that would
            result in extraction outside the target directory.

    Example:
        >>> with zipfile.ZipFile("archive.zip", "r") as zf:
        ...     validate_archive_paths(zf, Path("/tmp/extract"))
        ...     zf.extractall(Path("/tmp/extract"))
    """
    resolved_extract_dir = extract_dir.resolve()
    for member in zip_file.namelist():
        member_path = (resolved_extract_dir / member).resolve()
        if not str(member_path).startswith(str(resolved_extract_dir)):
            raise ValueError(f"Path traversal detected in archive member: {member}")
