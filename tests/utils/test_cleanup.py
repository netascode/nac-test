# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for cleanup utilities."""

from pathlib import Path

import pytest

from nac_test.core.constants import PYATS_RESULTS_DIRNAME
from nac_test.pyats_core.discovery.test_type_resolver import VALID_TEST_TYPES
from nac_test.utils.cleanup import cleanup_stale_test_artifacts


class TestCleanupStaleTestArtifacts:
    """Tests for cleanup_stale_test_artifacts function."""

    def test_removes_test_type_directories(self, tmp_path: Path) -> None:
        """Test that api/, d2d/, default/ directories are removed."""
        test_type_dirs = (*VALID_TEST_TYPES, "default")
        for test_type in test_type_dirs:
            test_type_dir = tmp_path / test_type
            test_type_dir.mkdir()
            (test_type_dir / "html_report_data_temp").mkdir()
            (test_type_dir / "html_report_data_temp" / "stale.jsonl").touch()

        cleanup_stale_test_artifacts(tmp_path)

        for test_type in test_type_dirs:
            assert not (tmp_path / test_type).exists()

    @pytest.mark.parametrize(
        "preserved_path,is_file",
        [
            ("nac_test_job_api_20250224.zip", True),
            ("nac_test_job_d2d_20250224.zip", True),
            (PYATS_RESULTS_DIRNAME, False),
            ("robot_results", False),
            ("merged_data_model.yaml", True),
        ],
    )
    def test_preserves_expected_paths(
        self, tmp_path: Path, preserved_path: str, is_file: bool
    ) -> None:
        """Test that archives, pyats_results, robot_results, and other files are preserved."""
        path = tmp_path / preserved_path
        if is_file:
            path.touch()
        else:
            path.mkdir()
            (path / "content.txt").touch()

        (tmp_path / "api").mkdir()

        cleanup_stale_test_artifacts(tmp_path)

        assert path.exists()
        assert not (tmp_path / "api").exists()

    def test_handles_nonexistent_directory(self) -> None:
        """Test that nonexistent directory is handled gracefully."""
        cleanup_stale_test_artifacts(Path("/nonexistent/path"))

    def test_handles_empty_directory(self, tmp_path: Path) -> None:
        """Test that empty directory is handled gracefully."""
        cleanup_stale_test_artifacts(tmp_path)
        assert tmp_path.exists()
