# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tag matching for pyATS test filtering using Robot Framework tag pattern semantics.

This module provides tag matching functionality that uses Robot Framework's TagPatterns
API to filter pyATS tests based on their groups attribute. This ensures consistent
behavior between Robot Framework and pyATS test selection.

Tag Pattern Syntax (from Robot Framework):
    - Simple tags: 'health', 'bgp', 'sanity'
    - Wildcards: 'bgp*', '?est', 'health*check'
    - AND: 'healthANDbgp' or 'health&bgp'
    - OR: 'healthORbgp'
    - NOT: 'healthNOTsanity'
    - Patterns are case-insensitive and ignore underscores

Usage:
    >>> matcher = TagMatcher(include=['health', 'bgpORospf'], exclude=['nrfu'])
    >>> matcher.should_include(['health', 'bgp'])  # True
    >>> matcher.should_include(['nrfu'])           # False
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from robot.model import TagPatterns

logger = logging.getLogger(__name__)


class TagMatcher:
    """Matches tags against include/exclude patterns using Robot Framework semantics.

    This class wraps Robot Framework's TagPatterns to provide consistent tag matching
    behavior for pyATS tests. Tests are included if they match any include pattern
    (or if no include patterns are specified) AND don't match any exclude pattern.

    Attributes:
        include_patterns: TagPatterns object for include matching.
        exclude_patterns: TagPatterns object for exclude matching.
    """

    def __init__(
        self,
        include: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
    ) -> None:
        """Initialize the TagMatcher with include and exclude patterns.

        Args:
            include: Tag patterns to include. Tests must match at least one pattern
                     to be included. If None or empty, all tests are included
                     (subject to exclude patterns).
            exclude: Tag patterns to exclude. Tests matching any pattern are excluded,
                     regardless of include patterns.
        """
        self._include_list = list(include) if include else []
        self._exclude_list = list(exclude) if exclude else []

        # Create TagPatterns objects - these handle the Robot Framework pattern syntax
        self.include_patterns = (
            TagPatterns(self._include_list) if self._include_list else None
        )
        self.exclude_patterns = (
            TagPatterns(self._exclude_list) if self._exclude_list else None
        )

    @property
    def has_filters(self) -> bool:
        """Check if any tag filters are configured.

        Returns:
            True if either include or exclude patterns are specified.
        """
        return bool(self._include_list or self._exclude_list)

    def should_include(self, tags: Sequence[str] | None) -> bool:
        """Determine if a test with the given tags should be included.

        The matching logic follows Robot Framework semantics:
        1. If exclude patterns exist and any match, the test is excluded
        2. If include patterns exist, at least one must match for inclusion
        3. If no include patterns exist, the test is included (unless excluded)

        Args:
            tags: The tags/groups associated with a test class. Can be None or empty.

        Returns:
            True if the test should be included, False if it should be filtered out.
        """
        tags_list = list(tags) if tags else []

        # Check exclusions first - if any exclude pattern matches, filter out
        if self.exclude_patterns and self.exclude_patterns.match(tags_list):
            return False

        # If no include patterns specified, include the test
        if not self.include_patterns:
            return True

        # Check if tags match any include pattern
        return bool(self.include_patterns.match(tags_list))

    def __repr__(self) -> str:
        """Return a string representation of the TagMatcher."""
        return f"TagMatcher(include={self._include_list}, exclude={self._exclude_list})"
