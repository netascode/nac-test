# -*- coding: utf-8 -*-

"""PyATS test discovery functionality.

This module handles discovering and categorizing PyATS test files
based on directory structure (api/ vs d2d/).
"""

from pathlib import Path
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class TestDiscovery:
    """Handles PyATS test file discovery and categorization."""

    def __init__(self, test_dir: Path):
        """Initialize test discovery.

        Args:
            test_dir: Root directory containing test files
        """
        self.test_dir = Path(test_dir)

    def discover_pyats_tests(self) -> Tuple[List[Path], List[Tuple[Path, str]]]:
        """Find all .py test files when --pyats flag is set

        Searches for Python test files in the test directory structure.
        Supports both traditional paths (test/operational/) and
        categorized paths (test/api/operational/, test/d2d/operational/).

        Excludes utility directories and non-test files.
        Validates files are readable and appear to contain test code.

        Returns:
            Tuple of (test_files, skipped_files) where skipped_files contains
            tuples of (path, reason) for each skipped file
        """
        test_files = []
        skipped_files = []

        # Use rglob for recursive search - finds .py files at any depth
        for test_path in self.test_dir.rglob("*.py"):
            # Skip non-test files
            if "__pycache__" in str(test_path):
                continue
            if test_path.name.startswith("_"):
                continue
            if test_path.name == "__init__.py":
                continue

            # Convert to string for efficient path checking
            path_str = str(test_path)

            # Include files in standard test directories
            # This supports paths like:
            # - /test/operational/
            # - /test/api/operational/
            # - /test/d2d/operational/
            # - /tests/api/
            # - /tests/d2d/
            if "/test/" in path_str or "/tests/" in path_str:
                # Exclude utility directories
                if "pyats_common" not in path_str and "jinja_filters" not in path_str:
                    # Try to validate the file
                    try:
                        # Quick validation - check if file is readable and has test indicators
                        content = test_path.read_text()

                        # Check for PyATS test indicators
                        if not ("aetest" in content or "from pyats" in content):
                            logger.debug(
                                f"Skipping {test_path}: No PyATS imports found"
                            )
                            skipped_files.append((test_path, "No PyATS imports"))
                            continue

                        # Check for test classes or functions
                        if not ("class" in content or "def test" in content):
                            logger.debug(
                                f"Skipping {test_path}: No test classes or functions found"
                            )
                            skipped_files.append((test_path, "No test definitions"))
                            continue

                        test_files.append(test_path.resolve())

                    except Exception as e:
                        # File read error - warn and skip
                        rel_path = test_path.relative_to(self.test_dir)
                        reason = f"{type(e).__name__}: {str(e)}"
                        logger.warning(f"Skipping {rel_path}: {reason}")
                        skipped_files.append((test_path, reason))
                        continue

        # Log summary of skipped files if any
        if skipped_files:
            logger.info(f"Skipped {len(skipped_files)} file(s) during discovery:")
            for path, reason in skipped_files[:5]:  # Show first 5
                logger.debug(f"  - {path.name}: {reason}")
            if len(skipped_files) > 5:
                logger.debug(f"  ... and {len(skipped_files) - 5} more")

        return sorted(test_files), skipped_files

    def categorize_tests_by_type(
        self, test_files: List[Path]
    ) -> Tuple[List[Path], List[Path]]:
        """Categorize test files based on directory structure.

        Tests MUST be in either 'api/' or 'd2d/' directories.
        Raises error if tests are found outside these directories.

        Args:
            test_files: List of discovered test file paths

        Returns:
            Tuple of (api_tests, d2d_tests)

        Raises:
            ValueError: If tests are found outside of api/ or d2d/ directories
        """
        api_tests = []
        d2d_tests = []
        uncategorized = []

        for test_file in test_files:
            path_str = str(test_file)

            # Check for directory markers anywhere in path
            if "/api/" in path_str:
                api_tests.append(test_file)
            elif "/d2d/" in path_str:
                d2d_tests.append(test_file)
            else:
                uncategorized.append(test_file)

        # Raise error if any tests are not properly categorized
        if uncategorized:
            # Show first 5 files as examples
            example_files = "\n".join(f"  - {f}" for f in uncategorized[:5])
            if len(uncategorized) > 5:
                example_files += f"\n  ... and {len(uncategorized) - 5} more"

            raise ValueError(
                f"Found {len(uncategorized)} test file(s) outside of 'api/' or 'd2d/' directories:\n"
                f"{example_files}\n\n"
                "All tests must be organized under:\n"
                "  - 'api/' for API-based tests\n"
                "  - 'd2d/' for direct-to-device (SSH-based) tests"
            )

        # Log the categorization results
        logger.info(f"Categorized tests: {len(api_tests)} API, {len(d2d_tests)} D2D")

        return api_tests, d2d_tests
