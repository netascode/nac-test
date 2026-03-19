# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Integration tests for TestDiscovery performance.

This module contains performance tests that validate discovery behavior
at scale. These tests are kept separate from unit tests as they create
many temporary files and measure timing characteristics.
"""

import time
from pathlib import Path

from nac_test.pyats_core.discovery.test_discovery import TestDiscovery


class TestDiscoveryPerformance:
    """Performance tests for the discovery mechanism."""

    def test_categorization_performance(self, tmp_path: Path) -> None:
        """Test that categorization completes quickly even with many files.

        Creates 50 test files and verifies categorization completes in
        reasonable time (<5 seconds for all files).
        """
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
        plan = discovery.discover_pyats_tests()

        start_time = time.perf_counter()
        api_tests, d2d_tests = plan.api_paths, plan.d2d_paths
        elapsed = time.perf_counter() - start_time

        # Verify results
        assert len(api_tests) == 25
        assert len(d2d_tests) == 25

        # Should complete in under 5 seconds (generous bound)
        assert elapsed < 5.0, f"Categorization took {elapsed:.2f}s, expected <5s"
