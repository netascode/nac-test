# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for TagMatcher.

This module tests the TagMatcher class which provides tag-based filtering
for pyATS tests using Robot Framework tag pattern semantics.

Test Structure:
    - TestBasicMatching: Tests simple tag matching without patterns
    - TestIncludePatterns: Tests include-only filtering (parametrized)
    - TestExcludePatterns: Tests exclude-only filtering (parametrized)
    - TestCombinedPatterns: Tests combined include and exclude filtering
    - TestRobotPatternSemantics: Tests Robot Framework pattern syntax (parametrized)
    - TestEdgeCases: Tests edge cases like empty tags, None values, etc. (parametrized)
    - TestFormatFilterDescription: Tests format_filter_description helper (parametrized)
"""

from collections.abc import Sequence

import pytest

from nac_test.pyats_core.discovery.tag_matcher import (
    TagMatcher,
    format_filter_description,
)


class TestBasicMatching:
    """Test basic tag matching functionality."""

    def test_no_filters_includes_all(self) -> None:
        """Test that no filters means all tests are included."""
        matcher = TagMatcher()

        assert matcher.should_include(["health"])
        assert matcher.should_include(["bgp", "ospf"])
        assert matcher.should_include([])
        assert matcher.should_include(None)

    def test_repr(self) -> None:
        """Test string representation of TagMatcher."""
        matcher = TagMatcher(include=["health"], exclude=["nrfu"])
        repr_str = repr(matcher)

        assert "TagMatcher" in repr_str
        assert "health" in repr_str
        assert "nrfu" in repr_str


class TestIncludePatterns:
    """Test include-only tag filtering (parametrized)."""

    @pytest.mark.parametrize(
        ("include", "tags", "expected"),
        [
            # Simple include match
            (["health"], ["health"], True),
            (["health"], ["health", "bgp"], True),
            (["health"], ["nrfu"], False),
            (["health"], [], False),
            # Multiple include patterns (OR logic)
            (["health", "bgp"], ["health"], True),
            (["health", "bgp"], ["bgp"], True),
            (["health", "bgp"], ["health", "bgp"], True),
            (["health", "bgp"], ["ospf"], False),
            # Empty tags don't match
            (["health"], [], False),
            (["health"], None, False),
            # Case insensitive (Robot semantics)
            (["HEALTH"], ["health"], True),
            (["HEALTH"], ["Health"], True),
            (["HEALTH"], ["HEALTH"], True),
        ],
    )
    def test_include_filtering(
        self, include: list[str], tags: list[str] | None, expected: bool
    ) -> None:
        """Test include pattern matching with various inputs."""
        matcher = TagMatcher(include=include)
        assert matcher.should_include(tags) is expected


class TestExcludePatterns:
    """Test exclude-only tag filtering (parametrized)."""

    @pytest.mark.parametrize(
        ("exclude", "tags", "expected"),
        [
            # Simple exclude match
            (["nrfu"], ["nrfu"], False),
            (["nrfu"], ["nrfu", "health"], False),
            (["nrfu"], ["health"], True),
            (["nrfu"], [], True),
            # Multiple exclude patterns
            (["nrfu", "slow"], ["nrfu"], False),
            (["nrfu", "slow"], ["slow"], False),
            (["nrfu", "slow"], ["nrfu", "slow"], False),
            (["nrfu", "slow"], ["health"], True),
            (["nrfu", "slow"], ["bgp"], True),
            # Empty tags don't match exclude
            (["nrfu"], [], True),
            (["nrfu"], None, True),
            # Case insensitive
            (["NRFU"], ["nrfu"], False),
            (["NRFU"], ["Nrfu"], False),
            (["NRFU"], ["NRFU"], False),
        ],
    )
    def test_exclude_filtering(
        self, exclude: list[str], tags: list[str] | None, expected: bool
    ) -> None:
        """Test exclude pattern matching with various inputs."""
        matcher = TagMatcher(exclude=exclude)
        assert matcher.should_include(tags) is expected


class TestCombinedPatterns:
    """Test combined include and exclude filtering."""

    @pytest.mark.parametrize(
        ("include", "exclude", "tags", "expected"),
        [
            # Exclude takes priority over include
            (["health"], ["nrfu"], ["health", "nrfu"], False),
            (["health"], ["nrfu"], ["health"], True),
            (["health"], ["nrfu"], ["bgp"], False),
            # Realistic scenario
            (["health", "bgp"], ["nrfu"], ["health"], True),
            (["health", "bgp"], ["nrfu"], ["bgp"], True),
            (["health", "bgp"], ["nrfu"], ["health", "nrfu"], False),
            (["health", "bgp"], ["nrfu"], ["ospf"], False),
            (["health", "bgp"], ["nrfu"], ["nrfu"], False),
        ],
    )
    def test_combined_filtering(
        self,
        include: list[str],
        exclude: list[str],
        tags: list[str],
        expected: bool,
    ) -> None:
        """Test combined include and exclude pattern matching."""
        matcher = TagMatcher(include=include, exclude=exclude)
        assert matcher.should_include(tags) is expected


class TestRobotPatternSemantics:
    """Test Robot Framework tag pattern syntax (parametrized)."""

    @pytest.mark.parametrize(
        ("pattern", "tags", "expected"),
        [
            # OR pattern (healthORbgp)
            ("healthORbgp", ["health"], True),
            ("healthORbgp", ["bgp"], True),
            ("healthORbgp", ["health", "bgp"], True),
            ("healthORbgp", ["ospf"], False),
            # AND pattern (healthANDbgp)
            ("healthANDbgp", ["health", "bgp"], True),
            ("healthANDbgp", ["health"], False),
            ("healthANDbgp", ["bgp"], False),
            # NOT pattern (healthNOTnrfu)
            ("healthNOTnrfu", ["health"], True),
            ("healthNOTnrfu", ["health", "bgp"], True),
            ("healthNOTnrfu", ["health", "nrfu"], False),
            ("healthNOTnrfu", ["nrfu"], False),
            ("healthNOTnrfu", ["bgp"], False),
            # Ampersand AND pattern (health&bgp)
            ("health&bgp", ["health", "bgp"], True),
            ("health&bgp", ["health"], False),
            ("health&bgp", ["bgp"], False),
        ],
    )
    def test_boolean_patterns(
        self, pattern: str, tags: list[str], expected: bool
    ) -> None:
        """Test OR, AND, NOT, and ampersand patterns."""
        matcher = TagMatcher(include=[pattern])
        assert matcher.should_include(tags) is expected

    @pytest.mark.parametrize(
        ("pattern", "tags", "expected"),
        [
            # Wildcard pattern (*)
            ("health*", ["health"], True),
            ("health*", ["healthcheck"], True),
            ("health*", ["health_bgp"], True),
            ("health*", ["bgp"], False),
            # Question mark wildcard (?)
            ("bgp?", ["bgp1"], True),
            ("bgp?", ["bgpX"], True),
            ("bgp?", ["bgp"], False),
            ("bgp?", ["bgp12"], False),
            # Underscore ignored (Robot semantics)
            ("health_check", ["healthcheck"], True),
            ("health_check", ["health_check"], True),
            ("health_check", ["health__check"], True),
        ],
    )
    def test_wildcard_patterns(
        self, pattern: str, tags: list[str], expected: bool
    ) -> None:
        """Test wildcard and underscore handling patterns."""
        matcher = TagMatcher(include=[pattern])
        assert matcher.should_include(tags) is expected


class TestEdgeCases:
    """Test edge cases and special scenarios (parametrized)."""

    @pytest.mark.parametrize(
        ("include", "exclude", "tags", "expected"),
        [
            # None values
            (None, None, ["any"], True),
            # Empty lists
            ([], [], ["any"], True),
        ],
    )
    def test_initialization_edge_cases(
        self,
        include: list[str] | None,
        exclude: list[str] | None,
        tags: list[str],
        expected: bool,
    ) -> None:
        """Test initialization with None and empty list values."""
        matcher = TagMatcher(include=include, exclude=exclude)
        assert matcher.should_include(tags) is expected

    @pytest.mark.parametrize(
        ("include", "tags", "expected"),
        [
            # Single tag list
            (["health"], ["health"], True),
            # Many tags
            (
                ["health"],
                ["health", "bgp", "ospf", "nrfu", "sanity", "regression"],
                True,
            ),
            # Tags as tuple
            (["health"], ("health", "bgp"), True),
        ],
    )
    def test_tag_formats(
        self, include: list[str], tags: Sequence[str], expected: bool
    ) -> None:
        """Test various tag format inputs."""
        matcher = TagMatcher(include=include)
        assert matcher.should_include(tags) is expected

    def test_include_as_tuple(self) -> None:
        """Test that include patterns can be passed as a tuple."""
        matcher = TagMatcher(include=("health", "bgp"))

        assert matcher.should_include(["health"])
        assert matcher.should_include(["bgp"])

    @pytest.mark.parametrize(
        ("include", "tags", "expected"),
        [
            # Special characters in tags
            (["bgp-v4"], ["bgp-v4"], True),
            # Numeric-looking tags
            (["v1"], ["v1"], True),
            (["v1"], ["v2"], False),
        ],
    )
    def test_special_characters(
        self, include: list[str], tags: list[str], expected: bool
    ) -> None:
        """Test tags with special characters and numeric-looking values."""
        matcher = TagMatcher(include=include)
        assert matcher.should_include(tags) is expected


class TestFormatFilterDescription:
    """Test format_filter_description helper and TagMatcher.__str__ (parametrized)."""

    @pytest.mark.parametrize(
        ("include", "exclude", "expected"),
        [
            # Basic formatting
            (["bgp"], None, "include: 'bgp'"),
            (None, ["ospf"], "exclude: 'ospf'"),
            (["bgp"], ["health"], "include: 'bgp', exclude: 'health'"),
            # Empty returns empty string
            (None, None, ""),
            ([], [], ""),
            # Multiple patterns
            (
                ["bgp", "ospf"],
                ["nrfuANDhealth"],
                "include: 'bgp', 'ospf', exclude: 'nrfu AND health'",
            ),
        ],
    )
    def test_basic_formatting(
        self, include: list[str] | None, exclude: list[str] | None, expected: str
    ) -> None:
        """Test basic format_filter_description output."""
        result = format_filter_description(include=include, exclude=exclude)
        assert result == expected

    @pytest.mark.parametrize(
        ("include", "exclude", "expected"),
        [
            # OR pattern formatting
            (None, ["bgpORospf"], "exclude: 'bgp OR ospf'"),
            # AND pattern formatting
            (["healthANDbgp"], None, "include: 'health AND bgp'"),
        ],
    )
    def test_pattern_formatting(
        self, include: list[str] | None, exclude: list[str] | None, expected: str
    ) -> None:
        """Test pattern expansion in format_filter_description."""
        result = format_filter_description(include=include, exclude=exclude)
        assert result == expected

    def test_str_matches_format_filter_description(self) -> None:
        """Test TagMatcher.__str__ matches format_filter_description."""
        matcher = TagMatcher(include=["bgpORospf"], exclude=["health"])
        assert str(matcher) == format_filter_description(
            include=["bgpORospf"], exclude=["health"]
        )
