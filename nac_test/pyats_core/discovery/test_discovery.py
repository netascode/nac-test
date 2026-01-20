# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# -*- coding: utf-8 -*-

"""PyATS test discovery functionality.

This module handles discovering and categorizing PyATS test files.
Test type detection uses a three-tier strategy:

    1. **Static Analysis** (Primary): AST-based detection of base class inheritance
    2. **Directory Structure** (Fallback): Checks for /api/ or /d2d/ in path
    3. **Default** (Last Resort): Falls back to 'api' with warning

This allows flexible test organization - tests can be placed in any directory
structure and will be automatically classified based on their base class
inheritance (e.g., NACTestBase -> api, SSHTestBase -> d2d).
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class TestDiscovery:
    """Handles PyATS test file discovery and categorization."""

    def __init__(self, test_dir: Path):
        """Initialize test discovery.

        Args:
            test_dir: Root directory containing test files
        """
        self.test_dir = Path(test_dir)

    def discover_pyats_tests(self) -> tuple[list[Path], list[tuple[Path, str]]]:
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
        self, test_files: list[Path]
    ) -> tuple[list[Path], list[Path]]:
        """Categorize discovered test files into API and D2D tests.

        Uses static analysis with directory fallback for maximum flexibility
        with zero user configuration.

        Detection Strategy (Priority Order):
            1. **Static Analysis**: Examines base class inheritance via AST
               - NACTestBase, APICTestBase, etc. -> 'api'
               - SSHTestBase, IOSXETestBase, etc. -> 'd2d'
            2. **Directory Fallback**: Checks for /api/ or /d2d/ in path
            3. **Default**: Falls back to 'api' with warning

        This approach allows tests to be organized by feature/domain rather
        than requiring rigid /api/ and /d2d/ directory structure, while
        maintaining 100% backward compatibility with existing projects.

        Args:
            test_files: List of discovered test file paths

        Returns:
            Tuple of (api_tests, d2d_tests)

        Example:
            ```python
            discovery = TestDiscovery(Path("/tests"))
            files, _ = discovery.discover_pyats_tests()
            api_tests, d2d_tests = discovery.categorize_tests_by_type(files)
            ```
        """
        # Lazy import to avoid circular dependencies
        from .test_type_resolver import TestTypeResolver

        resolver = TestTypeResolver(self.test_dir)
        api_tests: list[Path] = []
        d2d_tests: list[Path] = []

        for test_file in test_files:
            test_type = resolver.resolve(test_file)

            if test_type == "api":
                api_tests.append(test_file)
            else:  # "d2d"
                d2d_tests.append(test_file)

        logger.info(
            f"Categorized {len(api_tests)} API tests and {len(d2d_tests)} D2D tests"
        )

        return api_tests, d2d_tests
