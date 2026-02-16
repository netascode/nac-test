# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""PyATS test discovery functionality.

This module handles discovering and categorizing PyATS test files.

Discovery identifies PyATS tests by checking for:
    - Import from nac_test or nac_test_pyats_common
    - Presence of @aetest.test, @aetest.setup, or @aetest.cleanup decorators

Test type detection uses a three-tier strategy:
    1. **Static Analysis** (Primary): AST-based detection of base class inheritance
    2. **Directory Structure** (Fallback): Checks for /api/ or /d2d/ in path
    3. **Default** (Last Resort): Falls back to 'api' with warning
"""

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class TestDiscovery:
    """Handles PyATS test file discovery and categorization."""

    # PyATS test markers
    # using regex to avoid matching the terms in comments/strings
    # use multiple statements to provide good granularity for skip
    # reasons in logging
    _PYATS_IMPORT_PATTERN = re.compile(
        r"^\s*(?:from|import)\s+(?:nac_test|nac_test_pyats_common)\b",
        re.MULTILINE,
    )
    _PYATS_DECORATOR_PATTERN = re.compile(
        r"^\s*@aetest\.(test|setup|cleanup)\b",
        re.MULTILINE,
    )

    def __init__(self, test_dir: Path, exclude_paths: list[Path] | None = None):
        """Initialize test discovery.

        Args:
            test_dir: Root directory containing test files
            exclude_paths: Directories to exclude from discovery (e.g., filters, jinja tests)
        """
        self.test_dir = Path(test_dir)
        self.exclude_paths = [Path(p).resolve() for p in (exclude_paths or [])]

    def _is_excluded(self, path: Path) -> bool:
        """Check if path is within any excluded directory."""
        resolved = path.resolve()
        for excluded in self.exclude_paths:
            try:
                resolved.relative_to(excluded)
                return True
            except ValueError:
                continue
        return False

    def _should_skip_path(self, filename: str, test_path: Path) -> bool:
        """Check if a path should be skipped based on name/location.

        Args:
            filename: The filename to check
            test_path: Full path to the file

        Returns:
            True if the path should be skipped
        """
        if "__pycache__" in str(test_path):
            return True
        # Skip private/internal files (also covers __init__.py)
        if filename.startswith("_"):
            return True
        if self._is_excluded(test_path):
            return True
        return False

    def _is_valid_pyats_test(self, content: str) -> tuple[bool, str | None]:
        """Check if file content represents a valid PyATS test.

        Args:
            content: File content to check

        Returns:
            Tuple of (is_valid, skip_reason). skip_reason is None if valid.
        """
        if not self._PYATS_IMPORT_PATTERN.search(content):
            return False, "No nac_test imports"
        if not self._PYATS_DECORATOR_PATTERN.search(content):
            return False, "No @aetest decorators"
        return True, None

    def has_pyats_tests(self) -> bool:
        """Check if at least one PyATS test exists.

        Uses os.walk for true early exit from directory traversal.
        More efficient than discover_pyats_tests() when only existence check is needed.

        Returns:
            True if at least one valid PyATS test file exists
        """
        for dirpath, _, filenames in os.walk(self.test_dir):
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                test_path = Path(dirpath) / filename
                if self._should_skip_path(filename, test_path):
                    continue
                try:
                    content = test_path.read_text()
                    is_valid, _ = self._is_valid_pyats_test(content)
                    if is_valid:
                        return True
                except (OSError, UnicodeDecodeError) as e:
                    rel_path = test_path.relative_to(self.test_dir)
                    reason = f"{type(e).__name__}: {str(e)}"
                    logger.debug(f"Skipping {rel_path}: {reason}")
        return False

    def discover_pyats_tests(self) -> tuple[list[Path], list[tuple[Path, str]]]:
        """Find all PyATS test files in the test directory.

        Searches for Python files and validates them as PyATS tests by checking
        for nac_test imports and @aetest decorators.

        Returns:
            Tuple of (test_files, skipped_files) where skipped_files contains
            tuples of (path, reason) for each skipped file
        """
        test_files: list[Path] = []
        skipped_files: list[tuple[Path, str]] = []

        for test_path in self.test_dir.rglob("*.py"):
            if self._should_skip_path(test_path.name, test_path):
                continue

            try:
                content = test_path.read_text()
                is_valid, skip_reason = self._is_valid_pyats_test(content)

                if not is_valid:
                    assert (
                        skip_reason is not None
                    )  # mypy: skip_reason is set when invalid
                    logger.debug(f"Skipping {test_path}: {skip_reason}")
                    skipped_files.append((test_path, skip_reason))
                    continue

                test_files.append(test_path.resolve())

            except (OSError, UnicodeDecodeError) as e:
                rel_path = test_path.relative_to(self.test_dir)
                reason = f"{type(e).__name__}: {str(e)}"
                logger.warning(f"Skipping {rel_path}: {reason}")
                skipped_files.append((test_path, reason))
                continue

        if skipped_files:
            logger.info(f"Skipped {len(skipped_files)} file(s) during discovery:")
            for path, reason in skipped_files[:5]:
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

        Args:
            test_files: List of discovered test file paths

        Returns:
            Tuple of (api_tests, d2d_tests)
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
            else:
                d2d_tests.append(test_file)

        logger.info(
            f"Categorized {len(api_tests)} API tests and {len(d2d_tests)} D2D tests"
        )

        return api_tests, d2d_tests
