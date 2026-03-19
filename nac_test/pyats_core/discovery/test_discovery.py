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

from nac_test.pyats_core.common.types import TestExecutionPlan, TestFileMetadata

from .tag_matcher import TagMatcher
from .test_type_resolver import TestMetadataResolver

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

    def discover_pyats_tests(
        self,
        include_tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
    ) -> TestExecutionPlan:
        """Discover, filter, and categorize PyATS tests into an execution plan.

        This is the primary entry point for test discovery. It performs:
        1. Discovery: Find all valid PyATS test files
        2. Filtering: Apply include/exclude tag patterns
        3. Categorization: Sort tests into API vs D2D based on base class

        The returned TestExecutionPlan carries all information needed for
        test execution and post-execution result analysis, including a
        pre-computed path-to-type mapping for O(1) lookups.

        Args:
            include_tags: Optional tag patterns to include (Robot Framework syntax).
                         If specified, only tests with matching groups are included.
            exclude_tags: Optional tag patterns to exclude (Robot Framework syntax).
                         Tests with matching groups are filtered out.

        Returns:
            TestExecutionPlan with categorized tests and lookup table
        """
        api_tests: list[TestFileMetadata] = []
        d2d_tests: list[TestFileMetadata] = []
        skipped_files: list[tuple[Path, str]] = []
        test_type_by_path: dict[Path, str] = {}

        tag_matcher = TagMatcher(include=include_tags, exclude=exclude_tags)
        resolver = TestMetadataResolver(self.test_dir)
        filtered_count = 0

        for test_path in self.test_dir.rglob("*.py"):
            if self._should_skip_path(test_path.name, test_path):
                continue

            try:
                content = test_path.read_text()
                is_valid, skip_reason = self._is_valid_pyats_test(content)

                if not is_valid:
                    assert skip_reason is not None
                    logger.debug(f"Skipping {test_path}: {skip_reason}")
                    skipped_files.append((test_path, skip_reason))
                    continue

                resolved_path = test_path.resolve()
                metadata = resolver.resolve(resolved_path)

                if tag_matcher.has_filters:
                    if not tag_matcher.should_include(metadata.groups):
                        logger.debug(
                            f"Filtered out {test_path.name} (groups={metadata.groups})"
                        )
                        filtered_count += 1
                        continue

                test_type_by_path[resolved_path] = metadata.test_type
                if metadata.test_type == "d2d":
                    d2d_tests.append(metadata)
                else:
                    api_tests.append(metadata)

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

        if filtered_count:
            logger.info(f"Filtered out {filtered_count} test(s) by tag patterns")

        api_tests.sort(key=lambda m: m.path)
        d2d_tests.sort(key=lambda m: m.path)

        logger.info(
            f"Categorized {len(api_tests)} API tests and {len(d2d_tests)} D2D tests"
        )

        return TestExecutionPlan(
            api_tests=api_tests,
            d2d_tests=d2d_tests,
            skipped_files=skipped_files,
            filtered_by_tags=filtered_count,
            test_type_by_path=test_type_by_path,
        )
