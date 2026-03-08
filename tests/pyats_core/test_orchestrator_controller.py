# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for PyATSOrchestrator controller handling.

Tests for controller validation in PyATSOrchestrator:
1. Controller type passed from caller is used (no detection)
2. Dry-run mode accepts controller_type=None
3. Missing controller_type for execution raises ValueError
4. Missing credentials for provided controller_type returns error
5. Error results only for discovered test categories
"""

import pytest

from nac_test.core.types import ExecutionState
from nac_test.pyats_core.orchestrator import PyATSOrchestrator

from .conftest import (
    PYATS_API_TEST_FILE_CONTENT,
    PYATS_D2D_TEST_FILE_CONTENT,
    PyATSTestDirs,
)


class TestOrchestratorControllerValidation:
    """Tests for PyATSOrchestrator controller validation (detection happens in CombinedOrchestrator)."""

    @pytest.fixture(autouse=True)
    def _clean_env(self, clean_controller_env: None) -> None:
        """Ensure clean environment for all tests in this class."""

    def test_controller_type_preserved_from_init(
        self, pyats_test_dirs: PyATSTestDirs
    ) -> None:
        """Test that controller_type passed at init is preserved."""
        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_dirs.output_dir.parent / "data"],
            test_dir=pyats_test_dirs.test_dir,
            output_dir=pyats_test_dirs.output_dir,
            merged_data_filename=pyats_test_dirs.merged_file.name,
            controller_type="ACI",
        )

        assert orchestrator.controller_type == "ACI"

    def test_dry_run_accepts_none_controller_type(
        self, pyats_test_dirs: PyATSTestDirs
    ) -> None:
        """Test that dry-run mode works without controller_type."""
        (pyats_test_dirs.test_dir / "test_verify.py").write_text(
            PYATS_D2D_TEST_FILE_CONTENT
        )

        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_dirs.output_dir.parent / "data"],
            test_dir=pyats_test_dirs.test_dir,
            output_dir=pyats_test_dirs.output_dir,
            merged_data_filename=pyats_test_dirs.merged_file.name,
            controller_type=None,
            dry_run=True,
        )

        result = orchestrator.run_tests()

        assert orchestrator.controller_type is None
        assert result.d2d is not None
        assert result.d2d.state == ExecutionState.SKIPPED

    def test_missing_controller_type_for_execution_returns_error(
        self, pyats_test_dirs: PyATSTestDirs
    ) -> None:
        """Test that missing controller_type for actual execution returns error result."""
        (pyats_test_dirs.test_dir / "test_api.py").write_text(
            PYATS_API_TEST_FILE_CONTENT
        )

        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_dirs.output_dir.parent / "data"],
            test_dir=pyats_test_dirs.test_dir,
            output_dir=pyats_test_dirs.output_dir,
            merged_data_filename=pyats_test_dirs.merged_file.name,
            controller_type=None,
            dry_run=False,
        )

        result = orchestrator.run_tests()

        assert result.api is not None
        assert result.api.state == ExecutionState.ERROR
        assert "controller_type is required" in (result.api.reason or "")
        assert result.d2d is None  # only api test files were created

    def test_provided_controller_type_missing_credentials_returns_error(
        self, pyats_test_dirs: PyATSTestDirs
    ) -> None:
        """Test that provided controller_type with missing credentials returns error."""
        (pyats_test_dirs.test_dir / "test_api.py").write_text(
            PYATS_API_TEST_FILE_CONTENT
        )
        d2d_dir = pyats_test_dirs.test_dir / "d2d"
        d2d_dir.mkdir()
        (d2d_dir / "test_d2d.py").write_text(PYATS_D2D_TEST_FILE_CONTENT)

        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_dirs.output_dir.parent / "data"],
            test_dir=pyats_test_dirs.test_dir,
            output_dir=pyats_test_dirs.output_dir,
            merged_data_filename=pyats_test_dirs.merged_file.name,
            controller_type="ACI",
        )

        result = orchestrator.run_tests()

        assert result.api is not None
        assert result.api.state == ExecutionState.ERROR
        assert "credentials missing" in (result.api.reason or "").lower()
        assert result.d2d is not None
        assert result.d2d.state == ExecutionState.ERROR

    def test_error_results_only_for_discovered_categories_api_only(
        self, pyats_test_dirs: PyATSTestDirs
    ) -> None:
        """Test that error results are only returned for discovered test categories."""
        (pyats_test_dirs.test_dir / "test_api.py").write_text(
            PYATS_API_TEST_FILE_CONTENT
        )

        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_dirs.output_dir.parent / "data"],
            test_dir=pyats_test_dirs.test_dir,
            output_dir=pyats_test_dirs.output_dir,
            merged_data_filename=pyats_test_dirs.merged_file.name,
            controller_type="ACI",
        )

        result = orchestrator.run_tests()

        assert result.api is not None
        assert result.api.state == ExecutionState.ERROR
        assert result.d2d is None

    def test_error_results_only_for_discovered_categories_d2d_only(
        self, pyats_test_dirs: PyATSTestDirs
    ) -> None:
        """Test that error results are only returned for discovered test categories."""
        d2d_dir = pyats_test_dirs.test_dir / "d2d"
        d2d_dir.mkdir()
        (d2d_dir / "test_d2d.py").write_text(PYATS_D2D_TEST_FILE_CONTENT)

        orchestrator = PyATSOrchestrator(
            data_paths=[pyats_test_dirs.output_dir.parent / "data"],
            test_dir=pyats_test_dirs.test_dir,
            output_dir=pyats_test_dirs.output_dir,
            merged_data_filename=pyats_test_dirs.merged_file.name,
            controller_type="ACI",
        )

        result = orchestrator.run_tests()

        assert result.api is None
        assert result.d2d is not None
        assert result.d2d.state == ExecutionState.ERROR
