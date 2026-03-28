# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# mypy: disable-error-code="no-untyped-def,method-assign"

"""Unit tests for Robot Framework orchestrator."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from nac_test.core.constants import (
    EXIT_DATA_ERROR,
    LOG_HTML,
    ORDERING_FILENAME,
    OUTPUT_XML,
    REPORT_HTML,
    ROBOT_RESULTS_DIRNAME,
    SUMMARY_REPORT_FILENAME,
    XUNIT_XML,
)
from nac_test.core.types import ExecutionState, TestResults, ValidatedRobotArgs
from nac_test.robot.orchestrator import RobotOrchestrator
from nac_test.utils.logging import DEFAULT_LOGLEVEL, LogLevel
from tests.conftest import assert_is_link_to


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory for tests."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def merged_data() -> dict[str, Any]:
    """Minimal merged data dict passed to RobotOrchestrator/RobotWriter."""
    return {"test": "data"}


@pytest.fixture
def mock_templates_dir(tmp_path: Path) -> Path:
    """Create mock templates directory."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    return templates_dir


@pytest.fixture
def orchestrator(mock_templates_dir, temp_output_dir, merged_data) -> RobotOrchestrator:
    """Create a RobotOrchestrator instance for testing."""
    return RobotOrchestrator(
        templates_dir=mock_templates_dir,
        output_dir=temp_output_dir,
        merged_data=merged_data,
        loglevel=DEFAULT_LOGLEVEL,
    )


class TestRobotOrchestrator:
    """Test suite for RobotOrchestrator."""

    @staticmethod
    def _setup_run_tests_mocks(
        mock_generator: MagicMock,
        mock_pabot: MagicMock,
        orchestrator: RobotOrchestrator,
        temp_output_dir: Path,
    ) -> None:
        """Wire up the standard mocks and artifact files needed to exercise run_tests().

        Creates the robot_results/ directory with stub artifact files so that
        _create_backward_compat_links() and the report generator don't fail.
        """
        orchestrator.robot_writer.write = MagicMock()
        mock_pabot.return_value = 0

        mock_generator_instance = MagicMock()
        mock_generator_instance.generate_summary_report.return_value = (
            None,
            TestResults(),
        )
        mock_generator.return_value = mock_generator_instance

        robot_results_dir = temp_output_dir / ROBOT_RESULTS_DIRNAME
        robot_results_dir.mkdir(exist_ok=True)
        for filename in [LOG_HTML, OUTPUT_XML, REPORT_HTML, XUNIT_XML]:
            (robot_results_dir / filename).write_text(f"Mock {filename}")

    def test_initialization(
        self, orchestrator, temp_output_dir, mock_templates_dir
    ) -> None:
        """Test orchestrator initialization."""
        assert orchestrator.base_output_dir == temp_output_dir
        assert orchestrator.output_dir == temp_output_dir / ROBOT_RESULTS_DIRNAME
        assert orchestrator.ordering_file == orchestrator.output_dir / ORDERING_FILENAME
        assert orchestrator.templates_dir == mock_templates_dir
        assert orchestrator.merged_data == {"test": "data"}
        assert orchestrator.render_only is False
        assert orchestrator.dry_run is False
        assert orchestrator.loglevel == DEFAULT_LOGLEVEL

    # TODO(#699): remove this test — it only asserts that __init__ assigns attributes,
    # not any application logic. Replace with tests for actual orchestrator behaviour.
    def test_initialization_with_optional_params(
        self, mock_templates_dir, temp_output_dir
    ) -> None:
        """Test orchestrator initialization with optional parameters."""
        orchestrator = RobotOrchestrator(
            templates_dir=mock_templates_dir,
            output_dir=temp_output_dir,
            merged_data={"test": "data"},
            include_tags=["smoke", "regression"],
            exclude_tags=["wip"],
            render_only=True,
            dry_run=True,
            processes=4,
            extra_args=ValidatedRobotArgs(args=["--exitonfailure"], robot_opts={}),
            loglevel=LogLevel.DEBUG,
        )

        assert orchestrator.include_tags == ["smoke", "regression"]
        assert orchestrator.exclude_tags == ["wip"]
        assert orchestrator.render_only is True
        assert orchestrator.dry_run is True
        assert orchestrator.processes == 4
        assert orchestrator.extra_args == ValidatedRobotArgs(
            args=["--exitonfailure"], robot_opts={}
        )
        assert orchestrator.loglevel == LogLevel.DEBUG

    def test_create_backward_compat_links(self, orchestrator, temp_output_dir) -> None:
        """Test _create_backward_compat_links creates correct links (hard link or symlink)."""
        # Create robot_results directory with files
        robot_results_dir = temp_output_dir / ROBOT_RESULTS_DIRNAME
        robot_results_dir.mkdir()

        # xunit.xml is NOT linked (merged xunit is created separately)
        files_to_create = [LOG_HTML, OUTPUT_XML, REPORT_HTML]
        for filename in files_to_create:
            (robot_results_dir / filename).write_text(f"Mock {filename}")

        # Create links
        orchestrator._create_backward_compat_links()

        # Verify links were created at root (either hard link or symlink)
        for filename in files_to_create:
            link = temp_output_dir / filename
            source = robot_results_dir / filename
            assert link.exists(), f"Link not created for {filename}"
            assert_is_link_to(link, source)
            assert link.read_text() == f"Mock {filename}"

    def test_create_backward_compat_links_replaces_existing(
        self, orchestrator, temp_output_dir
    ) -> None:
        """Test _create_backward_compat_links replaces existing files."""
        # Create robot_results directory
        robot_results_dir = temp_output_dir / ROBOT_RESULTS_DIRNAME
        robot_results_dir.mkdir()
        (robot_results_dir / OUTPUT_XML).write_text("new content")

        # Create existing file at root (should be replaced)
        (temp_output_dir / OUTPUT_XML).write_text("old content")

        # Create links
        orchestrator._create_backward_compat_links()

        # Verify link was created and points to new content
        link = temp_output_dir / OUTPUT_XML
        assert link.exists()
        assert link.read_text() == "new content"

    def test_create_backward_compat_links_handles_missing_source(
        self, orchestrator, temp_output_dir, caplog
    ) -> None:
        """Test _create_backward_compat_links handles missing source files."""
        # Create robot_results directory but no files
        robot_results_dir = temp_output_dir / ROBOT_RESULTS_DIRNAME
        robot_results_dir.mkdir()

        # Should not raise an error
        orchestrator._create_backward_compat_links()

        # Verify warning was logged
        assert "Source file not found" in caplog.text

    def test_create_backward_compat_links_falls_back_to_symlink(
        self, orchestrator, temp_output_dir, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test link creation falls back to symlink when hard links fail on Unix."""
        robot_results_dir = temp_output_dir / ROBOT_RESULTS_DIRNAME
        robot_results_dir.mkdir()

        source = robot_results_dir / OUTPUT_XML
        source.write_text("<robot></robot>")

        monkeypatch.setattr("nac_test.robot.orchestrator.IS_WINDOWS", False)

        def fail_hardlink(self: Path, target: Path) -> None:
            raise OSError("hard links not supported")

        monkeypatch.setattr(Path, "hardlink_to", fail_hardlink)

        orchestrator._create_backward_compat_links()

        link = temp_output_dir / OUTPUT_XML
        assert link.is_symlink()
        assert link.resolve() == source

    @patch("nac_test.robot.orchestrator.run_pabot")
    def test_run_tests_render_only_mode(
        self, mock_pabot: MagicMock, orchestrator: RobotOrchestrator
    ) -> None:
        """Test run_tests in render-only mode."""
        orchestrator.render_only = True

        orchestrator.robot_writer.write = MagicMock()

        stats = orchestrator.run_tests()

        orchestrator.robot_writer.write.assert_called_once()
        mock_pabot.assert_not_called()

        assert stats.was_not_run is True
        assert stats.reason == "render-only mode"

    @patch("nac_test.robot.orchestrator.run_pabot")
    @patch("nac_test.robot.orchestrator.RobotReportGenerator")
    def test_run_tests_full_execution(
        self, mock_generator, mock_pabot, orchestrator, temp_output_dir
    ) -> None:
        """Test run_tests executes full test lifecycle."""
        orchestrator.robot_writer.write = MagicMock()

        mock_pabot.return_value = 0

        mock_generator_instance = MagicMock()
        mock_stats = TestResults(passed=1, failed=0, skipped=0)
        mock_generator_instance.generate_summary_report.return_value = (
            temp_output_dir / ROBOT_RESULTS_DIRNAME / SUMMARY_REPORT_FILENAME,
            mock_stats,
        )
        mock_generator.return_value = mock_generator_instance

        robot_results_dir = temp_output_dir / ROBOT_RESULTS_DIRNAME
        robot_results_dir.mkdir()
        for filename in [LOG_HTML, OUTPUT_XML, REPORT_HTML, XUNIT_XML]:
            (robot_results_dir / filename).write_text(f"Mock {filename}")

        stats = orchestrator.run_tests()

        orchestrator.robot_writer.write.assert_called_once()
        mock_pabot.assert_called_once()
        mock_generator_instance.generate_summary_report.assert_called_once()

        assert stats.total == 1
        assert stats.passed == 1
        assert stats.failed == 0
        assert stats.skipped == 0

    @patch("nac_test.robot.orchestrator.run_pabot")
    def test_run_tests_handles_pabot_exit_252_as_empty(
        self, mock_pabot: MagicMock, orchestrator: RobotOrchestrator
    ) -> None:
        """Test run_tests returns TestResults.empty() on pabot exit code 252 (no tests matched filters)."""
        orchestrator.robot_writer.write = MagicMock()

        # Mock pabot exit code EXIT_DATA_ERROR (for example no tests matched --include/--exclude filters)
        mock_pabot.return_value = EXIT_DATA_ERROR

        # Should return empty TestResults (not error) - "no tests executed" warning
        result = orchestrator.run_tests()
        assert isinstance(result, TestResults)
        assert result.is_empty
        assert result.state == ExecutionState.EMPTY
        assert not result.has_error

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

    def test_create_backward_compat_links_target_is_directory(
        self, orchestrator, temp_output_dir, caplog
    ) -> None:
        """Test link creation when target path exists as a directory."""
        robot_results_dir = temp_output_dir / ROBOT_RESULTS_DIRNAME
        robot_results_dir.mkdir()

        output_xml = robot_results_dir / OUTPUT_XML
        output_xml.write_text("<robot></robot>")

        target_dir = temp_output_dir / OUTPUT_XML
        target_dir.mkdir()

        # Should not raise, but log a warning and skip that link
        orchestrator._create_backward_compat_links()

        assert "is a directory" in caplog.text

    def test_verbose_flag_defaults_to_false(self, orchestrator) -> None:
        """Test that verbose flag defaults to False."""
        assert orchestrator.verbose is False

    @pytest.mark.parametrize(
        ("verbose", "loglevel", "expected_verbose", "expected_default_robot_loglevel"),
        [
            (True, LogLevel.WARNING, True, None),
            (True, LogLevel.DEBUG, True, "DEBUG"),
            (False, LogLevel.DEBUG, False, "DEBUG"),
            (False, LogLevel.WARNING, False, None),
        ],
        ids=[
            "verbose_true",
            "verbose_with_loglevel_debug",
            "loglevel_debug",
            "no_verbose_no_loglevel_debug",
        ],
    )
    @patch("nac_test.robot.orchestrator.run_pabot")
    @patch("nac_test.robot.orchestrator.RobotReportGenerator")
    def test_verbose_flag_passed_to_pabot(
        self,
        mock_generator,
        mock_pabot,
        mock_templates_dir,
        temp_output_dir,
        verbose,
        loglevel,
        expected_verbose,
        expected_default_robot_loglevel,
    ) -> None:
        """Test that verbose and loglevel are correctly passed to run_pabot."""
        orchestrator = RobotOrchestrator(
            templates_dir=mock_templates_dir,
            output_dir=temp_output_dir,
            merged_data={"test": "data"},
            verbose=verbose,
            loglevel=loglevel,
        )
        self._setup_run_tests_mocks(
            mock_generator, mock_pabot, orchestrator, temp_output_dir
        )

        orchestrator.run_tests()

        mock_pabot.assert_called_once()
        call_kwargs = mock_pabot.call_args[1]
        assert call_kwargs["verbose"] is expected_verbose
        assert call_kwargs["default_robot_loglevel"] == expected_default_robot_loglevel

    @pytest.mark.parametrize(
        ("include_tags", "exclude_tags"),
        [
            (["smoke"], []),
            ([], ["slow"]),
            (["smoke"], ["slow"]),
        ],
        ids=[
            "include_only",
            "exclude_only",
            "include_and_exclude",
        ],
    )
    @patch("nac_test.robot.orchestrator.run_pabot")
    @patch("nac_test.robot.orchestrator.RobotReportGenerator")
    def test_include_exclude_tags_passed_to_pabot(
        self,
        mock_generator,
        mock_pabot,
        mock_templates_dir,
        temp_output_dir,
        include_tags,
        exclude_tags,
    ) -> None:
        """Test that include/exclude tags are correctly passed through to run_pabot."""
        orchestrator = RobotOrchestrator(
            templates_dir=mock_templates_dir,
            output_dir=temp_output_dir,
            merged_data={"test": "data"},
            include_tags=include_tags,
            exclude_tags=exclude_tags,
        )
        self._setup_run_tests_mocks(
            mock_generator, mock_pabot, orchestrator, temp_output_dir
        )

        orchestrator.run_tests()

        mock_pabot.assert_called_once()
        call_kwargs = mock_pabot.call_args[1]
        assert call_kwargs["include"] == include_tags
        assert call_kwargs["exclude"] == exclude_tags
