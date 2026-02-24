# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for cleanup utilities."""

from pathlib import Path

from nac_test.core.constants import PYATS_RESULTS_DIRNAME
from nac_test.pyats_core.discovery.test_type_resolver import VALID_TEST_TYPES
from nac_test.utils.cleanup import cleanup_pyats_output_dir


class TestCleanupPyatsOutputDir:
    """Tests for cleanup_pyats_output_dir function."""

    def test_removes_archive_files(self, tmp_path: Path) -> None:
        """Test that archive files are removed."""
        # Create test archive files
        archive1 = tmp_path / "nac_test_job_api_20250224.zip"
        archive2 = tmp_path / "nac_test_job_d2d_20250224.zip"
        archive1.touch()
        archive2.touch()

        # Also create a non-archive file that should be preserved
        other_file = tmp_path / "merged_data_model.yaml"
        other_file.touch()

        cleanup_pyats_output_dir(tmp_path)

        # Archives should be removed
        assert not archive1.exists()
        assert not archive2.exists()

        # Other files should remain
        assert other_file.exists()

    def test_removes_pyats_results_directory(self, tmp_path: Path) -> None:
        """Test that pyats_results directory is removed."""
        # Create pyats_results directory with content
        pyats_results = tmp_path / PYATS_RESULTS_DIRNAME
        pyats_results.mkdir()
        (pyats_results / "api").mkdir()
        (pyats_results / "api" / "html_reports").mkdir()
        (pyats_results / "api" / "html_reports" / "summary_report.html").touch()

        cleanup_pyats_output_dir(tmp_path)

        # pyats_results directory should be removed
        assert not pyats_results.exists()

    def test_handles_nonexistent_directory(self) -> None:
        """Test that nonexistent directory is handled gracefully."""
        nonexistent = Path("/nonexistent/path/that/does/not/exist")
        # Should not raise any exception
        cleanup_pyats_output_dir(nonexistent)

    def test_handles_empty_directory(self, tmp_path: Path) -> None:
        """Test that empty directory is handled gracefully."""
        cleanup_pyats_output_dir(tmp_path)
        # Directory should still exist
        assert tmp_path.exists()

    def test_removes_nested_archives(self, tmp_path: Path) -> None:
        """Test that archives in nested directories are NOT removed.

        The cleanup only targets archives in the root output directory,
        not nested ones (this matches the glob pattern used).
        """
        # Create a nested directory with an archive
        nested = tmp_path / "some_dir"
        nested.mkdir()
        nested_archive = nested / "nac_test_job_api_20250224.zip"
        nested_archive.touch()

        # Create a root-level archive
        root_archive = tmp_path / "nac_test_job_d2d_20250224.zip"
        root_archive.touch()

        cleanup_pyats_output_dir(tmp_path)

        # Root archive should be removed
        assert not root_archive.exists()

        # Nested archive should remain (only root-level cleanup)
        assert nested_archive.exists()

    def test_preserves_robot_results(self, tmp_path: Path) -> None:
        """Test that robot_results directory is preserved."""
        # Create robot_results directory
        robot_results = tmp_path / "robot_results"
        robot_results.mkdir()
        (robot_results / "output.xml").touch()

        # Create pyats_results directory
        pyats_results = tmp_path / PYATS_RESULTS_DIRNAME
        pyats_results.mkdir()

        cleanup_pyats_output_dir(tmp_path)

        # robot_results should remain
        assert robot_results.exists()
        assert (robot_results / "output.xml").exists()

        # pyats_results should be removed
        assert not pyats_results.exists()

    def test_combined_cleanup_scenario(self, tmp_path: Path) -> None:
        """Test cleanup with both archives and results directory (issue #526 scenario)."""
        # Simulate interrupted run state - archives and partial results
        archive = tmp_path / "nac_test_job_api_20250223.zip"
        archive.touch()

        pyats_results = tmp_path / PYATS_RESULTS_DIRNAME
        pyats_results.mkdir()
        api_reports = pyats_results / "api" / "html_reports"
        api_reports.mkdir(parents=True)
        (api_reports / "summary_report.html").touch()

        # Other files that should survive
        merged_data = tmp_path / "merged_data_model_test_variables.yaml"
        merged_data.touch()

        cleanup_pyats_output_dir(tmp_path)

        # Stale artifacts removed
        assert not archive.exists()
        assert not pyats_results.exists()

        # Other files preserved
        assert merged_data.exists()

    def test_removes_test_type_directories(self, tmp_path: Path) -> None:
        """Test that api/, d2d/, default/ directories are removed."""
        test_type_dirs = (*VALID_TEST_TYPES, "default")
        for test_type in test_type_dirs:
            test_type_dir = tmp_path / test_type
            test_type_dir.mkdir()
            temp_data_dir = test_type_dir / "html_report_data_temp"
            temp_data_dir.mkdir()
            (temp_data_dir / "test_123.jsonl").touch()
            (temp_data_dir / "test_456.jsonl").touch()

        other_dir = tmp_path / "robot_results"
        other_dir.mkdir()
        (other_dir / "output.xml").touch()

        cleanup_pyats_output_dir(tmp_path)

        for test_type in test_type_dirs:
            assert not (tmp_path / test_type).exists()

        assert other_dir.exists()
        assert (other_dir / "output.xml").exists()
