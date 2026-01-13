
"""Integration tests for TestDiscovery with TestTypeResolver.

This module validates the integration between TestDiscovery and TestTypeResolver,
ensuring both backward compatibility with existing directory structures and
proper functionality for the new flexible organization approach.

Test Categories:
    - TestBackwardCompatibility: Tests traditional /api/ and /d2d/ structures
    - TestFlexibleStructure: Tests feature-based organization with base class detection
    - TestEdgeCases: Tests mixed scenarios and error handling
"""

from pathlib import Path

from nac_test.pyats_core.discovery.test_discovery import TestDiscovery


class TestBackwardCompatibility:
    """Ensure no breaking changes for existing project structures.

    These tests verify that projects using the traditional /api/ and /d2d/
    directory structure continue to work without any modifications.
    """

    def test_traditional_api_structure(self, tmp_path: Path) -> None:
        """Test that tests in /test/api/ are correctly categorized as API tests."""
        # Create traditional API test structure
        api_dir = tmp_path / "test" / "api" / "operational"
        api_dir.mkdir(parents=True)

        test_file = api_dir / "verify_tenant.py"
        test_file.write_text("""
from pyats import aetest

class TestTenant(aetest.Testcase):
    @aetest.test
    def test_tenant_exists(self):
        pass
""")

        # Discover and categorize
        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        # Verify API categorization
        assert len(api_tests) == 1
        assert len(d2d_tests) == 0
        assert "verify_tenant.py" in str(api_tests[0])

    def test_traditional_d2d_structure(self, tmp_path: Path) -> None:
        """Test that tests in /test/d2d/ are correctly categorized as D2D tests."""
        # Create traditional D2D test structure
        d2d_dir = tmp_path / "test" / "d2d" / "operational"
        d2d_dir.mkdir(parents=True)

        test_file = d2d_dir / "verify_routing.py"
        test_file.write_text("""
from pyats import aetest

class TestRouting(aetest.Testcase):
    @aetest.test
    def test_routing_table(self):
        pass
""")

        # Discover and categorize
        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        # Verify D2D categorization
        assert len(api_tests) == 0
        assert len(d2d_tests) == 1
        assert "verify_routing.py" in str(d2d_tests[0])

    def test_mixed_traditional_structure(self, tmp_path: Path) -> None:
        """Test traditional structure with both API and D2D tests."""
        # Create both directories
        api_dir = tmp_path / "test" / "api" / "operational"
        d2d_dir = tmp_path / "test" / "d2d" / "operational"
        api_dir.mkdir(parents=True)
        d2d_dir.mkdir(parents=True)

        # Create API test
        api_test = api_dir / "verify_api.py"
        api_test.write_text("""
from pyats import aetest

class TestAPI(aetest.Testcase):
    @aetest.test
    def test_api(self):
        pass
""")

        # Create D2D test
        d2d_test = d2d_dir / "verify_ssh.py"
        d2d_test.write_text("""
from pyats import aetest

class TestSSH(aetest.Testcase):
    @aetest.test
    def test_ssh(self):
        pass
""")

        # Discover and categorize
        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        # Verify both are categorized correctly
        assert len(api_tests) == 1
        assert len(d2d_tests) == 1
        assert "verify_api.py" in str(api_tests[0])
        assert "verify_ssh.py" in str(d2d_tests[0])


class TestFlexibleStructure:
    """Test the new flexible structure using base class detection.

    These tests verify that tests can be organized by feature/domain
    rather than being forced into /api/ or /d2d/ directories, as long
    as they inherit from recognized base classes.
    """

    def test_api_base_class_in_feature_directory(self, tmp_path: Path) -> None:
        """Test that NACTestBase inheritance is detected regardless of directory."""
        # Create feature-based structure (no /api/ or /d2d/ in path)
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

        # Discover and categorize
        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        # Should be API based on base class, not directory
        assert len(api_tests) == 1
        assert len(d2d_tests) == 0

    def test_d2d_base_class_in_feature_directory(self, tmp_path: Path) -> None:
        """Test that SSHTestBase inheritance is detected regardless of directory."""
        # Create feature-based structure (no /api/ or /d2d/ in path)
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

        # Discover and categorize
        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        # Should be D2D based on base class, not directory
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

        # Discover and categorize
        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        # Should be D2D based on base class (AST priority)
        assert len(api_tests) == 0
        assert len(d2d_tests) == 1

    def test_architecture_specific_base_classes(self, tmp_path: Path) -> None:
        """Test detection of architecture-specific base classes (APICTestBase, etc)."""
        # Create test with APICTestBase
        test_dir = tmp_path / "test" / "aci" / "operational"
        test_dir.mkdir(parents=True)

        test_file = test_dir / "verify_epg.py"
        test_file.write_text("""
from pyats import aetest

class APICTestBase:
    '''Simulated architecture base.'''
    pass

class TestEPG(APICTestBase):
    @aetest.test
    def test_epg_config(self):
        pass
""")

        # Discover and categorize
        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        # APICTestBase should be detected as API
        assert len(api_tests) == 1
        assert len(d2d_tests) == 0


class TestEdgeCases:
    """Test edge cases and error handling scenarios."""

    def test_unknown_base_class_defaults_to_api(self, tmp_path: Path) -> None:
        """Test that unknown base classes default to API with warning."""
        # Create test with unknown base class, not in /api/ or /d2d/ directory
        test_dir = tmp_path / "test" / "random" / "operational"
        test_dir.mkdir(parents=True)

        test_file = test_dir / "verify_custom.py"
        test_file.write_text("""
from pyats import aetest

class CustomTestBase:
    '''Unknown base class.'''
    pass

class TestCustom(CustomTestBase):
    @aetest.test
    def test_custom(self):
        pass
""")

        # Discover and categorize
        discovery = TestDiscovery(tmp_path)
        files, _ = discovery.discover_pyats_tests()
        api_tests, d2d_tests = discovery.categorize_tests_by_type(files)

        # Should default to API
        assert len(api_tests) == 1
        assert len(d2d_tests) == 0

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

        # Should complete in under 5 seconds (generous bound)
        assert elapsed < 5.0, f"Categorization took {elapsed:.2f}s, expected <5s"
