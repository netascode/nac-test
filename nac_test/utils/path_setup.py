"""
Path setup utilities for nac-test test execution.

This module provides functions to configure Python paths for test imports,
supporting potential different styles within a /tests directory structure.
"""

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def find_tests_directory(path: str | Path) -> Path:
    """
    Find the /tests directory in the path hierarchy.

    Args:
        path: Starting path (file or directory)

    Returns:
        Path to the tests directory

    Raises:
        ValueError: If no /tests directory is found in the path hierarchy
    """
    current = Path(path).resolve()

    for parent in [current] + list(current.parents):
        if parent.name == "tests":
            logger.debug(f"Found tests directory: {parent}")
            return parent

    raise ValueError(
        f"No 'tests' directory found in path hierarchy of {path}. "
        "Test files must be located under a /tests directory."
    )


def determine_import_path(test_path: str | Path) -> Path:
    """
    Determine the correct path to add to sys.path based on import style detection.

    Supports two import styles:
    - 'from tests.module import ...' -> needs parent of /tests
    - 'from templates.module import ...' -> needs /tests itself

    Args:
        test_path: Path to a test file or directory under /tests

    Returns:
        Path that should be added to sys.path for imports to work

    Raises:
        ValueError: If the path structure is invalid
    """
    tests_dir = find_tests_directory(test_path)

    # Check if /tests has importable subdirectories
    # Look for directories with __init__.py that aren't common test directories
    modern_style_indicators = ["templates", "filters", "jinja_filters"]

    for item in tests_dir.iterdir():
        if (
            item.is_dir()
            and item.name in modern_style_indicators
            and (item / "__init__.py").exists()
        ):
            logger.debug(f"Detected modern import style with '{item.name}' directory")
            return tests_dir

    # Default to (imports from tests.*)
    logger.debug("Using legacy import style")
    return tests_dir.parent


def add_tests_parent_to_syspath(path: str | Path) -> None:
    """
    Add the appropriate parent directory to sys.path for test imports.

    This function is used for dynamic imports in the main process.
    It's idempotent - safe to call multiple times.

    Args:
        path: Path to a test file or directory under /tests

    Raises:
        ValueError: If the path structure is invalid
    """
    try:
        import_path = determine_import_path(path)
        path_str = str(import_path)

        if path_str not in sys.path:
            logger.info(f"Adding to sys.path: {import_path}")
            sys.path.insert(0, path_str)
        else:
            logger.debug(f"Path already in sys.path: {import_path}")

    except ValueError as e:
        logger.error(f"Failed to set up import path: {e}")
        raise


def get_pythonpath_for_tests(
    test_dir: str | Path,
    extra_dirs: list[str | Path] | None = None,
) -> str:
    """
    Build PYTHONPATH string for subprocess execution.

    Creates a complete PYTHONPATH that includes:
    1. The appropriate import path for the test directory
    2. Any additional directories (e.g., nac-test source)
    3. The existing PYTHONPATH from the environment

    Args:
        test_dir: Directory containing test files
        extra_dirs: Additional directories to include in PYTHONPATH

    Returns:
        Colon-separated (or semicolon on Windows) PYTHONPATH string

    Raises:
        ValueError: If the test directory structure is invalid
    """
    paths: list[str] = []

    # Add the appropriate import path for tests
    try:
        import_path = determine_import_path(test_dir)
        paths.append(str(import_path))
    except ValueError as e:
        logger.error(f"Invalid test directory structure: {e}")
        raise

    # Add any extra directories
    if extra_dirs:
        for extra_dir in extra_dirs:
            dir_path = str(Path(extra_dir).resolve())
            if dir_path not in paths:
                paths.append(dir_path)

    # Preserve existing PYTHONPATH
    existing = os.environ.get("PYTHONPATH")
    if existing:
        # Add existing paths that aren't already included
        for existing_path in existing.split(os.pathsep):
            if existing_path and existing_path not in paths:
                paths.append(existing_path)

    return os.pathsep.join(paths)
