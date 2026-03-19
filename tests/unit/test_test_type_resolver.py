# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for TestMetadataResolver.

This module tests the TestMetadataResolver class which extracts metadata from
PyATS test files: test type (API vs D2D) and groups (for tag-based filtering).

Test Structure:
    - TestStaticAnalysisDetection: Tests AST-based base class detection
    - TestDirectoryFallback: Tests directory path-based fallback detection
    - TestDefaultBehavior: Tests default classification with warnings
    - TestErrorHandling: Tests various error conditions
    - TestIntegration: Integration tests with real test scenarios
    - TestGroupsExtraction: Tests groups attribute extraction for tag filtering

The tests use fixture files from tests/fixtures/ to avoid creating temporary
files during test execution, ensuring consistent and reliable test behavior.
"""

import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from nac_test.pyats_core.common.types import TestFileMetadata
from nac_test.pyats_core.discovery.test_type_resolver import (
    BASE_CLASS_MAPPING,
    DEFAULT_TEST_TYPE,
    NoRecognizedBaseError,
    TestMetadataResolver,
)

# Get the fixtures directory path
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _create_mock_path(path_str: str, content: str = "") -> Any:
    """Create a mock Path object for testing.

    Args:
        path_str: The path string to return from as_posix() and __str__()
        content: The file content to return from read_text()

    Returns:
        A MagicMock configured to behave like a Path object
    """
    mock = MagicMock()
    mock.resolve.return_value = mock
    mock.as_posix.return_value = path_str
    mock.read_text.return_value = content
    mock.__str__ = MagicMock(return_value=path_str)  # type: ignore[method-assign]
    mock.name = Path(path_str).name
    return mock


class TestStaticAnalysisDetection:
    """Test AST-based detection of test types from base class inheritance.

    This class tests the primary detection method which uses Python's AST
    module to statically analyze test files and determine their type based
    on base class inheritance.
    """

    def test_direct_api_inheritance(self) -> None:
        """Test detection of API test with direct NACTestBase inheritance."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "api" / "test_api_simple.py"

        result = resolver.resolve(test_file)

        assert result.test_type == "api"

    def test_direct_d2d_inheritance(self) -> None:
        """Test detection of D2D test with direct SSHTestBase inheritance."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "d2d" / "test_d2d_simple.py"

        result = resolver.resolve(test_file)

        assert result.test_type == "d2d"

    def test_multiple_inheritance_api(self) -> None:
        """Test detection with multiple inheritance where API base is present."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "api" / "test_api_multiple_inheritance.py"

        result = resolver.resolve(test_file)

        assert result.test_type == "api"

    def test_multiple_inheritance_d2d(self) -> None:
        """Test detection with multiple inheritance where D2D base is present."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "d2d" / "test_d2d_multiple_inheritance.py"

        result = resolver.resolve(test_file)

        assert result.test_type == "d2d"

    def test_qualified_attribute_inheritance(self) -> None:
        """Test detection of qualified class references (module.ClassName)."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "api" / "test_api_attribute.py"

        result = resolver.resolve(test_file)

        assert result.test_type == "api"

    def test_multiline_class_definition_api(self) -> None:
        """Test detection with multiline class definition for API test."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "api" / "test_api_multiline.py"

        result = resolver.resolve(test_file)

        assert result.test_type == "api"

    def test_multiline_class_definition_d2d(self) -> None:
        """Test detection with multiline class definition for D2D test."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "d2d" / "test_d2d_multiline.py"

        result = resolver.resolve(test_file)

        assert result.test_type == "d2d"

    def test_all_known_api_bases(self) -> None:
        """Test that all API base classes in mapping are detected correctly."""
        # This test validates the BASE_CLASS_MAPPING configuration
        api_bases = [
            base for base, test_type in BASE_CLASS_MAPPING.items() if test_type == "api"
        ]

        # Ensure we have API bases defined
        assert len(api_bases) > 0
        assert "NACTestBase" in api_bases
        assert "APICTestBase" in api_bases
        assert "CatalystCenterTestBase" in api_bases

    def test_all_known_d2d_bases(self) -> None:
        """Test that all D2D base classes in mapping are detected correctly."""
        # This test validates the BASE_CLASS_MAPPING configuration
        d2d_bases = [
            base for base, test_type in BASE_CLASS_MAPPING.items() if test_type == "d2d"
        ]

        # Ensure we have D2D bases defined
        assert len(d2d_bases) > 0
        assert "SSHTestBase" in d2d_bases
        assert "IOSXETestBase" in d2d_bases

    def test_nested_classes_ignored(self) -> None:
        """Test that nested classes are ignored during detection."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "edge_cases" / "test_nested_classes.py"

        # The top-level class inherits from NACTestBase (API)
        result = resolver.resolve(test_file)

        assert result.test_type == "api"

    def test_import_alias_not_detected(self) -> None:
        """Test that import aliases fall back to directory detection."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "edge_cases" / "test_import_alias.py"

        # Should fall back to default since alias isn't recognized
        with patch("logging.Logger.warning") as mock_warning:
            result = resolver.resolve(test_file)

        assert result.test_type == "api"  # Default
        mock_warning.assert_called_once()
        assert "Could not detect test type" in str(mock_warning.call_args)

    def test_comments_and_strings_ignored(self) -> None:
        """Test that comments and strings don't affect detection."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "edge_cases" / "test_comments_and_strings.py"

        # Should detect the actual base class, not the ones in comments/strings
        result = resolver.resolve(test_file)

        assert result.test_type == "d2d"  # Based on actual SSHTestBase inheritance


class TestDirectoryFallback:
    """Test directory-based fallback detection.

    When AST analysis fails to detect a recognized base class, the resolver
    falls back to checking the directory path for /api/ or /d2d/ indicators.
    """

    def test_d2d_directory_fallback(self) -> None:
        """Test fallback to D2D when file is in /d2d/ directory."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "directory_fallback" / "d2d" / "test_custom_base.py"

        result = resolver.resolve(test_file)

        assert result.test_type == "d2d"

    def test_api_directory_fallback(self) -> None:
        """Test fallback to API when file is in /api/ directory."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "directory_fallback" / "api" / "test_unknown_base.py"

        result = resolver.resolve(test_file)

        assert result.test_type == "api"

    def test_directory_fallback_case_sensitive(self) -> None:
        """Test that directory detection is case-sensitive."""
        resolver = TestMetadataResolver(FIXTURES_DIR)

        # Create a mock path with uppercase D2D (which shouldn't match)
        mock_path = _create_mock_path("/tests/D2D/test_file.py", "class Test: pass")

        # Should fall back to default, not detect as d2d
        with patch("logging.Logger.warning") as mock_warning:
            result = resolver.resolve(mock_path)

        assert result.test_type == "api"  # Default
        mock_warning.assert_called_once()

    def test_nested_d2d_directory_detection(self) -> None:
        """Test that nested /d2d/ paths are detected correctly."""
        resolver = TestMetadataResolver(FIXTURES_DIR)

        # Mock a deeply nested d2d path
        mock_path = _create_mock_path(
            "/project/tests/feature/d2d/verify_ssh.py", "class Test: pass"
        )

        result = resolver.resolve(mock_path)

        assert result.test_type == "d2d"

    def test_ast_priority_over_directory(self) -> None:
        """Test that AST detection has priority over directory structure.

        A file with SSHTestBase in an /api/ directory should still be
        detected as D2D based on the base class.
        """
        resolver = TestMetadataResolver(FIXTURES_DIR)

        # Mock file in /api/ directory but with D2D base class
        mock_path = _create_mock_path(
            "/tests/api/test_file.py",
            """
from nac_test.pyats_core.common.ssh_base_test import SSHTestBase

class TestDevice(SSHTestBase):
    pass
""",
        )

        result = resolver.resolve(mock_path)

        # AST detection should win over directory
        assert result.test_type == "d2d"


class TestDefaultBehavior:
    """Test default behavior when detection fails.

    When both AST analysis and directory detection fail, the resolver
    defaults to 'api' type with a warning.
    """

    def test_defaults_to_api_with_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that unknown tests default to API with warning."""
        resolver = TestMetadataResolver(FIXTURES_DIR)

        # Create a mock file with no recognized base and not in special directory
        mock_path = _create_mock_path(
            "/tests/random/test_file.py", "class Test(UnknownBase): pass"
        )

        with caplog.at_level(logging.WARNING):
            result = resolver.resolve(mock_path)

        assert result.test_type == "api"
        assert "Could not detect test type" in caplog.text
        assert "Assuming 'api'" in caplog.text

    def test_empty_file_defaults_to_api(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that empty files default to API."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "edge_cases" / "test_empty_file.py"

        with caplog.at_level(logging.WARNING):
            result = resolver.resolve(test_file)

        assert result.test_type == "api"
        assert "Could not detect test type" in caplog.text

    def test_no_classes_defaults_to_api(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that files with no classes default to API."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "edge_cases" / "test_no_base_class.py"

        with caplog.at_level(logging.WARNING):
            result = resolver.resolve(test_file)

        assert result.test_type == "api"
        assert "Could not detect test type" in caplog.text

    def test_default_type_constant(self) -> None:
        """Test that the DEFAULT_TEST_TYPE constant is 'api'."""
        assert DEFAULT_TEST_TYPE == "api"


class TestErrorHandling:
    """Test error cases and exception handling.

    Tests various error conditions including syntax errors, file read errors,
    and mixed test types.
    """

    def test_syntax_error_falls_back(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that syntax errors in test files trigger fallback detection."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "edge_cases" / "test_syntax_error.py"

        with caplog.at_level(logging.WARNING):
            result = resolver.resolve(test_file)

        # Should fall back to default
        assert result.test_type == "api"
        assert "Failed to parse" in caplog.text

    def test_file_not_found_error(self) -> None:
        """Test that nonexistent files raise appropriate errors."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "nonexistent" / "test_missing.py"

        # The resolver should let the OSError propagate from read_text()
        with pytest.raises(OSError):
            resolver._extract_metadata_via_ast(test_file)

    def test_mixed_api_and_d2d_returns_first(self) -> None:
        """Test file with both API and D2D classes returns first found type.

        The current implementation returns the type of the first recognized
        base class found, which is reasonable behavior for mixed files.
        """
        resolver = TestMetadataResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "edge_cases" / "test_mixed_invalid.py"

        # The file has TestAPI(NACTestBase) first, then TestSSH(SSHTestBase)
        result = resolver.resolve(test_file)

        # Should return 'api' (the first recognized base)
        assert result.test_type == "api"

    def test_no_recognized_base_exception(self) -> None:
        """Test NoRecognizedBaseError exception behavior."""
        # Test with found bases
        exc = NoRecognizedBaseError("test.py", ["CustomBase", "AnotherBase"])
        assert "test.py" in str(exc)
        assert "CustomBase" in str(exc)
        assert "AnotherBase" in str(exc)
        assert exc.filename == "test.py"
        assert exc.found_bases == ["CustomBase", "AnotherBase"]

        # Test without found bases
        exc2 = NoRecognizedBaseError("empty.py")
        assert "empty.py" in str(exc2)
        assert "No base classes found" in str(exc2)
        assert exc2.found_bases == []

    def test_unicode_in_file_path(self) -> None:
        """Test that unicode characters in file paths are handled correctly."""
        resolver = TestMetadataResolver(FIXTURES_DIR)

        # Mock a path with unicode characters
        mock_path = _create_mock_path(
            "/tests/тесты/test_файл.py",
            """
class TestCase(NACTestBase):
    pass
""",
        )

        result = resolver.resolve(mock_path)

        assert result.test_type == "api"

    def test_permission_denied_error(self) -> None:
        """Test handling of permission denied errors."""
        resolver = TestMetadataResolver(FIXTURES_DIR)

        mock_path = _create_mock_path("/tests/test.py", "")
        mock_path.read_text.side_effect = PermissionError("Permission denied")

        # Permission error should trigger fallback to default
        with patch("logging.Logger.warning") as mock_warning:
            result = resolver.resolve(mock_path)

        assert result.test_type == "api"  # Default
        # Check that warning was called twice - once for parse failure, once for default
        assert mock_warning.call_count >= 1
        # Check that at least one warning mentions parse failure or default behavior
        warning_messages = " ".join(str(call) for call in mock_warning.call_args_list)
        assert (
            "Failed to parse" in warning_messages
            or "Could not detect test type" in warning_messages
        )


class TestIntegration:
    """Integration tests validating resolver with real test scenarios."""

    def test_resolver_initialization(self) -> None:
        """Test that resolver initializes correctly with test root."""
        test_root = Path("/some/test/path")
        resolver = TestMetadataResolver(test_root)

        assert resolver.test_root == test_root.resolve()
        assert (
            resolver.logger.name == "nac_test.pyats_core.discovery.test_type_resolver"
        )

    def test_all_fixture_files_resolve(self) -> None:
        """Test that all fixture files can be resolved without errors."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        errors = []

        # Find all Python files in fixtures
        for py_file in FIXTURES_DIR.rglob("*.py"):
            try:
                metadata = resolver.resolve(py_file)
                assert metadata.test_type in {"api", "d2d"}
            except Exception as e:
                errors.append(f"{py_file}: {e}")

        # Only syntax_error.py should potentially cause issues (handled gracefully)
        assert len(errors) == 0, f"Errors resolving fixtures: {errors}"

    def test_logging_output(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that appropriate log messages are generated."""
        test_file = FIXTURES_DIR / "api" / "test_api_simple.py"

        # Capture initialization logging
        with caplog.at_level(logging.DEBUG):
            resolver = TestMetadataResolver(FIXTURES_DIR)

        # Check initialization logged
        assert "Initialized TestMetadataResolver" in caplog.text

        caplog.clear()

        # Resolve should show AST analysis
        with caplog.at_level(logging.DEBUG):
            resolver.resolve(test_file)

        # Check for expected debug messages
        assert "Analyzing AST" in caplog.text

    def test_base_class_mapping_completeness(self) -> None:
        """Test that BASE_CLASS_MAPPING covers expected architectures."""
        # Verify essential API bases are present
        api_bases = [
            "NACTestBase",
            "APICTestBase",
            "SDWANManagerTestBase",
            "CatalystCenterTestBase",
            "MerakiTestBase",
            "FMCTestBase",
            "ISETestBase",
        ]
        for base in api_bases:
            assert base in BASE_CLASS_MAPPING
            assert BASE_CLASS_MAPPING[base] == "api"

        # Verify essential D2D bases are present
        d2d_bases = [
            "SSHTestBase",
            "SDWANTestBase",
            "IOSXETestBase",
            "NXOSTestBase",
            "IOSTestBase",
        ]
        for base in d2d_bases:
            assert base in BASE_CLASS_MAPPING
            assert BASE_CLASS_MAPPING[base] == "d2d"

        # Verify all values are valid test types
        for test_type in BASE_CLASS_MAPPING.values():
            assert test_type in {"api", "d2d"}


class TestGroupsExtraction:
    """Test groups attribute extraction from test classes.

    These tests validate the resolve() method's groups extraction functionality
    used for tag-based filtering.
    """

    def test_extract_simple_groups(self) -> None:
        """Test extraction of simple groups list."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        mock_path = _create_mock_path(
            "/tests/test_file.py",
            """
class TestWithGroups(NACTestBase):
    groups = ["health", "bgp"]
""",
        )

        metadata = resolver.resolve(mock_path)

        assert metadata.test_type == "api"
        assert metadata.groups == ["health", "bgp"]

    def test_extract_groups_d2d(self) -> None:
        """Test extraction of groups from D2D test."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        mock_path = _create_mock_path(
            "/tests/test_file.py",
            """
class TestD2D(SSHTestBase):
    groups = ["nrfu", "ospf"]
""",
        )

        metadata = resolver.resolve(mock_path)

        assert metadata.test_type == "d2d"
        assert metadata.groups == ["nrfu", "ospf"]

    def test_no_groups_returns_empty_list(self) -> None:
        """Test that tests without groups attribute return empty list."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        mock_path = _create_mock_path(
            "/tests/test_file.py",
            """
class TestNoGroups(NACTestBase):
    pass
""",
        )

        metadata = resolver.resolve(mock_path)

        assert metadata.test_type == "api"
        assert metadata.groups == []

    def test_annotated_groups(self) -> None:
        """Test extraction of annotated groups (groups: list[str] = [...])."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        mock_path = _create_mock_path(
            "/tests/test_file.py",
            """
class TestAnnotated(NACTestBase):
    groups: list[str] = ["health"]
""",
        )

        metadata = resolver.resolve(mock_path)

        assert metadata.test_type == "api"
        assert metadata.groups == ["health"]

    def test_resolve_returns_metadata(self) -> None:
        """Test that resolve returns TestFileMetadata."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        mock_path = _create_mock_path(
            "/tests/test_file.py",
            """
class TestMetadata(NACTestBase):
    groups = ["health", "bgp"]
""",
        )

        result = resolver.resolve(mock_path)

        assert isinstance(result, TestFileMetadata)
        assert hasattr(result, "path")
        assert hasattr(result, "test_type")
        assert hasattr(result, "groups")

    def test_groups_with_unrecognized_base_fallback(self) -> None:
        """Test groups extraction falls back gracefully with unknown base class."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        mock_path = _create_mock_path(
            "/tests/random/test_file.py",
            """
class TestCustom(UnknownBase):
    groups = ["custom", "tags"]
""",
        )

        metadata = resolver.resolve(mock_path)

        assert metadata.test_type == "api"
        assert metadata.groups == []

    def test_groups_invalid_value_ignored(self) -> None:
        """Test that non-list groups values are ignored."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        mock_path = _create_mock_path(
            "/tests/test_file.py",
            """
class TestBad(NACTestBase):
    groups = "not_a_list"
""",
        )

        metadata = resolver.resolve(mock_path)

        assert metadata.test_type == "api"
        assert metadata.groups == []

    def test_groups_with_non_string_elements(self) -> None:
        """Test that non-string elements in groups are ignored."""
        resolver = TestMetadataResolver(FIXTURES_DIR)
        mock_path = _create_mock_path(
            "/tests/test_file.py",
            """
class TestMixed(NACTestBase):
    groups = ["valid", 123, "another"]
""",
        )

        metadata = resolver.resolve(mock_path)

        assert metadata.test_type == "api"
        assert metadata.groups == ["valid", "another"]
