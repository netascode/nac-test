# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tests for PyATSOrchestrator handling of ConfigFileCreationError."""

from pathlib import Path
from unittest.mock import patch

import pytest

from nac_test.pyats_core.orchestrator import PyATSOrchestrator

from .conftest import PyATSTestDirs


class TestOrchestratorConfigFileCreationError:
    """Tests for ConfigFileCreationError handling in PyATSOrchestrator."""

    @pytest.mark.parametrize(
        ("has_api", "has_d2d"),
        [
            (True, False),
            (False, True),
            (True, True),
        ],
    )
    def test_config_file_creation_error_returns_from_error_results(
        self,
        aci_controller_env: None,
        pyats_test_dirs: PyATSTestDirs,
        has_api: bool,
        has_d2d: bool,
    ) -> None:
        """OSError in SubprocessRunner._create_config_files returns from_error results."""
        api_tests = [Path("/fake/tests/api/test_one.py")] if has_api else []
        d2d_tests = [Path("/fake/tests/d2d/test_two.py")] if has_d2d else []

        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_dirs.output_dir.parent / "data"],
            test_dir=pyats_test_dirs.test_dir,
            output_dir=pyats_test_dirs.output_dir,
            merged_data_filename="merged.yaml",
        )

        with (
            patch.object(
                orchestrator.test_discovery, "discover_pyats_tests"
            ) as mock_discover,
            patch.object(
                orchestrator.test_discovery, "categorize_tests_by_type"
            ) as mock_categorize,
            patch.object(orchestrator, "validate_environment"),
            patch.object(Path, "write_text", side_effect=OSError("disk full")),
        ):
            mock_discover.return_value = (api_tests + d2d_tests, [])
            mock_categorize.return_value = (api_tests, d2d_tests)
            result = orchestrator.run_tests()

        if has_api:
            assert result.api is not None
            assert result.api.has_error is True
            assert result.api.reason is not None
            assert "disk full" in result.api.reason
        else:
            assert result.api is None

        if has_d2d:
            assert result.d2d is not None
            assert result.d2d.has_error is True
            assert result.d2d.reason is not None
            assert "disk full" in result.d2d.reason
        else:
            assert result.d2d is None
