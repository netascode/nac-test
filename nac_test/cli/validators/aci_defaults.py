# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""ACI defaults file validation for CLI.

This module provides validation to detect when users forget to pass the
ACI defaults file when running tests in an ACI environment. It fails fast
before the expensive data merge operation to save user time.
"""

import logging
import os
from pathlib import Path

import yaml  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# Environment variable that indicates ACI environment
ACI_URL_ENV_VAR = "ACI_URL"


def validate_aci_defaults(data_paths: list[Path]) -> bool:
    """Validate that ACI defaults file is provided when in ACI environment.

    This function performs a fast check to fail early when users forget to
    include the defaults file. It uses a two-stage approach:

    1. Quick path check: Look for "default"/"defaults" in path components
       (files must have .yaml/.yml extension) (instant)
    2. Content check: Peek inside YAML files for "defaults:" + "apic:" structure

    Design Rationale:
        This pre-merge validation catches the common mistake of forgetting
        ``-d ./defaults/`` before the expensive DataMerger operation runs.
        The overhead is minimal compared to the time saved when defaults are
        missing - users get immediate feedback instead of waiting for a full
        data merge before seeing the error.

    Args:
        data_paths: List of data file/directory paths provided via -d option.

    Returns:
        True if validation passes (not ACI environment, or defaults found).
        False if ACI environment detected AND no defaults structure found.
    """
    aci_url = os.environ.get(ACI_URL_ENV_VAR)
    if not aci_url:
        # Not an ACI environment, no validation needed
        return True

    # Stage 1: Quick path-based check (instant)
    # Look for "default" or "defaults" in path components with proper specificity
    for path in data_paths:
        if _path_looks_like_defaults(path):
            return True

    # Stage 2: Content-based check (peek inside YAML files)
    # This catches cases where user has valid defaults in a non-standard path
    # e.g., -d ./my_aci_config.yaml where the file contains defaults.apic
    for path in data_paths:
        if _path_contains_defaults_structure(path):
            return True

    return False


def _path_looks_like_defaults(path: Path) -> bool:
    """Quick heuristic check if a path looks like it contains defaults.

    This is a fast pre-filter that checks path components without file I/O.

    For files: Check if filename contains "default" or "defaults" AND has .yaml/.yml extension
    For directories: Check if any directory component is named "default" or "defaults"

    Args:
        path: A file or directory path to check.

    Returns:
        True if the path looks like it might contain defaults based on naming conventions.

    Examples:
        >>> _path_looks_like_defaults(Path("/path/to/defaults.yaml"))
        True
        >>> _path_looks_like_defaults(Path("/path/to/defaults/"))
        True
        >>> _path_looks_like_defaults(Path("/path/to/my-defaults-backup.txt"))
        False  # Not a YAML file
        >>> _path_looks_like_defaults(Path("/users/defaultuser/config.yaml"))
        False  # "default" not as standalone directory component
    """
    # Check if it's a file with YAML extension
    if path.is_file() or path.suffix in (".yaml", ".yml"):
        # Check if filename (not full path) contains "default" or "defaults"
        filename_lower = path.name.lower()
        if path.suffix in (".yaml", ".yml") and ("default" in filename_lower):
            return True

    # Check if any directory component is exactly "default" or "defaults"
    for part in path.parts:
        if part.lower() in ("default", "defaults"):
            return True

    return False


def _path_contains_defaults_structure(path: Path) -> bool:
    """Check if a path (file or directory) contains the defaults.apic structure.

    For YAML files, this function parses the document using yaml.safe_load()
    to verify the actual structure (defaults.apic exists as nested keys).
    For directories, it scans all YAML files within (non-recursively).

    Args:
        path: A file or directory path to check.

    Returns:
        True if the defaults.apic structure is found.
    """
    if path.is_file() and path.suffix in (".yaml", ".yml"):
        return _file_contains_defaults_structure(path)
    elif path.is_dir():
        # Check all YAML files in directory (non-recursive for performance)
        for extension in ("*.yaml", "*.yml"):
            for yaml_file in path.glob(extension):
                if _file_contains_defaults_structure(yaml_file):
                    return True
    return False


def _file_contains_defaults_structure(file_path: Path) -> bool:
    """Check if a single YAML file contains the defaults.apic structure.

    Uses YAML parsing to verify actual document structure, avoiding false
    positives from string matching (e.g., comments, string values).

    Performance:
        - Skips files larger than 3MB to prevent memory exhaustion when loading YAML

    Args:
        file_path: Path to a YAML file.

    Returns:
        True if the file contains a 'defaults' key with an 'apic' sub-key.
    """
    try:
        # Performance: Skip oversized files to prevent memory exhaustion
        # ACI YAML files can be large (2-3MB), but anything beyond that risks hanging the CLI
        file_size = file_path.stat().st_size
        if file_size > 3 * 1024 * 1024:  # 3MB limit for ACI defaults validation
            logger.warning(
                "Skipping oversized file (%d bytes) during ACI defaults scan to prevent memory exhaustion: %s",
                file_size,
                file_path,
            )
            return False

        content = file_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)

        # Verify actual YAML structure: data['defaults']['apic']
        if isinstance(data, dict):
            defaults = data.get("defaults")
            if isinstance(defaults, dict):
                return "apic" in defaults
        return False

    except (yaml.YAMLError, OSError, UnicodeDecodeError):
        # If we can't read or parse the file, skip it
        return False
