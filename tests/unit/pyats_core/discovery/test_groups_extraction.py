# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for groups attribute extraction from test classes."""

from pathlib import Path

import pytest

from nac_test.pyats_core.common.types import TestFileMetadata
from nac_test.pyats_core.discovery.test_type_resolver import TestMetadataResolver

from .helpers import create_mock_path

_UNUSED_TEST_ROOT = Path("/unused")


class TestGroupsExtraction:
    """Test groups attribute extraction from test classes."""

    @pytest.mark.parametrize(
        ("content", "expected_type", "expected_groups"),
        [
            # Simple groups list (API)
            (
                "class Test(NACTestBase):\n    groups = ['health', 'bgp']",
                "api",
                ["health", "bgp"],
            ),
            # Groups from D2D test
            (
                "class Test(SSHTestBase):\n    groups = ['nrfu', 'ospf']",
                "d2d",
                ["nrfu", "ospf"],
            ),
            # Annotated groups (groups: list[str] = [...])
            (
                "class Test(NACTestBase):\n    groups: list[str] = ['health']",
                "api",
                ["health"],
            ),
        ],
    )
    def test_valid_groups_extraction(
        self, content: str, expected_type: str, expected_groups: list[str]
    ) -> None:
        """Test extraction of valid groups from various formats."""
        resolver = TestMetadataResolver(_UNUSED_TEST_ROOT)
        mock_path = create_mock_path("/tests/test_file.py", content)

        metadata = resolver.resolve(mock_path)

        assert metadata.test_type == expected_type
        assert metadata.groups == expected_groups

    def test_no_groups_returns_empty_list(self) -> None:
        """Test that tests without groups attribute return empty list."""
        resolver = TestMetadataResolver(_UNUSED_TEST_ROOT)
        mock_path = create_mock_path(
            "/tests/test_file.py", "class Test(NACTestBase):\n    pass"
        )

        metadata = resolver.resolve(mock_path)

        assert metadata.groups == []

    @pytest.mark.parametrize(
        ("content", "expected_groups"),
        [
            # Non-list value ignored
            ("class Test(NACTestBase):\n    groups = 'not_a_list'", []),
            # Non-string elements filtered out
            (
                "class Test(NACTestBase):\n    groups = ['valid', 123, 'another']",
                ["valid", "another"],
            ),
        ],
    )
    def test_invalid_groups_handling(
        self, content: str, expected_groups: list[str]
    ) -> None:
        """Test that invalid groups values are handled gracefully."""
        resolver = TestMetadataResolver(_UNUSED_TEST_ROOT)
        mock_path = create_mock_path("/tests/test_file.py", content)

        metadata = resolver.resolve(mock_path)

        assert metadata.groups == expected_groups

    def test_unrecognized_base_class_ignores_groups(self) -> None:
        """Test that groups are ignored when base class is unrecognized."""
        resolver = TestMetadataResolver(_UNUSED_TEST_ROOT)
        mock_path = create_mock_path(
            "/tests/random/test_file.py",
            "class Test(UnknownBase):\n    groups = ['custom', 'tags']",
        )

        metadata = resolver.resolve(mock_path)

        assert metadata.test_type == "api"  # Falls back to default
        assert metadata.groups == []  # Groups ignored for unrecognized base

    def test_resolve_returns_metadata_with_groups(self) -> None:
        """Test that resolve returns TestFileMetadata with groups attribute."""
        resolver = TestMetadataResolver(_UNUSED_TEST_ROOT)
        mock_path = create_mock_path(
            "/tests/test_file.py",
            "class Test(NACTestBase):\n    groups = ['health', 'bgp']",
        )

        result = resolver.resolve(mock_path)

        assert isinstance(result, TestFileMetadata)
        assert hasattr(result, "groups")
        assert result.groups == ["health", "bgp"]
