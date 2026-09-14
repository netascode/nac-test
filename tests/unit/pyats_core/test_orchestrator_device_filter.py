# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Cisco Systems, Inc.

"""Unit tests for PyATSOrchestrator device filter handling and diagnostics."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nac_test.pyats_core.orchestrator import PyATSOrchestrator
from nac_test.utils.device_filter import DeviceFilterError

from ..conftest import PyATSTestDirs


class TestOrchestratorDeviceFilter:
    """Unit tests for device filter handling in PyATSOrchestrator."""

    def test_filter_zero_matches_returns_empty_results(
        self,
        aci_controller_env: None,
        pyats_test_dirs: PyATSTestDirs,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A filter matching no devices is treated like an empty inventory, not an error."""
        d2d_test_paths = [Path("/fake/tests/d2d/test_one.py")]
        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_dirs.output_dir.parent / "data"],
            test_dir=pyats_test_dirs.test_dir,
            output_dir=pyats_test_dirs.output_dir,
            device_filters=["hostname=nonexistent"],
        )

        mock_discovery_result = MagicMock()
        mock_discovery_result.total_count = 1
        mock_discovery_result.api_tests = []
        mock_discovery_result.d2d_tests = [MagicMock(path=p) for p in d2d_test_paths]
        mock_discovery_result.api_paths = []
        mock_discovery_result.d2d_paths = d2d_test_paths
        mock_discovery_result.all_tests = mock_discovery_result.d2d_tests
        mock_discovery_result.filtered_by_tags = False

        mock_inv = MagicMock()
        mock_inv.get_device_inventory.return_value = []
        mock_inv.filter_diagnostics = {
            "count_before": 2,
            "count_after": 0,
            "unknown_fields": [],
            "filters": ["hostname=nonexistent"],
        }
        mock_inv.skipped_devices = []

        with (
            patch.object(
                orchestrator.test_discovery,
                "discover_pyats_tests",
                return_value=mock_discovery_result,
            ),
            patch.object(orchestrator, "device_inventory_discovery", mock_inv),
            patch("nac_test.pyats_core.orchestrator.SubprocessRunner"),
        ):
            results = orchestrator.run_tests()

        assert results.api is None
        assert results.d2d is None
        # Warning goes to the console (same channel as the empty-inventory warning),
        # naming the filter rather than blaming the inventory.
        stdout = capsys.readouterr().out
        assert "No devices matched the device filter(s): hostname=nonexistent" in stdout
        assert "2 -> 0 devices" in stdout
        assert "No devices found in inventory" not in stdout

    def test_filter_unknown_field_raises(
        self,
        aci_controller_env: None,
        pyats_test_dirs: PyATSTestDirs,
    ) -> None:
        """An unknown filter field aborts the run with DeviceFilterError.

        API tests are included in the fixture so the abort also covers the
        ordering invariant: the filter check must run before any task coroutine
        is created, otherwise aborting strands the API coroutine un-awaited and
        silently cancels the API suite.
        """
        api_test_paths = [Path("/fake/tests/api/test_api.py")]
        d2d_test_paths = [Path("/fake/tests/d2d/test_one.py")]
        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_dirs.output_dir.parent / "data"],
            test_dir=pyats_test_dirs.test_dir,
            output_dir=pyats_test_dirs.output_dir,
            device_filters=["nonexistent_field=val"],
        )

        mock_discovery_result = MagicMock()
        mock_discovery_result.total_count = 2
        mock_discovery_result.api_tests = [MagicMock(path=p) for p in api_test_paths]
        mock_discovery_result.d2d_tests = [MagicMock(path=p) for p in d2d_test_paths]
        mock_discovery_result.api_paths = api_test_paths
        mock_discovery_result.d2d_paths = d2d_test_paths
        mock_discovery_result.all_tests = (
            mock_discovery_result.api_tests + mock_discovery_result.d2d_tests
        )
        mock_discovery_result.filtered_by_tags = False

        mock_inv = MagicMock()
        mock_inv.get_device_inventory.return_value = []
        mock_inv.filter_diagnostics = {
            "count_before": 2,
            "count_after": 0,
            "unknown_fields": ["nonexistent_field"],
            "filters": ["nonexistent_field=val"],
        }
        mock_inv.skipped_devices = []

        api_mock = AsyncMock(return_value=None)

        with (
            patch.object(
                orchestrator.test_discovery,
                "discover_pyats_tests",
                return_value=mock_discovery_result,
            ),
            patch.object(orchestrator, "device_inventory_discovery", mock_inv),
            patch("nac_test.pyats_core.orchestrator.SubprocessRunner"),
            patch.object(orchestrator, "_execute_api_tests_standard", api_mock),
            pytest.raises(DeviceFilterError) as exc_info,
        ):
            orchestrator.run_tests()

        assert (
            "Device filter field(s) not found in data model: 'nonexistent_field'"
            in str(exc_info.value)
        )
        # The API coroutine must never have been created, or it would be stranded.
        assert api_mock.call_count == 0

    def test_repeated_positive_filters_emits_warning(
        self,
        aci_controller_env: None,
        pyats_test_dirs: PyATSTestDirs,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Multiple positive filters on the same field emit a warning."""
        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_dirs.output_dir.parent / "data"],
            test_dir=pyats_test_dirs.test_dir,
            output_dir=pyats_test_dirs.output_dir,
            device_filters=["role=leaf", "role=spine"],
        )

        mock_discovery_result = MagicMock()
        mock_discovery_result.total_count = 0
        mock_discovery_result.api_tests = []
        mock_discovery_result.d2d_tests = []
        mock_discovery_result.api_paths = []
        mock_discovery_result.d2d_paths = []
        mock_discovery_result.all_tests = []
        mock_discovery_result.filtered_by_tags = False

        with (
            patch.object(
                orchestrator.test_discovery,
                "discover_pyats_tests",
                return_value=mock_discovery_result,
            ),
            caplog.at_level("WARNING"),
        ):
            orchestrator.run_tests()

        assert "Multiple positive filters for field 'role' detected" in caplog.text

    def test_device_filter_warns_when_no_d2d_tests(
        self,
        aci_controller_env: None,
        pyats_test_dirs: PyATSTestDirs,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """When --device-filter is specified but only API tests exist, warning is logged."""
        api_test_paths = [Path("/fake/tests/api/test_one.py")]
        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_dirs.output_dir.parent / "data"],
            test_dir=pyats_test_dirs.test_dir,
            output_dir=pyats_test_dirs.output_dir,
            device_filters=["role=leaf"],
            dry_run=True,
        )

        mock_discovery_result = MagicMock()
        mock_discovery_result.total_count = 1
        mock_discovery_result.api_tests = [MagicMock(path=p) for p in api_test_paths]
        mock_discovery_result.d2d_tests = []
        mock_discovery_result.api_paths = api_test_paths
        mock_discovery_result.d2d_paths = []
        mock_discovery_result.all_tests = mock_discovery_result.api_tests
        mock_discovery_result.filtered_by_tags = False

        with (
            patch.object(
                orchestrator.test_discovery,
                "discover_pyats_tests",
                return_value=mock_discovery_result,
            ),
            caplog.at_level("WARNING"),
        ):
            orchestrator.run_tests()

        assert (
            "--device-filter was specified but no D2D tests were executed"
            in caplog.text
        )
