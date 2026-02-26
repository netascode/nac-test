# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Integration tests for TestDiscovery with TestTypeResolver.

This module validates the integration between TestDiscovery and TestTypeResolver,
testing the three-tier test type detection strategy:

    1. **AST Analysis** (Primary): Base class inheritance detection
    2. **Directory Fallback**: /api/ or /d2d/ path detection
    3. **Default**: Falls back to 'api' with warning

Test Categories:
    - TestBaseClassDetection: Tests AST-based base class detection (primary method)
    - TestDirectoryFallback: Tests directory path fallback when no base class found
    - TestDefaultBehavior: Tests default-to-api when neither AST nor directory works
    - TestEdgeCases: Tests mixed scenarios and error handling
    - TestRelaxedPathRequirements: Tests for issue #475 - arbitrary directory naming
    - TestExcludePaths: Tests directory exclusion functionality
"""

from pathlib import Path

from nac_test.pyats_core.discovery.test_discovery import TestDiscovery


class TestBaseClassDetection:
    """Test AST-based base class detection (primary classification method).

    These tests verify that test type is correctly determined by analyzing
    base class inheritance. This is the highest priority detection method.
    """

    def test_nac_test_base_detected_as_api(self, tmp_path: Path) -> None:
        """Test that NACTestBase inheritance is detected as API type."""
        feature_dir = tmp_path / "test" / "tenant" / "operational"
        feature_dir.mkdir(parents=True)

        test_file = feature_dir / "verify_tenant.py"
        test_file.write_text("""
from pyats import aetest
from nac_test.pyats_core.common.base_test import NACTestBase

class TestTenant(NACTestBase):
    @aetest.test
    def test_tenant_config(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        assert len(api_tests) == 1
        assert len(d2d_tests) == 0

    def test_ssh_test_base_detected_as_d2d(self, tmp_path: Path) -> None:
        """Test that SSHTestBase inheritance is detected as D2D type."""
        feature_dir = tmp_path / "test" / "routing" / "operational"
        feature_dir.mkdir(parents=True)

        test_file = feature_dir / "verify_ospf.py"
        test_file.write_text("""
from pyats import aetest
from nac_test.pyats_core.common.ssh_base_test import SSHTestBase

class TestOSPF(SSHTestBase):
    @aetest.test
    def test_ospf_neighbors(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        assert len(api_tests) == 0
        assert len(d2d_tests) == 1

    def test_base_class_takes_priority_over_directory(self, tmp_path: Path) -> None:
        """Test that base class detection has priority over directory path.

        A test file with SSHTestBase inheritance placed in /api/ directory
        should still be classified as D2D because AST detection has priority.
        """
        # Create test in /api/ directory but with D2D base class
        api_dir = tmp_path / "test" / "api" / "operational"
        api_dir.mkdir(parents=True)

        test_file = api_dir / "verify_device_ssh.py"
        test_file.write_text("""
from pyats import aetest
from nac_test.pyats_core.common.ssh_base_test import SSHTestBase

class TestDeviceSSH(SSHTestBase):
    '''Even though in /api/ directory, should be D2D due to base class.'''
    @aetest.test
    def test_device_connectivity(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        # Should be D2D based on base class (AST priority)
        assert len(api_tests) == 0
        assert len(d2d_tests) == 1

    def test_architecture_specific_api_base_classes(self, tmp_path: Path) -> None:
        """Test detection of architecture-specific API base classes."""
        test_dir = tmp_path / "test" / "aci" / "operational"
        test_dir.mkdir(parents=True)

        test_file = test_dir / "verify_epg.py"
        test_file.write_text("""
from pyats import aetest
from nac_test import runtime

class APICTestBase:
    '''Simulated architecture base.'''
    pass

class TestEPG(APICTestBase):
    @aetest.test
    def test_epg_config(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        # APICTestBase should be detected as API
        assert len(api_tests) == 1
        assert len(d2d_tests) == 0

    def test_architecture_specific_d2d_base_classes(self, tmp_path: Path) -> None:
        """Test detection of architecture-specific D2D base classes."""
        test_dir = tmp_path / "test" / "ios" / "operational"
        test_dir.mkdir(parents=True)

        test_file = test_dir / "verify_interfaces.py"
        test_file.write_text("""
from pyats import aetest
from nac_test import runtime

class IOSXETestBase:
    '''Simulated IOS-XE base.'''
    pass

class TestInterfaces(IOSXETestBase):
    @aetest.test
    def test_interface_status(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        # IOSXETestBase should be detected as D2D
        assert len(api_tests) == 0
        assert len(d2d_tests) == 1


class TestDirectoryFallback:
    """Test directory-based fallback when no recognized base class is found.

    When AST analysis doesn't find a known base class (e.g., test inherits from
    aetest.Testcase directly), the resolver falls back to checking for /api/ or
    /d2d/ in the file path.
    """

    def test_api_directory_fallback(self, tmp_path: Path) -> None:
        """Test that /api/ in path triggers API classification when no base class."""
        api_dir = tmp_path / "test" / "api" / "operational"
        api_dir.mkdir(parents=True)

        # Uses aetest.Testcase (not a known base), so falls back to directory
        test_file = api_dir / "verify_tenant.py"
        test_file.write_text("""
from pyats import aetest
from nac_test import runtime

class TestTenant(aetest.Testcase):
    @aetest.test
    def test_tenant_exists(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        assert len(api_tests) == 1
        assert len(d2d_tests) == 0
        assert "verify_tenant.py" in str(api_tests[0])

    def test_d2d_directory_fallback(self, tmp_path: Path) -> None:
        """Test that /d2d/ in path triggers D2D classification when no base class."""
        d2d_dir = tmp_path / "test" / "d2d" / "operational"
        d2d_dir.mkdir(parents=True)

        # Uses aetest.Testcase (not a known base), so falls back to directory
        test_file = d2d_dir / "verify_routing.py"
        test_file.write_text("""
from pyats import aetest
from nac_test import runtime

class TestRouting(aetest.Testcase):
    @aetest.test
    def test_routing_table(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        assert len(api_tests) == 0
        assert len(d2d_tests) == 1
        assert "verify_routing.py" in str(d2d_tests[0])

    def test_mixed_api_and_d2d_directories(self, tmp_path: Path) -> None:
        """Test directory fallback with both /api/ and /d2d/ directories."""
        api_dir = tmp_path / "test" / "api" / "operational"
        d2d_dir = tmp_path / "test" / "d2d" / "operational"
        api_dir.mkdir(parents=True)
        d2d_dir.mkdir(parents=True)

        # Both use aetest.Testcase, so both fall back to directory
        (api_dir / "verify_api.py").write_text("""
from pyats import aetest
from nac_test import runtime

class TestAPI(aetest.Testcase):
    @aetest.test
    def test_api(self):
        pass
""")

        (d2d_dir / "verify_ssh.py").write_text("""
from pyats import aetest
from nac_test import runtime

class TestSSH(aetest.Testcase):
    @aetest.test
    def test_ssh(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        assert len(api_tests) == 1
        assert len(d2d_tests) == 1
        assert "verify_api.py" in str(api_tests[0])
        assert "verify_ssh.py" in str(d2d_tests[0])

    def test_nested_d2d_directory(self, tmp_path: Path) -> None:
        """Test that deeply nested /d2d/ paths are detected."""
        nested_dir = tmp_path / "test" / "features" / "d2d" / "routing" / "ospf"
        nested_dir.mkdir(parents=True)

        test_file = nested_dir / "verify_ospf.py"
        test_file.write_text("""
from pyats import aetest
from nac_test import runtime

class TestOSPF(aetest.Testcase):
    @aetest.test
    def test_ospf(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        assert len(api_tests) == 0
        assert len(d2d_tests) == 1


class TestDefaultBehavior:
    """Test default-to-api behavior when neither base class nor directory works.

    When AST analysis finds no known base class AND the path doesn't contain
    /api/ or /d2d/, the resolver defaults to 'api' type with a warning.
    """

    def test_unknown_base_class_no_directory_defaults_to_api(
        self, tmp_path: Path
    ) -> None:
        """Test that unknown base class without /api/ or /d2d/ defaults to API."""
        # Path has neither /api/ nor /d2d/
        test_dir = tmp_path / "test" / "random" / "operational"
        test_dir.mkdir(parents=True)

        test_file = test_dir / "verify_custom.py"
        test_file.write_text("""
from pyats import aetest
from nac_test import runtime

class CustomTestBase:
    '''Unknown base class - not in BASE_CLASS_MAPPING.'''
    pass

class TestCustom(CustomTestBase):
    @aetest.test
    def test_custom(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        # Should default to API
        assert len(api_tests) == 1
        assert len(d2d_tests) == 0

    def test_aetest_testcase_no_directory_defaults_to_api(self, tmp_path: Path) -> None:
        """Test that aetest.Testcase without /api/ or /d2d/ defaults to API."""
        # Path has neither /api/ nor /d2d/
        test_dir = tmp_path / "test" / "features" / "networking"
        test_dir.mkdir(parents=True)

        test_file = test_dir / "verify_feature.py"
        test_file.write_text("""
from pyats import aetest
from nac_test import runtime

class TestFeature(aetest.Testcase):
    @aetest.test
    def test_feature(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        # Should default to API
        assert len(api_tests) == 1
        assert len(d2d_tests) == 0


class TestEdgeCases:
    """Test edge cases and error handling scenarios."""

    def test_multiple_test_files_mixed_types(self, tmp_path: Path) -> None:
        """Test discovery with multiple files of different types."""
        # Create feature-based structure with mixed test types
        feature_dir = tmp_path / "test" / "vrf" / "operational"
        feature_dir.mkdir(parents=True)

        # API test using NACTestBase
        api_file = feature_dir / "verify_vrf_api.py"
        api_file.write_text("""
from pyats import aetest
from nac_test.pyats_core.common.base_test import NACTestBase

class TestVRFApi(NACTestBase):
    @aetest.test
    def test_vrf_via_api(self):
        pass
""")

        # D2D test using SSHTestBase
        d2d_file = feature_dir / "verify_vrf_ssh.py"
        d2d_file.write_text("""
from pyats import aetest
from nac_test.pyats_core.common.ssh_base_test import SSHTestBase

class TestVRFDevice(SSHTestBase):
    @aetest.test
    def test_vrf_via_ssh(self):
        pass
""")

        # Discover and categorize
        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        # Both types should be detected in same directory
        assert len(api_tests) == 1
        assert len(d2d_tests) == 1
        assert "verify_vrf_api.py" in str(api_tests[0])
        assert "verify_vrf_ssh.py" in str(d2d_tests[0])

    def test_no_test_files_returns_empty(self, tmp_path: Path) -> None:
        """Test that empty directories return empty lists."""
        # Create empty test structure
        test_dir = tmp_path / "test" / "empty"
        test_dir.mkdir(parents=True)

        # Discover and categorize
        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        assert len(api_tests) == 0
        assert len(d2d_tests) == 0

    def test_deep_nested_feature_structure(self, tmp_path: Path) -> None:
        """Test detection in deeply nested feature directories."""
        # Create deeply nested structure
        deep_dir = tmp_path / "test" / "features" / "networking" / "routing" / "ospf"
        deep_dir.mkdir(parents=True)

        test_file = deep_dir / "verify_ospf_neighbors.py"
        test_file.write_text("""
from pyats import aetest
from nac_test.pyats_core.common.ssh_base_test import SSHTestBase

class TestOSPFNeighbors(SSHTestBase):
    @aetest.test
    def test_ospf_neighbor_count(self):
        pass
""")

        # Discover and categorize
        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        # Should detect D2D even in deeply nested structure
        assert len(api_tests) == 0
        assert len(d2d_tests) == 1


class TestDiscoveryFiltering:
    """Test file filtering and skip logic during discovery.

    These tests verify that various files are correctly skipped during
    discovery (pycache, underscore-prefixed, __init__.py, etc).
    """

    def test_skips_pycache_directories(self, tmp_path: Path) -> None:
        """Test that __pycache__ directories are skipped."""
        test_dir = tmp_path / "test"
        test_dir.mkdir(parents=True)

        # Create a valid test file
        (test_dir / "verify_test.py").write_text("""
from pyats import aetest
from nac_test import runtime

class Test(aetest.Testcase):
    @aetest.test
    def test_something(self):
        pass
""")

        # Create a file inside __pycache__ that looks like a test
        pycache_dir = test_dir / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "verify_cached.py").write_text("""
from pyats import aetest
from nac_test import runtime

class Test(aetest.Testcase):
    @aetest.test
    def test_something(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()

        assert len(files) == 1
        assert "verify_test.py" in str(files[0])
        assert not any("__pycache__" in str(f) for f in files)

    def test_skips_underscore_prefixed_files(self, tmp_path: Path) -> None:
        """Test that files starting with underscore are skipped."""
        test_dir = tmp_path / "test"
        test_dir.mkdir(parents=True)

        # Create a valid test file
        (test_dir / "verify_test.py").write_text("""
from pyats import aetest
from nac_test import runtime

class Test(aetest.Testcase):
    @aetest.test
    def test_something(self):
        pass
""")

        # Create underscore-prefixed file that looks like a test
        (test_dir / "_helper.py").write_text("""
from pyats import aetest
from nac_test import runtime

class Helper(aetest.Testcase):
    @aetest.test
    def helper_method(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()

        assert len(files) == 1
        assert "verify_test.py" in str(files[0])
        assert not any("_helper.py" in str(f) for f in files)

    def test_skips_init_files(self, tmp_path: Path) -> None:
        """Test that __init__.py files are skipped."""
        test_dir = tmp_path / "test"
        test_dir.mkdir(parents=True)

        # Create a valid test file
        (test_dir / "verify_test.py").write_text("""
from pyats import aetest
from nac_test import runtime

class Test(aetest.Testcase):
    @aetest.test
    def test_something(self):
        pass
""")

        # Create __init__.py with test-like content
        (test_dir / "__init__.py").write_text("""
from pyats import aetest
from nac_test import runtime

class Init(aetest.Testcase):
    @aetest.test
    def init_test(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()

        assert len(files) == 1
        assert "verify_test.py" in str(files[0])
        assert not any("__init__.py" in str(f) for f in files)

    def test_skips_files_without_aetest_decorators(self, tmp_path: Path) -> None:
        """Test that files with nac_test import but no @aetest decorators are skipped."""
        test_dir = tmp_path / "test"
        test_dir.mkdir(parents=True)

        # Create a valid test file
        (test_dir / "verify_test.py").write_text("""
from pyats import aetest
from nac_test import runtime

class Test(aetest.Testcase):
    @aetest.test
    def test_something(self):
        pass
""")

        # Create file with nac_test import but no decorators
        (test_dir / "helper_module.py").write_text("""
from nac_test import runtime

class Helper:
    def helper_method(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, skipped = discovery.discover_pyats_tests()

        assert len(files) == 1
        assert "verify_test.py" in str(files[0])
        # The helper file should be in skipped list
        skipped_names = [str(p) for p, _ in skipped]
        assert any("helper_module.py" in name for name in skipped_names)

    def test_skips_files_without_nac_test_imports(self, tmp_path: Path) -> None:
        """Test that files without nac_test imports are skipped."""
        test_dir = tmp_path / "test"
        test_dir.mkdir(parents=True)

        # Create a valid test file
        (test_dir / "verify_test.py").write_text("""
from pyats import aetest
from nac_test import runtime

class Test(aetest.Testcase):
    @aetest.test
    def test_something(self):
        pass
""")

        # Create file with @aetest decorator but no nac_test import
        (test_dir / "third_party_test.py").write_text("""
from pyats import aetest

class ThirdParty(aetest.Testcase):
    @aetest.test
    def test_third_party(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, skipped = discovery.discover_pyats_tests()

        assert len(files) == 1
        assert "verify_test.py" in str(files[0])
        # The third party file should be in skipped list
        skipped_names = [str(p) for p, _ in skipped]
        assert any("third_party_test.py" in name for name in skipped_names)

    def test_skipped_files_logging_with_many_files(self, tmp_path: Path) -> None:
        """Test that skipped files logging truncates after 5 files."""
        test_dir = tmp_path / "test"
        test_dir.mkdir(parents=True)

        # Create one valid test file
        (test_dir / "verify_test.py").write_text("""
from pyats import aetest
from nac_test import runtime

class Test(aetest.Testcase):
    @aetest.test
    def test_something(self):
        pass
""")

        # Create 7 files without proper imports (will be skipped)
        for i in range(7):
            (test_dir / f"invalid_test_{i}.py").write_text("""
from pyats import aetest

class Invalid(aetest.Testcase):
    @aetest.test
    def test_invalid(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, skipped = discovery.discover_pyats_tests()

        assert len(files) == 1
        assert len(skipped) == 7  # All 7 invalid files should be skipped

    def test_has_pyats_tests_skips_non_python_files(self, tmp_path: Path) -> None:
        """Test that has_pyats_tests() skips non-.py files."""
        test_dir = tmp_path / "test"
        test_dir.mkdir(parents=True)

        # Create non-Python files
        (test_dir / "README.md").write_text("# Test README")
        (test_dir / "config.yaml").write_text("key: value")
        (test_dir / "data.json").write_text("{}")

        # Create a valid test file
        (test_dir / "verify_test.py").write_text("""
from pyats import aetest
from nac_test import runtime

class Test(aetest.Testcase):
    @aetest.test
    def test_something(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        # has_pyats_tests should return True (found valid test) and skip non-.py files
        assert discovery.has_pyats_tests() is True

    def test_has_pyats_tests_only_non_python_files(self, tmp_path: Path) -> None:
        """Test that has_pyats_tests() returns False with only non-.py files."""
        test_dir = tmp_path / "test"
        test_dir.mkdir(parents=True)

        # Create only non-Python files
        (test_dir / "README.md").write_text("# Test README")
        (test_dir / "config.yaml").write_text("key: value")

        discovery = TestDiscovery(tmp_path)
        assert discovery.has_pyats_tests() is False


class TestDiscoveryPerformance:
    """Performance tests for the discovery mechanism."""

    def test_categorization_performance(self, tmp_path: Path) -> None:
        """Test that categorization completes quickly even with many files.

        Creates 50 test files and verifies categorization completes in
        reasonable time (<5 seconds for all files).
        """
        import time

        # Create 50 test files (25 API, 25 D2D)
        test_dir = tmp_path / "test" / "performance"
        test_dir.mkdir(parents=True)

        for i in range(25):
            # API test
            api_file = test_dir / f"verify_api_{i}.py"
            api_file.write_text(f"""
from pyats import aetest
from nac_test.pyats_core.common.base_test import NACTestBase

class TestAPI{i}(NACTestBase):
    @aetest.test
    def test_api(self):
        pass
""")
            # D2D test
            d2d_file = test_dir / f"verify_d2d_{i}.py"
            d2d_file.write_text(f"""
from pyats import aetest
from nac_test.pyats_core.common.ssh_base_test import SSHTestBase

class TestD2D{i}(SSHTestBase):
    @aetest.test
    def test_d2d(self):
        pass
""")

        # Time the categorization
        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()

        start_time = time.perf_counter()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)
        elapsed = time.perf_counter() - start_time

        # Verify results
        assert len(api_tests) == 25
        assert len(d2d_tests) == 25

        # Should complete in under 8 seconds (generous bound)
        # Note: I have seen consistent failures under python 3.13 github runner, so increasing
        # bound to 8s for now, but locally it should be much faster (~1s)
        assert elapsed < 8.0, f"Categorization took {elapsed:.2f}s, expected <8s"


class TestRelaxedPathRequirements:
    """Tests for issue #475: Relax path requirements for PyATS test discovery.

    These tests verify that the /test/ or /tests/ directory requirement has been
    removed, allowing arbitrary directory naming conventions like tests-mini/.
    """

    def test_arbitrary_directory_name_tests_mini(self, tmp_path: Path) -> None:
        """Test that tests work in arbitrarily named directories like tests-mini/."""
        arbitrary_dir = tmp_path / "tests-mini" / "features"
        arbitrary_dir.mkdir(parents=True)

        test_file = arbitrary_dir / "verify_feature.py"
        test_file.write_text("""
from pyats import aetest
from nac_test.pyats_core.common.base_test import NACTestBase

class TestFeature(NACTestBase):
    @aetest.test
    def test_feature(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()

        assert len(files) == 1
        assert "verify_feature.py" in str(files[0])

    def test_root_level_test_file(self, tmp_path: Path) -> None:
        """Test that test files at root level are discovered."""
        test_file = tmp_path / "verify_root.py"
        test_file.write_text("""
from pyats import aetest
from nac_test.pyats_core.common.base_test import NACTestBase

class TestRoot(NACTestBase):
    @aetest.test
    def test_root(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()

        assert len(files) == 1
        assert "verify_root.py" in str(files[0])

    def test_custom_project_structure(self, tmp_path: Path) -> None:
        """Test discovery in completely custom project structures."""
        custom_dir = tmp_path / "src" / "validation" / "network"
        custom_dir.mkdir(parents=True)

        test_file = custom_dir / "verify_connectivity.py"
        test_file.write_text("""
from pyats import aetest
from nac_test.pyats_core.common.ssh_base_test import SSHTestBase

class TestConnectivity(SSHTestBase):
    @aetest.test
    def test_ping(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        assert len(files) == 1
        assert len(d2d_tests) == 1
        assert "verify_connectivity.py" in str(files[0])

    def test_has_pyats_tests_returns_true_on_first_match(self, tmp_path: Path) -> None:
        """Test that has_pyats_tests() returns True and exits early on first match."""
        test_dir = tmp_path / "tests"
        test_dir.mkdir(parents=True)

        test_file = test_dir / "verify_test.py"
        test_file.write_text("""
from pyats import aetest
from nac_test.pyats_core.common.base_test import NACTestBase

class TestSomething(NACTestBase):
    @aetest.test
    def test_something(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        assert discovery.has_pyats_tests() is True

    def test_has_pyats_tests_returns_false_when_no_tests(self, tmp_path: Path) -> None:
        """Test that has_pyats_tests() returns False when no valid tests exist."""
        test_dir = tmp_path / "tests"
        test_dir.mkdir(parents=True)

        # Create a file without pyats import - should not be detected
        test_file = test_dir / "verify_test.py"
        test_file.write_text("""
import os

class TestSomething:
    def test_something(self):
        pass
""")

        discovery = TestDiscovery(tmp_path)
        assert discovery.has_pyats_tests() is False

    def test_has_pyats_tests_respects_exclude_paths(self, tmp_path: Path) -> None:
        """Test that has_pyats_tests() respects exclude_paths."""
        excluded_dir = tmp_path / "excluded"
        excluded_dir.mkdir(parents=True)

        test_file = excluded_dir / "verify_test.py"
        test_file.write_text("""
from pyats import aetest
from nac_test.pyats_core.common.base_test import NACTestBase

class TestSomething(NACTestBase):
    @aetest.test
    def test_something(self):
        pass
""")

        discovery = TestDiscovery(tmp_path, exclude_paths=[excluded_dir])
        assert discovery.has_pyats_tests() is False


class TestExcludePaths:
    """Test directory exclusion functionality.

    These tests verify that specific directories can be excluded from
    discovery, which is needed for --filters and --tests CLI paths that
    contain Jinja Python modules (not PyATS tests).
    """

    def test_exclude_single_directory(self, tmp_path: Path) -> None:
        """Test that a single directory can be excluded from discovery."""
        filters_dir = tmp_path / "filters"
        filters_dir.mkdir(parents=True)

        # This file looks like a PyATS test but should be excluded
        filter_file = filters_dir / "custom_filter.py"
        filter_file.write_text("""
from pyats import aetest
from nac_test.pyats_core.common.base_test import NACTestBase

class Filter:
    name = "custom_filter"

    @aetest.test
    def filter(cls, data):
        return data
""")

        test_dir = tmp_path / "test" / "api"
        test_dir.mkdir(parents=True)

        test_file = test_dir / "verify_test.py"
        test_file.write_text("""
from pyats import aetest
from nac_test.pyats_core.common.base_test import NACTestBase

class TestSomething(NACTestBase):
    @aetest.test
    def test_something(self):
        pass
""")

        discovery = TestDiscovery(tmp_path, exclude_paths=[filters_dir])
        files, _ = discovery.discover_pyats_tests()

        assert len(files) == 1
        assert "verify_test.py" in str(files[0])
        assert not any("custom_filter.py" in str(f) for f in files)

    def test_exclude_multiple_directories(self, tmp_path: Path) -> None:
        """Test excluding multiple directories."""
        filters_dir = tmp_path / "filters"
        jinja_tests_dir = tmp_path / "jinja_tests"
        test_dir = tmp_path / "test" / "api"

        filters_dir.mkdir(parents=True)
        jinja_tests_dir.mkdir(parents=True)
        test_dir.mkdir(parents=True)

        # Files that should be excluded
        (filters_dir / "filter.py").write_text("""
from pyats import aetest
from nac_test import something

@aetest.test
def x(): pass
""")
        (jinja_tests_dir / "jinja_test.py").write_text("""
from pyats import aetest
from nac_test import something

@aetest.test
def x(): pass
""")

        # File that should be included
        (test_dir / "verify_test.py").write_text("""
from pyats import aetest
from nac_test.pyats_core.common.base_test import NACTestBase

class TestSomething(NACTestBase):
    @aetest.test
    def test_something(self):
        pass
""")

        discovery = TestDiscovery(
            tmp_path, exclude_paths=[filters_dir, jinja_tests_dir]
        )
        files, _ = discovery.discover_pyats_tests()

        assert len(files) == 1
        assert "verify_test.py" in str(files[0])

    def test_exclude_nested_directory(self, tmp_path: Path) -> None:
        """Test that nested directories within exclude paths are also excluded."""
        exclude_dir = tmp_path / "helpers" / "jinja"
        exclude_dir.mkdir(parents=True)

        nested_dir = exclude_dir / "nested" / "deep"
        nested_dir.mkdir(parents=True)

        (nested_dir / "helper.py").write_text("""
from pyats import aetest
from nac_test import something

@aetest.test
def x(): pass
""")

        test_dir = tmp_path / "test"
        test_dir.mkdir(parents=True)

        (test_dir / "verify_test.py").write_text("""
from pyats import aetest
from nac_test.pyats_core.common.base_test import NACTestBase

class TestSomething(NACTestBase):
    @aetest.test
    def test_something(self):
        pass
""")

        discovery = TestDiscovery(tmp_path, exclude_paths=[exclude_dir])
        files, _ = discovery.discover_pyats_tests()

        assert len(files) == 1
        assert "verify_test.py" in str(files[0])
