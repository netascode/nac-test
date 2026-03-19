# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for TestDiscovery class.

This module tests the TestDiscovery class which handles PyATS test file
discovery and categorization.

Test Structure:
    - TestDiscoveryFiltering: Tests file filtering and skip logic
    - TestRelaxedPathRequirements: Tests arbitrary directory structure support
    - TestExcludePaths: Tests directory exclusion functionality
    - TestErrorHandling: Tests error handling during discovery
"""

from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture

from nac_test.pyats_core.discovery.test_discovery import TestDiscovery

# =============================================================================
# Test Content Templates
# =============================================================================

VALID_PYATS_TEST = """\
from pyats import aetest
from nac_test import runtime

class Test(aetest.Testcase):
    @aetest.test
    def test_something(self):
        pass
"""

VALID_API_TEST = """\
from pyats import aetest
from nac_test.pyats_core.common.base_test import NACTestBase

class TestAPI(NACTestBase):
    @aetest.test
    def test_api(self):
        pass
"""

VALID_D2D_TEST = """\
from pyats import aetest
from nac_test.pyats_core.common.ssh_base_test import SSHTestBase

class TestD2D(SSHTestBase):
    @aetest.test
    def test_d2d(self):
        pass
"""

NO_NAC_TEST_IMPORT = """\
from pyats import aetest

class ThirdParty(aetest.Testcase):
    @aetest.test
    def test_third_party(self):
        pass
"""

NO_AETEST_DECORATOR = """\
from nac_test import runtime

class Helper:
    def helper_method(self):
        pass
"""


# =============================================================================
# TestDiscoveryFiltering
# =============================================================================


class TestDiscoveryFiltering:
    """Test file filtering and skip logic during discovery.

    These tests verify that various files are correctly skipped during
    discovery (pycache, underscore-prefixed, __init__.py, etc).
    """

    @pytest.mark.parametrize(
        ("extra_file_path", "extra_file_content", "skip_marker"),
        [
            # __pycache__ directories skipped
            ("test/__pycache__/verify_cached.py", VALID_PYATS_TEST, "__pycache__"),
            # Underscore-prefixed files skipped
            ("test/_helper.py", VALID_PYATS_TEST, "_helper.py"),
            # __init__.py files skipped
            ("test/__init__.py", VALID_PYATS_TEST, "__init__.py"),
        ],
        ids=["pycache", "underscore-prefixed", "init-file"],
    )
    def test_skips_special_paths(
        self,
        tmp_path: Path,
        extra_file_path: str,
        extra_file_content: str,
        skip_marker: str,
    ) -> None:
        """Test that special paths are correctly skipped."""
        # Create a valid test file
        test_dir = tmp_path / "test"
        test_dir.mkdir(parents=True)
        (test_dir / "verify_test.py").write_text(VALID_PYATS_TEST)

        # Create the file that should be skipped
        skip_file = tmp_path / extra_file_path
        skip_file.parent.mkdir(parents=True, exist_ok=True)
        skip_file.write_text(extra_file_content)

        discovery = TestDiscovery(tmp_path)
        plan = discovery.discover_pyats_tests()

        assert plan.total_count == 1
        assert "verify_test.py" in str(plan.all_tests[0])
        assert not any(skip_marker in str(t.path) for t in plan.all_tests)

    @pytest.mark.parametrize(
        ("extra_file_path", "extra_file_content", "expected_skip_reason"),
        [
            # Files without @aetest decorators → skipped with reason
            ("test/helper_module.py", NO_AETEST_DECORATOR, "helper_module.py"),
            # Files without nac_test imports → skipped with reason
            ("test/third_party_test.py", NO_NAC_TEST_IMPORT, "third_party_test.py"),
        ],
        ids=["no-decorator", "no-nac-test-import"],
    )
    def test_skips_invalid_pyats_files(
        self,
        tmp_path: Path,
        extra_file_path: str,
        extra_file_content: str,
        expected_skip_reason: str,
    ) -> None:
        """Test that invalid PyATS files are skipped and recorded."""
        # Create a valid test file
        test_dir = tmp_path / "test"
        test_dir.mkdir(parents=True)
        (test_dir / "verify_test.py").write_text(VALID_PYATS_TEST)

        # Create the file that should be skipped
        skip_file = tmp_path / extra_file_path
        skip_file.parent.mkdir(parents=True, exist_ok=True)
        skip_file.write_text(extra_file_content)

        discovery = TestDiscovery(tmp_path)
        plan = discovery.discover_pyats_tests()

        assert plan.total_count == 1
        assert "verify_test.py" in str(plan.all_tests[0])
        # The invalid file should be in skipped list
        skipped_names = [str(p) for p, _ in plan.skipped_files]
        assert any(expected_skip_reason in name for name in skipped_names)

    def test_skipped_files_recorded_with_many_files(self, tmp_path: Path) -> None:
        """Test that all skipped files are recorded in the result."""
        test_dir = tmp_path / "test"
        test_dir.mkdir(parents=True)

        # Create one valid test file
        (test_dir / "verify_test.py").write_text(VALID_PYATS_TEST)

        # Create 7 files without proper imports (will be skipped)
        for i in range(7):
            (test_dir / f"invalid_test_{i}.py").write_text(NO_NAC_TEST_IMPORT)

        discovery = TestDiscovery(tmp_path)
        plan = discovery.discover_pyats_tests()

        assert plan.total_count == 1
        assert len(plan.skipped_files) == 7

    @pytest.mark.parametrize(
        ("files", "expected_has_tests"),
        [
            # Valid test found among non-python files
            (
                {
                    "test/README.md": "# Readme",
                    "test/config.yaml": "key: value",
                    "test/verify_test.py": VALID_PYATS_TEST,
                },
                True,
            ),
            # Only non-python files
            (
                {
                    "test/README.md": "# Readme",
                    "test/config.yaml": "key: value",
                },
                False,
            ),
        ],
        ids=["with-valid-test", "only-non-python"],
    )
    def test_has_pyats_tests_ignores_non_python(
        self, tmp_path: Path, files: dict[str, str], expected_has_tests: bool
    ) -> None:
        """Test that has_pyats_tests() correctly handles non-Python files."""
        for relpath, content in files.items():
            path = tmp_path / relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

        discovery = TestDiscovery(tmp_path)
        assert discovery.has_pyats_tests() is expected_has_tests


# =============================================================================
# TestRelaxedPathRequirements
# =============================================================================


class TestRelaxedPathRequirements:
    """Tests for issue #475: Relax path requirements for PyATS test discovery.

    These tests verify that the /test/ or /tests/ directory requirement has been
    removed, allowing arbitrary directory naming conventions like tests-mini/.
    """

    @pytest.mark.parametrize(
        "dir_structure",
        [
            # Arbitrary directory name (tests-mini/)
            "tests-mini/features/verify_feature.py",
            # Root level test file
            "verify_root.py",
            # Custom project structure
            "src/validation/network/verify_connectivity.py",
        ],
        ids=["tests-mini", "root-level", "custom-structure"],
    )
    def test_arbitrary_directory_structures(
        self, tmp_path: Path, dir_structure: str
    ) -> None:
        """Test that tests are discovered in arbitrary directory structures."""
        test_file = tmp_path / dir_structure
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(VALID_API_TEST)

        discovery = TestDiscovery(tmp_path)
        plan = discovery.discover_pyats_tests()

        assert plan.total_count == 1

    @pytest.mark.parametrize(
        ("setup", "exclude_dirs", "expected"),
        [
            # has_pyats_tests returns True on first match
            ({"tests/verify_test.py": VALID_API_TEST}, [], True),
            # has_pyats_tests returns False when no valid tests
            ({"tests/verify_test.py": NO_NAC_TEST_IMPORT}, [], False),
            # has_pyats_tests respects exclude_paths
            ({"excluded/verify_test.py": VALID_API_TEST}, ["excluded"], False),
        ],
        ids=["finds-valid-test", "no-valid-tests", "respects-exclude"],
    )
    def test_has_pyats_tests_behavior(
        self,
        tmp_path: Path,
        setup: dict[str, str],
        exclude_dirs: list[str],
        expected: bool,
    ) -> None:
        """Test has_pyats_tests() with various configurations."""
        for relpath, content in setup.items():
            path = tmp_path / relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

        exclude = [tmp_path / p for p in exclude_dirs]
        discovery = TestDiscovery(tmp_path, exclude_paths=exclude)
        assert discovery.has_pyats_tests() == expected


# =============================================================================
# TestExcludePaths
# =============================================================================


class TestExcludePaths:
    """Test directory exclusion functionality.

    These tests verify that specific directories can be excluded from
    discovery, which is needed for --filters and --tests CLI paths that
    contain Jinja Python modules (not PyATS tests).
    """

    @pytest.mark.parametrize(
        ("exclude_files", "exclude_dirs", "expected_excluded"),
        [
            # Single directory excluded
            (
                {"filters/custom_filter.py": VALID_PYATS_TEST},
                ["filters"],
                ["custom_filter.py"],
            ),
            # Multiple directories excluded
            (
                {
                    "filters/filter.py": VALID_PYATS_TEST,
                    "jinja_tests/jinja_test.py": VALID_PYATS_TEST,
                },
                ["filters", "jinja_tests"],
                ["filter.py", "jinja_test.py"],
            ),
            # Nested directory excluded
            (
                {"helpers/jinja/nested/deep/helper.py": VALID_PYATS_TEST},
                ["helpers/jinja"],
                ["helper.py"],
            ),
        ],
        ids=["single-dir", "multiple-dirs", "nested-dir"],
    )
    def test_exclude_paths(
        self,
        tmp_path: Path,
        exclude_files: dict[str, str],
        exclude_dirs: list[str],
        expected_excluded: list[str],
    ) -> None:
        """Test that specified directories are excluded from discovery."""
        # Create files that should be excluded
        for relpath, content in exclude_files.items():
            path = tmp_path / relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

        # Create a valid test file that should be included
        test_dir = tmp_path / "test" / "api"
        test_dir.mkdir(parents=True)
        (test_dir / "verify_test.py").write_text(VALID_API_TEST)

        exclude = [tmp_path / d for d in exclude_dirs]
        discovery = TestDiscovery(tmp_path, exclude_paths=exclude)
        plan = discovery.discover_pyats_tests()

        assert plan.total_count == 1
        assert "verify_test.py" in str(plan.all_tests[0])
        # Verify excluded files are not in results
        for excluded_name in expected_excluded:
            assert not any(excluded_name in str(t.path) for t in plan.all_tests)


# =============================================================================
# TestErrorHandling
# =============================================================================


class TestErrorHandling:
    """Test error handling during discovery."""

    def test_unreadable_file_skipped_in_has_pyats_tests(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """Test that unreadable files are skipped in has_pyats_tests()."""
        test_dir = tmp_path / "test"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "verify_test.py"
        test_file.write_text(VALID_PYATS_TEST)

        # Mock read_text to raise OSError for this specific file
        original_read_text = Path.read_text

        def mock_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
            if "verify_test.py" in str(self):
                raise OSError("Permission denied")
            return original_read_text(self, *args, **kwargs)

        mocker.patch.object(Path, "read_text", mock_read_text)

        discovery = TestDiscovery(tmp_path)
        # Should not raise, should return False (no readable tests)
        assert discovery.has_pyats_tests() is False

    def test_unreadable_file_skipped_in_discover(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """Test that unreadable files are logged and skipped in discover_pyats_tests()."""
        test_dir = tmp_path / "test"
        test_dir.mkdir(parents=True)

        good_file = test_dir / "verify_good.py"
        good_file.write_text(VALID_PYATS_TEST)

        bad_file = test_dir / "verify_bad.py"
        bad_file.write_text(VALID_PYATS_TEST)

        original_read_text = Path.read_text

        def mock_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
            if "verify_bad.py" in str(self):
                raise OSError("Permission denied")
            return original_read_text(self, *args, **kwargs)

        mocker.patch.object(Path, "read_text", mock_read_text)

        discovery = TestDiscovery(tmp_path)
        plan = discovery.discover_pyats_tests()

        # Good file should be discovered, bad file should be in skipped
        assert plan.total_count == 1
        assert len(plan.skipped_files) == 1
        assert "Permission denied" in plan.skipped_files[0][1]
