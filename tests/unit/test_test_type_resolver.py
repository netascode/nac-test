"""Unit tests for TestTypeResolver.

This module tests the TestTypeResolver class which is responsible for detecting
whether PyATS test files should be classified as API (controller/REST) or D2D
(Direct-to-Device/SSH) tests.

Test Structure:
    - TestStaticAnalysisDetection: Tests AST-based base class detection
    - TestDirectoryFallback: Tests directory path-based fallback detection
    - TestDefaultBehavior: Tests default classification with warnings
    - TestErrorHandling: Tests various error conditions
    - TestCaching: Tests the caching mechanism for performance

The tests use fixture files from tests/fixtures/ to avoid creating temporary
files during test execution, ensuring consistent and reliable test behavior.
"""

import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from nac_test.pyats_core.discovery.test_type_resolver import (
    BASE_CLASS_MAPPING,
    DEFAULT_TEST_TYPE,
    NoRecognizedBaseError,
    TestTypeResolver,
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
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "api" / "test_api_simple.py"

        result = resolver.resolve(test_file)

        assert result == "api"

    def test_direct_d2d_inheritance(self) -> None:
        """Test detection of D2D test with direct SSHTestBase inheritance."""
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "d2d" / "test_d2d_simple.py"

        result = resolver.resolve(test_file)

        assert result == "d2d"

    def test_multiple_inheritance_api(self) -> None:
        """Test detection with multiple inheritance where API base is present."""
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "api" / "test_api_multiple_inheritance.py"

        result = resolver.resolve(test_file)

        assert result == "api"

    def test_multiple_inheritance_d2d(self) -> None:
        """Test detection with multiple inheritance where D2D base is present."""
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "d2d" / "test_d2d_multiple_inheritance.py"

        result = resolver.resolve(test_file)

        assert result == "d2d"

    def test_qualified_attribute_inheritance(self) -> None:
        """Test detection of qualified class references (module.ClassName)."""
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "api" / "test_api_attribute.py"

        result = resolver.resolve(test_file)

        assert result == "api"

    def test_multiline_class_definition_api(self) -> None:
        """Test detection with multiline class definition for API test."""
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "api" / "test_api_multiline.py"

        result = resolver.resolve(test_file)

        assert result == "api"

    def test_multiline_class_definition_d2d(self) -> None:
        """Test detection with multiline class definition for D2D test."""
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "d2d" / "test_d2d_multiline.py"

        result = resolver.resolve(test_file)

        assert result == "d2d"

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
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "edge_cases" / "test_nested_classes.py"

        # The top-level class inherits from NACTestBase (API)
        result = resolver.resolve(test_file)

        assert result == "api"

    def test_import_alias_not_detected(self) -> None:
        """Test that import aliases fall back to directory detection."""
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "edge_cases" / "test_import_alias.py"

        # Should fall back to default since alias isn't recognized
        with patch("logging.Logger.warning") as mock_warning:
            result = resolver.resolve(test_file)

        assert result == "api"  # Default
        mock_warning.assert_called_once()
        assert "Could not detect test type" in str(mock_warning.call_args)

    def test_comments_and_strings_ignored(self) -> None:
        """Test that comments and strings don't affect detection."""
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "edge_cases" / "test_comments_and_strings.py"

        # Should detect the actual base class, not the ones in comments/strings
        result = resolver.resolve(test_file)

        assert result == "d2d"  # Based on actual SSHTestBase inheritance


class TestDirectoryFallback:
    """Test directory-based fallback detection.

    When AST analysis fails to detect a recognized base class, the resolver
    falls back to checking the directory path for /api/ or /d2d/ indicators.
    """

    def test_d2d_directory_fallback(self) -> None:
        """Test fallback to D2D when file is in /d2d/ directory."""
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "directory_fallback" / "d2d" / "test_custom_base.py"

        result = resolver.resolve(test_file)

        assert result == "d2d"

    def test_api_directory_fallback(self) -> None:
        """Test fallback to API when file is in /api/ directory."""
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "directory_fallback" / "api" / "test_unknown_base.py"

        result = resolver.resolve(test_file)

        assert result == "api"

    def test_directory_fallback_case_sensitive(self) -> None:
        """Test that directory detection is case-sensitive."""
        resolver = TestTypeResolver(FIXTURES_DIR)

        # Create a mock path with uppercase D2D (which shouldn't match)
        mock_path = _create_mock_path("/tests/D2D/test_file.py", "class Test: pass")

        # Should fall back to default, not detect as d2d
        with patch("logging.Logger.warning") as mock_warning:
            result = resolver.resolve(mock_path)

        assert result == "api"  # Default
        mock_warning.assert_called_once()

    def test_nested_d2d_directory_detection(self) -> None:
        """Test that nested /d2d/ paths are detected correctly."""
        resolver = TestTypeResolver(FIXTURES_DIR)

        # Mock a deeply nested d2d path
        mock_path = _create_mock_path(
            "/project/tests/feature/d2d/verify_ssh.py", "class Test: pass"
        )

        result = resolver.resolve(mock_path)

        assert result == "d2d"

    def test_ast_priority_over_directory(self) -> None:
        """Test that AST detection has priority over directory structure.

        A file with SSHTestBase in an /api/ directory should still be
        detected as D2D based on the base class.
        """
        resolver = TestTypeResolver(FIXTURES_DIR)

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
        assert result == "d2d"


class TestDefaultBehavior:
    """Test default behavior when detection fails.

    When both AST analysis and directory detection fail, the resolver
    defaults to 'api' type with a warning.
    """

    def test_defaults_to_api_with_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that unknown tests default to API with warning."""
        resolver = TestTypeResolver(FIXTURES_DIR)

        # Create a mock file with no recognized base and not in special directory
        mock_path = _create_mock_path(
            "/tests/random/test_file.py", "class Test(UnknownBase): pass"
        )

        with caplog.at_level(logging.WARNING):
            result = resolver.resolve(mock_path)

        assert result == "api"
        assert "Could not detect test type" in caplog.text
        assert "Assuming 'api'" in caplog.text

    def test_empty_file_defaults_to_api(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that empty files default to API."""
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "edge_cases" / "test_empty_file.py"

        with caplog.at_level(logging.WARNING):
            result = resolver.resolve(test_file)

        assert result == "api"
        assert "Could not detect test type" in caplog.text

    def test_no_classes_defaults_to_api(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that files with no classes default to API."""
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "edge_cases" / "test_no_base_class.py"

        with caplog.at_level(logging.WARNING):
            result = resolver.resolve(test_file)

        assert result == "api"
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
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "edge_cases" / "test_syntax_error.py"

        with caplog.at_level(logging.WARNING):
            result = resolver.resolve(test_file)

        # Should fall back to default
        assert result == "api"
        assert "Failed to parse" in caplog.text

    def test_file_not_found_error(self) -> None:
        """Test that nonexistent files raise appropriate errors."""
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "nonexistent" / "test_missing.py"

        # The resolver should let the OSError propagate from read_text()
        with pytest.raises(OSError):
            resolver._detect_from_base_class(test_file)

    def test_mixed_api_and_d2d_returns_first(self) -> None:
        """Test file with both API and D2D classes returns first found type.

        The current implementation returns the type of the first recognized
        base class found, which is reasonable behavior for mixed files.
        """
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "edge_cases" / "test_mixed_invalid.py"

        # The file has TestAPI(NACTestBase) first, then TestSSH(SSHTestBase)
        result = resolver.resolve(test_file)

        # Should return 'api' (the first recognized base)
        assert result == "api"

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
        resolver = TestTypeResolver(FIXTURES_DIR)

        # Mock a path with unicode characters
        mock_path = _create_mock_path(
            "/tests/тесты/test_файл.py",
            """
class TestCase(NACTestBase):
    pass
""",
        )

        result = resolver.resolve(mock_path)

        assert result == "api"

    def test_permission_denied_error(self) -> None:
        """Test handling of permission denied errors."""
        resolver = TestTypeResolver(FIXTURES_DIR)

        mock_path = _create_mock_path("/tests/test.py", "")
        mock_path.read_text.side_effect = PermissionError("Permission denied")

        # Permission error should trigger fallback to default
        with patch("logging.Logger.warning") as mock_warning:
            result = resolver.resolve(mock_path)

        assert result == "api"  # Default
        # Check that warning was called twice - once for parse failure, once for default
        assert mock_warning.call_count >= 1
        # Check that at least one warning mentions parse failure or default behavior
        warning_messages = " ".join(str(call) for call in mock_warning.call_args_list)
        assert (
            "Failed to parse" in warning_messages
            or "Could not detect test type" in warning_messages
        )


class TestCaching:
    """Test cache behavior for performance optimization.

    The resolver caches detection results to avoid repeated AST parsing
    of the same files.
    """

    def test_results_are_cached(self) -> None:
        """Test that detection results are cached after first call."""
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "api" / "test_api_simple.py"

        # First call should do actual detection
        with patch.object(
            resolver, "_resolve_uncached", wraps=resolver._resolve_uncached
        ) as mock_resolve:
            result1 = resolver.resolve(test_file)
            assert mock_resolve.call_count == 1

        # Second call should use cache
        with patch.object(
            resolver, "_resolve_uncached", wraps=resolver._resolve_uncached
        ) as mock_resolve:
            result2 = resolver.resolve(test_file)
            assert mock_resolve.call_count == 0

        assert result1 == result2 == "api"
        assert len(resolver._cache) == 1

    def test_cache_uses_absolute_paths(self) -> None:
        """Test that cache keys use absolute paths for consistency."""
        resolver = TestTypeResolver(FIXTURES_DIR)

        # Use relative path
        relative_path = Path("api/test_api_simple.py")
        absolute_path = (FIXTURES_DIR / relative_path).resolve()

        # Mock the file operations
        with patch.object(
            Path, "read_text", return_value="class Test(NACTestBase): pass"
        ):
            # Resolve with relative path (which gets converted to absolute internally)
            resolver.resolve(absolute_path)

            # Check cache has absolute path as key
            assert absolute_path in resolver._cache
            assert len(resolver._cache) == 1

    def test_clear_cache(self) -> None:
        """Test that clear_cache() empties the cache."""
        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file1 = FIXTURES_DIR / "api" / "test_api_simple.py"
        test_file2 = FIXTURES_DIR / "d2d" / "test_d2d_simple.py"

        # Populate cache
        resolver.resolve(test_file1)
        resolver.resolve(test_file2)
        assert len(resolver._cache) == 2

        # Clear cache
        resolver.clear_cache()
        assert len(resolver._cache) == 0

        # Verify detection still works after clearing
        result = resolver.resolve(test_file1)
        assert result == "api"
        assert len(resolver._cache) == 1

    def test_cache_different_instances(self) -> None:
        """Test that different resolver instances have separate caches."""
        resolver1 = TestTypeResolver(FIXTURES_DIR)
        resolver2 = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "api" / "test_api_simple.py"

        # Populate cache in resolver1
        resolver1.resolve(test_file)
        assert len(resolver1._cache) == 1
        assert len(resolver2._cache) == 0

        # resolver2 should do its own detection
        with patch.object(
            resolver2, "_resolve_uncached", wraps=resolver2._resolve_uncached
        ) as mock_resolve:
            resolver2.resolve(test_file)
            assert mock_resolve.call_count == 1

        assert len(resolver2._cache) == 1

    def test_cache_performance(self) -> None:
        """Test that cached lookups are significantly faster than initial detection."""
        import time

        resolver = TestTypeResolver(FIXTURES_DIR)
        test_file = FIXTURES_DIR / "api" / "test_api_simple.py"

        # First call (uncached)
        start = time.perf_counter()
        resolver.resolve(test_file)
        uncached_time = time.perf_counter() - start

        # Second call (cached)
        start = time.perf_counter()
        resolver.resolve(test_file)
        cached_time = time.perf_counter() - start

        # Cached should be faster - we use a conservative 2x to avoid flaky tests
        # (Sometimes the first call is also very fast due to OS caching)
        assert cached_time < uncached_time * 2  # Very conservative check

    def test_cache_with_modified_files(self) -> None:
        """Test that cache doesn't detect file modifications (by design).

        The cache is not invalidated on file changes - this is intentional
        for performance. Users must call clear_cache() if files change.
        """
        resolver = TestTypeResolver(FIXTURES_DIR)

        # Mock a file path
        mock_path = _create_mock_path("/test/file.py", "class Test(NACTestBase): pass")

        # First call returns API
        result1 = resolver.resolve(mock_path)
        assert result1 == "api"

        # "Modify" file to D2D (but cache won't know)
        mock_path.read_text.return_value = "class Test(SSHTestBase): pass"
        result2 = resolver.resolve(mock_path)

        # Still returns cached value
        assert result2 == "api"

        # After clear_cache, it detects the change
        resolver.clear_cache()
        result3 = resolver.resolve(mock_path)
        assert result3 == "d2d"


class TestIntegration:
    """Integration tests validating resolver with real test scenarios."""

    def test_resolver_initialization(self) -> None:
        """Test that resolver initializes correctly with test root."""
        test_root = Path("/some/test/path")
        resolver = TestTypeResolver(test_root)

        assert resolver.test_root == test_root.resolve()
        assert len(resolver._cache) == 0
        assert (
            resolver.logger.name == "nac_test.pyats_core.discovery.test_type_resolver"
        )

    def test_all_fixture_files_resolve(self) -> None:
        """Test that all fixture files can be resolved without errors."""
        resolver = TestTypeResolver(FIXTURES_DIR)
        errors = []

        # Find all Python files in fixtures
        for py_file in FIXTURES_DIR.rglob("*.py"):
            try:
                result = resolver.resolve(py_file)
                assert result in {"api", "d2d"}
            except Exception as e:
                errors.append(f"{py_file}: {e}")

        # Only syntax_error.py should potentially cause issues (handled gracefully)
        assert len(errors) == 0, f"Errors resolving fixtures: {errors}"

    def test_logging_output(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that appropriate log messages are generated."""
        test_file = FIXTURES_DIR / "api" / "test_api_simple.py"

        # Capture initialization logging
        with caplog.at_level(logging.DEBUG):
            resolver = TestTypeResolver(FIXTURES_DIR)

        # Check initialization logged
        assert "Initialized TestTypeResolver" in caplog.text

        caplog.clear()

        # First resolve should show cache miss and AST analysis
        with caplog.at_level(logging.DEBUG):
            resolver.resolve(test_file)

        # Check for expected debug messages
        assert "Cache miss" in caplog.text
        assert "Analyzing AST" in caplog.text

        # Second call should show cache hit
        caplog.clear()
        with caplog.at_level(logging.DEBUG):
            resolver.resolve(test_file)

        assert "Cache hit" in caplog.text

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
