# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for cleanup utilities."""

from pathlib import Path

import pytest

from nac_test.core.constants import (
    COMBINED_SUMMARY_FILENAME,
    LOG_HTML,
    OUTPUT_XML,
    PYATS_RESULTS_DIRNAME,
    REPORT_HTML,
    ROBOT_RESULTS_DIRNAME,
    XUNIT_XML,
)
from nac_test.pyats_core.discovery.test_type_resolver import VALID_TEST_TYPES
from nac_test.utils.cleanup import cleanup_output_dir


class TestCleanupOutputDir:
    """Tests for cleanup_output_dir function."""

    def test_removes_test_type_directories(self, tmp_path: Path) -> None:
        """Test that api/, d2d/, default/ directories are removed."""
        test_type_dirs = (*VALID_TEST_TYPES, "default")
        for test_type in test_type_dirs:
            test_type_dir = tmp_path / test_type
            test_type_dir.mkdir()
            (test_type_dir / "html_report_data_temp").mkdir()
            (test_type_dir / "html_report_data_temp" / "stale.jsonl").touch()

        cleanup_output_dir(tmp_path)

        for test_type in test_type_dirs:
            assert not (tmp_path / test_type).exists()

    def test_removes_result_directories(self, tmp_path: Path) -> None:
        """Test that robot_results/ and pyats_results/ are removed."""
        for dir_name in (ROBOT_RESULTS_DIRNAME, PYATS_RESULTS_DIRNAME):
            result_dir = tmp_path / dir_name
            result_dir.mkdir()
            (result_dir / "output.xml").touch()

        cleanup_output_dir(tmp_path)

        assert not (tmp_path / ROBOT_RESULTS_DIRNAME).exists()
        assert not (tmp_path / PYATS_RESULTS_DIRNAME).exists()

    def test_removes_root_level_artifacts(self, tmp_path: Path) -> None:
        """Test that root-level combined artifacts are removed."""
        artifacts = (
            LOG_HTML,
            OUTPUT_XML,
            REPORT_HTML,
            XUNIT_XML,
            COMBINED_SUMMARY_FILENAME,
        )
        for filename in artifacts:
            (tmp_path / filename).touch()

        cleanup_output_dir(tmp_path)

        for filename in artifacts:
            assert not (tmp_path / filename).exists()

    def test_removes_broken_symlink(self, tmp_path: Path) -> None:
        """Test that broken symlinks (e.g. log.html pointing to deleted robot_results/) are removed."""
        target = tmp_path / "robot_results" / LOG_HTML
        link = tmp_path / LOG_HTML
        link.symlink_to(target)  # target does not exist — broken symlink
        assert link.is_symlink()
        assert not link.exists()

        cleanup_output_dir(tmp_path)

        assert not link.is_symlink()

    @pytest.mark.parametrize(
        "preserved_path",
        [
            "nac_test_job_api_20250224.zip",
            "nac_test_job_d2d_20250224.zip",
            "merged_data_model.yaml",
        ],
    )
    def test_preserves_archives_and_data_files(
        self, tmp_path: Path, preserved_path: str
    ) -> None:
        """Test that archives and merged data files are preserved."""
        path = tmp_path / preserved_path
        path.touch()

        cleanup_output_dir(tmp_path)

        assert path.exists()

    def test_handles_nonexistent_directory(self) -> None:
        """Test that nonexistent directory is handled gracefully."""
        cleanup_output_dir(Path("/nonexistent/path"))

    def test_handles_empty_directory(self, tmp_path: Path) -> None:
        """Test that empty directory is handled gracefully."""
        cleanup_output_dir(tmp_path)
        assert tmp_path.exists()
