# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for TagMatcher.

This module tests the TagMatcher class which provides tag-based filtering
for pyATS tests using Robot Framework tag pattern semantics.

Test Structure:
    - TestBasicMatching: Tests simple tag matching without patterns
    - TestIncludePatterns: Tests include-only filtering
    - TestExcludePatterns: Tests exclude-only filtering
    - TestCombinedPatterns: Tests combined include and exclude filtering
    - TestRobotPatternSemantics: Tests Robot Framework pattern syntax (AND, OR, NOT, wildcards)
    - TestEdgeCases: Tests edge cases like empty tags, None values, etc.
"""

from nac_test.pyats_core.discovery.tag_matcher import TagMatcher


class TestBasicMatching:
    """Test basic tag matching functionality."""

    def test_no_filters_includes_all(self) -> None:
        """Test that no filters means all tests are included."""
        matcher = TagMatcher()

        assert matcher.should_include(["health"])
        assert matcher.should_include(["bgp", "ospf"])
        assert matcher.should_include([])
        assert matcher.should_include(None)

    def test_has_filters_false_when_empty(self) -> None:
        """Test has_filters is False when no filters configured."""
        matcher = TagMatcher()
        assert matcher.has_filters is False

        matcher2 = TagMatcher(include=[], exclude=[])
        assert matcher2.has_filters is False

    def test_has_filters_true_with_include(self) -> None:
        """Test has_filters is True when include patterns are set."""
        matcher = TagMatcher(include=["health"])
        assert matcher.has_filters is True

    def test_has_filters_true_with_exclude(self) -> None:
        """Test has_filters is True when exclude patterns are set."""
        matcher = TagMatcher(exclude=["nrfu"])
        assert matcher.has_filters is True

    def test_repr(self) -> None:
        """Test string representation of TagMatcher."""
        matcher = TagMatcher(include=["health"], exclude=["nrfu"])
        repr_str = repr(matcher)

        assert "TagMatcher" in repr_str
        assert "health" in repr_str
        assert "nrfu" in repr_str


class TestIncludePatterns:
    """Test include-only tag filtering."""

    def test_simple_include_match(self) -> None:
        """Test matching a simple include pattern."""
        matcher = TagMatcher(include=["health"])

        assert matcher.should_include(["health"])
        assert matcher.should_include(["health", "bgp"])
        assert not matcher.should_include(["nrfu"])
        assert not matcher.should_include([])

    def test_multiple_include_patterns_or(self) -> None:
        """Test that multiple include patterns use OR logic."""
        matcher = TagMatcher(include=["health", "bgp"])

        assert matcher.should_include(["health"])
        assert matcher.should_include(["bgp"])
        assert matcher.should_include(["health", "bgp"])
        assert not matcher.should_include(["ospf"])

    def test_include_with_empty_tags(self) -> None:
        """Test that empty tags don't match include patterns."""
        matcher = TagMatcher(include=["health"])

        assert not matcher.should_include([])
        assert not matcher.should_include(None)

    def test_include_case_insensitive(self) -> None:
        """Test that tag matching is case-insensitive (Robot semantics)."""
        matcher = TagMatcher(include=["HEALTH"])

        assert matcher.should_include(["health"])
        assert matcher.should_include(["Health"])
        assert matcher.should_include(["HEALTH"])


class TestExcludePatterns:
    """Test exclude-only tag filtering."""

    def test_simple_exclude_match(self) -> None:
        """Test matching a simple exclude pattern."""
        matcher = TagMatcher(exclude=["nrfu"])

        assert not matcher.should_include(["nrfu"])
        assert not matcher.should_include(["nrfu", "health"])
        assert matcher.should_include(["health"])
        assert matcher.should_include([])

    def test_multiple_exclude_patterns(self) -> None:
        """Test multiple exclude patterns."""
        matcher = TagMatcher(exclude=["nrfu", "slow"])

        assert not matcher.should_include(["nrfu"])
        assert not matcher.should_include(["slow"])
        assert not matcher.should_include(["nrfu", "slow"])
        assert matcher.should_include(["health"])
        assert matcher.should_include(["bgp"])

    def test_exclude_with_empty_tags(self) -> None:
        """Test that empty tags don't match exclude patterns."""
        matcher = TagMatcher(exclude=["nrfu"])

        assert matcher.should_include([])
        assert matcher.should_include(None)

    def test_exclude_case_insensitive(self) -> None:
        """Test that exclude matching is case-insensitive."""
        matcher = TagMatcher(exclude=["NRFU"])

        assert not matcher.should_include(["nrfu"])
        assert not matcher.should_include(["Nrfu"])
        assert not matcher.should_include(["NRFU"])


class TestCombinedPatterns:
    """Test combined include and exclude filtering."""

    def test_exclude_takes_priority(self) -> None:
        """Test that exclude patterns take priority over include."""
        matcher = TagMatcher(include=["health"], exclude=["nrfu"])

        assert not matcher.should_include(["health", "nrfu"])
        assert matcher.should_include(["health"])
        assert not matcher.should_include(["bgp"])

    def test_combined_realistic_scenario(self) -> None:
        """Test a realistic filtering scenario."""
        matcher = TagMatcher(include=["health", "bgp"], exclude=["nrfu"])

        assert matcher.should_include(["health"])
        assert matcher.should_include(["bgp"])
        assert not matcher.should_include(["health", "nrfu"])
        assert not matcher.should_include(["ospf"])
        assert not matcher.should_include(["nrfu"])


class TestRobotPatternSemantics:
    """Test Robot Framework tag pattern syntax."""

    def test_or_pattern(self) -> None:
        """Test OR pattern (healthORbgp)."""
        matcher = TagMatcher(include=["healthORbgp"])

        assert matcher.should_include(["health"])
        assert matcher.should_include(["bgp"])
        assert matcher.should_include(["health", "bgp"])
        assert not matcher.should_include(["ospf"])

    def test_and_pattern(self) -> None:
        """Test AND pattern (healthANDbgp)."""
        matcher = TagMatcher(include=["healthANDbgp"])

        assert matcher.should_include(["health", "bgp"])
        assert not matcher.should_include(["health"])
        assert not matcher.should_include(["bgp"])

    def test_not_pattern(self) -> None:
        """Test NOT pattern (healthNOTnrfu)."""
        matcher = TagMatcher(include=["healthNOTnrfu"])

        assert matcher.should_include(["health"])
        assert matcher.should_include(["health", "bgp"])
        assert not matcher.should_include(["health", "nrfu"])
        assert not matcher.should_include(["nrfu"])
        assert not matcher.should_include(["bgp"])

    def test_wildcard_pattern(self) -> None:
        """Test wildcard patterns (*)."""
        matcher = TagMatcher(include=["health*"])

        assert matcher.should_include(["health"])
        assert matcher.should_include(["healthcheck"])
        assert matcher.should_include(["health_bgp"])
        assert not matcher.should_include(["bgp"])

    def test_question_mark_wildcard(self) -> None:
        """Test single-character wildcard (?)."""
        matcher = TagMatcher(include=["bgp?"])

        assert matcher.should_include(["bgp1"])
        assert matcher.should_include(["bgpX"])
        assert not matcher.should_include(["bgp"])
        assert not matcher.should_include(["bgp12"])

    def test_ampersand_and_pattern(self) -> None:
        """Test ampersand AND pattern (health&bgp)."""
        matcher = TagMatcher(include=["health&bgp"])

        assert matcher.should_include(["health", "bgp"])
        assert not matcher.should_include(["health"])
        assert not matcher.should_include(["bgp"])

    def test_underscore_ignored(self) -> None:
        """Test that underscores are ignored in matching (Robot semantics)."""
        matcher = TagMatcher(include=["health_check"])

        assert matcher.should_include(["healthcheck"])
        assert matcher.should_include(["health_check"])
        assert matcher.should_include(["health__check"])


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_none_include_exclude(self) -> None:
        """Test initialization with None values."""
        matcher = TagMatcher(include=None, exclude=None)

        assert not matcher.has_filters
        assert matcher.should_include(["any"])

    def test_empty_list_include_exclude(self) -> None:
        """Test initialization with empty lists."""
        matcher = TagMatcher(include=[], exclude=[])

        assert not matcher.has_filters
        assert matcher.should_include(["any"])

    def test_single_tag_list(self) -> None:
        """Test matching with single-element tag lists."""
        matcher = TagMatcher(include=["health"])

        assert matcher.should_include(["health"])

    def test_many_tags(self) -> None:
        """Test matching with many tags."""
        matcher = TagMatcher(include=["health"])
        tags = ["health", "bgp", "ospf", "nrfu", "sanity", "regression"]

        assert matcher.should_include(tags)

    def test_tags_as_tuple(self) -> None:
        """Test that tags can be passed as a tuple."""
        matcher = TagMatcher(include=["health"])

        assert matcher.should_include(("health", "bgp"))

    def test_include_as_tuple(self) -> None:
        """Test that include patterns can be passed as a tuple."""
        matcher = TagMatcher(include=("health", "bgp"))

        assert matcher.should_include(["health"])
        assert matcher.should_include(["bgp"])

    def test_special_characters_in_tags(self) -> None:
        """Test tags with special characters."""
        matcher = TagMatcher(include=["bgp-v4"])

        assert matcher.should_include(["bgp-v4"])

    def test_numeric_looking_tags(self) -> None:
        """Test tags that look like numbers."""
        matcher = TagMatcher(include=["v1"])

        assert matcher.should_include(["v1"])
        assert not matcher.should_include(["v2"])
