# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# mypy: disable-error-code="no-untyped-def,method-assign"
# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for Robot Framework orchestrator."""

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nac_test.core.types import TestResults
from nac_test.robot.orchestrator import RobotOrchestrator
from nac_test.utils.logging import VerbosityLevel


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory for tests."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def mock_data_paths(tmp_path: Path) -> list[Path]:
    """Create mock data paths."""
    data_file = tmp_path / "data.yaml"
    data_file.write_text("test: data")
    return [data_file]


@pytest.fixture
def mock_templates_dir(tmp_path: Path) -> Path:
    """Create mock templates directory."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    return templates_dir


@pytest.fixture
def orchestrator(
    mock_data_paths, mock_templates_dir, temp_output_dir
) -> RobotOrchestrator:
    """Create a RobotOrchestrator instance for testing."""
    return RobotOrchestrator(
        data_paths=mock_data_paths,
        templates_dir=mock_templates_dir,
        output_dir=temp_output_dir,
        merged_data_filename="merged_data.yaml",
        verbosity=VerbosityLevel.WARNING,
    )


class TestRobotOrchestrator:
    """Test suite for RobotOrchestrator."""

    def test_initialization(
        self, orchestrator, temp_output_dir, mock_data_paths, mock_templates_dir
    ) -> None:
        """Test orchestrator initialization."""
        assert orchestrator.base_output_dir == temp_output_dir
        assert orchestrator.output_dir == temp_output_dir  # At root for backward compat
        assert orchestrator.data_paths == mock_data_paths
        assert orchestrator.templates_dir == mock_templates_dir
        assert orchestrator.merged_data_filename == "merged_data.yaml"
        assert orchestrator.render_only is False
        assert orchestrator.dry_run is False
        assert orchestrator.verbosity == VerbosityLevel.WARNING

    def test_initialization_with_optional_params(
        self, mock_data_paths, mock_templates_dir, temp_output_dir
    ) -> None:
        """Test orchestrator initialization with optional parameters."""
        orchestrator = RobotOrchestrator(
            data_paths=mock_data_paths,
            templates_dir=mock_templates_dir,
            output_dir=temp_output_dir,
            merged_data_filename="merged.yaml",
            include_tags=["smoke", "regression"],
            exclude_tags=["wip"],
            render_only=True,
            dry_run=True,
            processes=4,
            extra_args=["--exitonfailure"],
            verbosity=VerbosityLevel.DEBUG,
        )

        assert orchestrator.include_tags == ["smoke", "regression"]
        assert orchestrator.exclude_tags == ["wip"]
        assert orchestrator.render_only is True
        assert orchestrator.dry_run is True
        assert orchestrator.processes == 4
        assert orchestrator.extra_args == ["--exitonfailure"]
        assert orchestrator.verbosity == VerbosityLevel.DEBUG

    def test_get_output_summary(
        self, orchestrator, temp_output_dir, mock_templates_dir
    ) -> None:
        """Test get_output_summary returns correct information."""
        summary = orchestrator.get_output_summary()

        assert summary["type"] == "robot"
        assert summary["base_output_dir"] == str(temp_output_dir)
        assert summary["working_dir"] == str(temp_output_dir)
        assert summary["templates_dir"] == str(mock_templates_dir)
        assert summary["merged_data_file"] == str(temp_output_dir / "merged_data.yaml")
        assert summary["render_only"] is False

    def test_move_robot_results_to_subdirectory(
        self, orchestrator, temp_output_dir
    ) -> None:
        """Test _move_robot_results_to_subdirectory moves files correctly."""
        # Create mock Robot output files at root
        files_to_create = ["output.xml", "log.html", "report.html", "xunit.xml"]
        for filename in files_to_create:
            (temp_output_dir / filename).write_text(f"Mock {filename} content")

        # Move files to subdirectory
        orchestrator._move_robot_results_to_subdirectory()

        # Verify files were moved to robot_results/
        robot_results_dir = temp_output_dir / "robot_results"
        assert robot_results_dir.exists()

        for filename in files_to_create:
            target = robot_results_dir / filename
            assert target.exists()
            assert target.read_text() == f"Mock {filename} content"

            # Verify files no longer at root
            assert not (temp_output_dir / filename).exists()

    def test_move_robot_results_handles_missing_files(
        self, orchestrator, temp_output_dir
    ) -> None:
        """Test _move_robot_results_to_subdirectory handles missing files gracefully."""
        # Create only some files
        (temp_output_dir / "output.xml").write_text("output")
        (temp_output_dir / "log.html").write_text("log")
        # Don't create report.html and xunit.xml

        # Should not raise an error
        orchestrator._move_robot_results_to_subdirectory()

        # Verify existing files were moved
        robot_results_dir = temp_output_dir / "robot_results"
        assert (robot_results_dir / "output.xml").exists()
        assert (robot_results_dir / "log.html").exists()
        assert not (robot_results_dir / "report.html").exists()
        assert not (robot_results_dir / "xunit.xml").exists()

    def test_create_backward_compat_symlinks(
        self, orchestrator, temp_output_dir
    ) -> None:
        """Test _create_backward_compat_symlinks creates correct symlinks."""
        # Create robot_results directory with files
        robot_results_dir = temp_output_dir / "robot_results"
        robot_results_dir.mkdir()

        files_to_create = ["output.xml", "log.html", "report.html", "xunit.xml"]
        for filename in files_to_create:
            (robot_results_dir / filename).write_text(f"Mock {filename}")

        # Create symlinks
        orchestrator._create_backward_compat_symlinks()

        # Verify symlinks were created at root
        for filename in files_to_create:
            symlink = temp_output_dir / filename
            assert symlink.is_symlink()
            assert symlink.resolve() == robot_results_dir / filename
            assert symlink.read_text() == f"Mock {filename}"

    def test_create_backward_compat_symlinks_replaces_existing(
        self, orchestrator, temp_output_dir
    ) -> None:
        """Test _create_backward_compat_symlinks replaces existing symlinks/files."""
        # Create robot_results directory
        robot_results_dir = temp_output_dir / "robot_results"
        robot_results_dir.mkdir()
        (robot_results_dir / "output.xml").write_text("new content")

        # Create existing file at root (should be replaced)
        (temp_output_dir / "output.xml").write_text("old content")

        # Create symlinks
        orchestrator._create_backward_compat_symlinks()

        # Verify symlink was created and points to new content
        symlink = temp_output_dir / "output.xml"
        assert symlink.is_symlink()
        assert symlink.read_text() == "new content"

    def test_create_backward_compat_symlinks_handles_missing_source(
        self, orchestrator, temp_output_dir, caplog
    ) -> None:
        """Test _create_backward_compat_symlinks handles missing source files."""
        # Create robot_results directory but no files
        robot_results_dir = temp_output_dir / "robot_results"
        robot_results_dir.mkdir()

        # Should not raise an error
        orchestrator._create_backward_compat_symlinks()

        # Verify warning was logged
        assert "Source file not found for symlink" in caplog.text

    def test_get_test_statistics_success(self, orchestrator, temp_output_dir) -> None:
        """Test _get_test_statistics extracts stats from output.xml."""
        # Create robot_results directory
        robot_results_dir = temp_output_dir / "robot_results"
        robot_results_dir.mkdir()

        # Create a minimal valid Robot output.xml
        output_xml = robot_results_dir / "output.xml"
        output_xml.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2025-02-01T12:00:00.000000">
<suite id="s1" name="Test Suite">
    <test id="s1-t1" name="Test Case 1">
        <status status="PASS" start="2025-02-01T12:00:00.000000" elapsed="1.0"/>
    </test>
    <test id="s1-t2" name="Test Case 2">
        <status status="FAIL" start="2025-02-01T12:00:01.000000" elapsed="1.0">Error message</status>
    </test>
    <test id="s1-t3" name="Test Case 3">
        <status status="SKIP" start="2025-02-01T12:00:02.000000" elapsed="0.0">Skipped</status>
    </test>
    <status status="FAIL" start="2025-02-01T12:00:00.000000" elapsed="3.0"/>
</suite>
<statistics>
    <total>
        <stat pass="1" fail="1" skip="1">All Tests</stat>
    </total>
</statistics>
</robot>""")

        # Get statistics
        stats = orchestrator._get_test_statistics()

        # Verify statistics
        assert stats.total == 3
        assert stats.passed == 1
        assert stats.failed == 1
        assert stats.skipped == 1

    def test_get_test_statistics_missing_output_xml(
        self, orchestrator, temp_output_dir, caplog
    ) -> None:
        """Test _get_test_statistics handles missing output.xml."""
        # Don't create output.xml

        stats = orchestrator._get_test_statistics()

        # Should return zeros (TestResults object)
        assert stats == TestResults.empty()
        assert "Robot output.xml not found" in caplog.text

    def test_get_test_statistics_invalid_xml(
        self, orchestrator: RobotOrchestrator, temp_output_dir, caplog
    ) -> None:
        """Test _get_test_statistics handles invalid XML."""
        # Create robot_results directory
        robot_results_dir = temp_output_dir / "robot_results"
        robot_results_dir.mkdir()

        # Create invalid XML
        output_xml = robot_results_dir / "output.xml"
        output_xml.write_text("invalid xml content")

        stats = orchestrator._get_test_statistics()

        # Should return zeros and log error (TestResults object)
        assert stats == TestResults.empty()
        assert "Failed to parse Robot output.xml" in caplog.text

    @patch("nac_test.robot.orchestrator.run_pabot")
    def test_run_tests_render_only_mode(
        self, mock_pabot: MagicMock, orchestrator: RobotOrchestrator
    ) -> None:
        """Test run_tests in render-only mode."""
        orchestrator.render_only = True

        # Mock RobotWriter instance methods directly on the orchestrator's writer
        orchestrator.robot_writer.write = MagicMock()
        orchestrator.robot_writer.write_merged_data_model = MagicMock()

        stats = orchestrator.run_tests()

        # Verify template rendering was called
        orchestrator.robot_writer.write.assert_called_once()
        orchestrator.robot_writer.write_merged_data_model.assert_called_once()

        # Verify pabot was NOT called
        mock_pabot.assert_not_called()

        # Verify empty statistics returned (TestResults object)
        assert stats == TestResults.empty()

    @patch("nac_test.robot.orchestrator.run_pabot")
    @patch("nac_test.robot.orchestrator.RobotReportGenerator")
    def test_run_tests_full_execution(
        self, mock_generator, mock_pabot, orchestrator, temp_output_dir
    ) -> None:
        """Test run_tests executes full test lifecycle."""
        # Mock RobotWriter instance methods directly
        orchestrator.robot_writer.write = MagicMock()
        orchestrator.robot_writer.write_merged_data_model = MagicMock()

        # Mock pabot success
        mock_pabot.return_value = 0

        # Mock report generator
        mock_generator_instance = MagicMock()
        mock_generator_instance.generate_summary_report.return_value = (
            temp_output_dir / "robot_results" / "summary_report.html"
        )
        mock_generator.return_value = mock_generator_instance

        # Create mock Robot output files
        robot_results_dir = temp_output_dir / "robot_results"
        robot_results_dir.mkdir()
        output_xml = robot_results_dir / "output.xml"
        output_xml.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0">
<suite id="s1" name="Test">
    <test id="s1-t1" name="Test 1">
        <status status="PASS" start="2025-02-01T12:00:00.000000" elapsed="1.0"/>
    </test>
    <status status="PASS" start="2025-02-01T12:00:00.000000" elapsed="1.0"/>
</suite>
<statistics>
    <total>
        <stat pass="1" fail="0" skip="0">All Tests</stat>
    </total>
</statistics>
</robot>""")

        # Create files at root that need to be moved
        for filename in ["log.html", "report.html", "xunit.xml"]:
            (temp_output_dir / filename).write_text(f"Mock {filename}")
        # Copy output.xml to root for moving test
        shutil.copy(output_xml, temp_output_dir / "output.xml")

        stats = orchestrator.run_tests()

        # Verify all phases executed
        orchestrator.robot_writer.write.assert_called_once()
        orchestrator.robot_writer.write_merged_data_model.assert_called_once()
        mock_pabot.assert_called_once()
        mock_generator_instance.generate_summary_report.assert_called_once()

        # Verify statistics returned
        assert stats.total == 1
        assert stats.passed == 1
        assert stats.failed == 0
        assert stats.skipped == 0

    @patch("nac_test.robot.orchestrator.run_pabot")
    def test_run_tests_handles_pabot_error_252(
        self, mock_pabot: MagicMock, orchestrator: RobotOrchestrator
    ) -> None:
        """Test run_tests raises RuntimeError on pabot exit code 252 (invalid arguments)."""
        # Mock RobotWriter instance methods
        orchestrator.robot_writer.write = MagicMock()
        orchestrator.robot_writer.write_merged_data_model = MagicMock()

        # Mock pabot failure with exit code 252
        mock_pabot.return_value = 252

        # Should raise RuntimeError (handled by combined_orchestrator)
        with pytest.raises(RuntimeError, match="Invalid Robot Framework arguments"):
            orchestrator.run_tests()

    def test_run_tests_return_type(self, orchestrator: RobotOrchestrator) -> None:
        """Test run_tests returns TestResults with correct attributes."""
        orchestrator.render_only = True

        stats = orchestrator.run_tests()

        # Verify return type and attributes (TestResults, not dict)
        assert isinstance(stats, TestResults)
        assert hasattr(stats, "total")
        assert hasattr(stats, "passed")
        assert hasattr(stats, "failed")
        assert hasattr(stats, "skipped")
        # Verify values for render-only mode
        assert stats.total == 0
        assert stats.passed == 0
        assert stats.failed == 0
        assert stats.skipped == 0

    def test_run_tests_raises_on_template_rendering_error(
        self, orchestrator: RobotOrchestrator
    ) -> None:
        """Test run_tests raises exception on template rendering errors.

        Exceptions are caught at the combined_orchestrator level, not here.
        """
        # Mock RobotWriter.write to raise an exception
        orchestrator.robot_writer.write = MagicMock(
            side_effect=ValueError("Template error: invalid syntax")
        )

        # Should raise exception (handled by combined_orchestrator)
        with pytest.raises(ValueError, match="Template error"):
            orchestrator.run_tests()

    def test_create_backward_compat_symlinks_target_is_directory(
        self, orchestrator, temp_output_dir, caplog
    ) -> None:
        """Test symlink creation when target path exists as a directory."""
        robot_results_dir = temp_output_dir / "robot_results"
        robot_results_dir.mkdir()

        output_xml = robot_results_dir / "output.xml"
        output_xml.write_text("<robot></robot>")

        target_dir = temp_output_dir / "output.xml"
        target_dir.mkdir()

        # Should not raise, but log a warning and skip that symlink
        orchestrator._create_backward_compat_symlinks()

        assert "is a directory" in caplog.text

    def test_get_test_statistics_partially_corrupted_xml(
        self, orchestrator, temp_output_dir, caplog
    ) -> None:
        """Test statistics parsing with valid XML but missing statistics element."""
        robot_results_dir = temp_output_dir / "robot_results"
        robot_results_dir.mkdir()

        output_xml = robot_results_dir / "output.xml"
        output_xml.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<invalid_root>
    <suite name="Test">
        <test name="Example">
            <status status="PASS"></status>
        </test>
    </suite>
</invalid_root>"""
        )

        with caplog.at_level("ERROR"):
            result = orchestrator._get_test_statistics()

        assert result == TestResults.empty()
        assert "Failed to parse Robot output.xml" in caplog.text
