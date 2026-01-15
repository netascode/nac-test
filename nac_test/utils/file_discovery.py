"""File discovery utilities for locating data files in the directory tree."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def find_data_file(
    filename: str,
    start_path: Path | None = None,
    search_dirs: list[str] | None = None,
    max_depth: int = 10,
) -> Path | None:
    """Find a data file by traversing up the directory tree.

    Starting from start_path (or cwd), traverse up the directory tree looking
    for the file in each level's subdirectories (data/, config/, etc).

    Args:
        filename: Name of the file to find (e.g., "config.yaml").
        start_path: Directory to start searching from. Defaults to cwd.
        search_dirs: Subdirectories to check at each level.
            Defaults to ["data", "config"].
        max_depth: Maximum levels to traverse up. Defaults to 10.

    Returns:
        Path object to the found file, or None if not found.

    Example:
        >>> config_path = find_data_file("config.yaml")
        >>> if config_path:
        ...     with open(config_path) as f:
        ...         config = yaml.safe_load(f)
    """
    # Set defaults
    if start_path is None:
        start_path = Path.cwd()
    if search_dirs is None:
        search_dirs = ["data", "config"]

    # Ensure start_path is absolute
    current_path = start_path.resolve()

    logger.debug(f"Starting file search for '{filename}' from {current_path}")
    logger.debug(f"Will search in subdirectories: {search_dirs}")
    logger.debug(f"Maximum depth: {max_depth}")

    depth = 0

    while depth < max_depth:
        # First check the current directory itself
        candidate = current_path / filename
        if candidate.exists() and candidate.is_file():
            logger.debug(f"Found '{filename}' at {candidate}")
            return candidate

        # Then check each search subdirectory
        for subdir in search_dirs:
            subdir_path = current_path / subdir
            if subdir_path.exists() and subdir_path.is_dir():
                candidate = subdir_path / filename
                if candidate.exists() and candidate.is_file():
                    logger.debug(f"Found '{filename}' at {candidate}")
                    return candidate

        # Move up one directory level
        parent = current_path.parent

        # Check if we've reached the root
        if parent == current_path:
            logger.debug(f"Reached root directory without finding '{filename}'")
            break

        current_path = parent
        depth += 1
        logger.debug(f"Moving up to {current_path} (depth {depth})")

    if depth >= max_depth:
        logger.debug(f"Reached maximum depth {max_depth} without finding '{filename}'")

    logger.debug(f"File '{filename}' not found after searching {depth} levels")
    return None
