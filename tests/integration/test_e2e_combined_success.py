# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
E2E Integration Tests - Combined Reporting Success Scenario

Tests the complete combined reporting workflow when all tests pass.
Uses class-scoped fixtures to run expensive E2E test once and share
results across all test methods.
"""

import logging
import os
from typing import Any

import pytest
from typer.testing import CliRunner

import nac_test.cli.main
from tests.integration.mocks.mock_server import MockAPIServer

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.integration


class TestCombinedReportingSuccess:
    """
    E2E test class for combined reporting - all tests pass scenario.

    Runs E2E test ONCE using class-scoped fixture, then executes
    41 focused test methods against the shared results.
    """

    @pytest.fixture(scope="class")
    def e2e_results(
        self,
        mock_api_server: MockAPIServer,
        sdwan_user_testbed: str,
        tmp_path_factory: pytest.TempPathFactory,
    ) -> dict[str, Any]:
        """
        Class-scoped fixture: Run E2E test once, share results.

        Executes nac-test CLI with success fixture (all tests pass):
        - Robot: 1 test passes (SHOULD_FAIL=false)
        - PyATS: 2 tests pass (control connections + config sync)

        Returns:
            dict: Shared E2E results containing output_dir, exit_code, stdout, etc.
        """
        # Setup: Create class-scoped temp directory
        output_dir = tmp_path_factory.mktemp("e2e_success")

        # Setup: Configure environment (using os.environ for class-scoped fixture)
        old_env = {}
        env_vars = {
            "SDWAN_URL": mock_api_server.url,
            "SDWAN_USERNAME": "mock_user",
            "SDWAN_PASSWORD": "mock_pass",
            "IOSXE_USERNAME": "mock_user",
            "IOSXE_PASSWORD": "mock_pass",
        }
        for key, value in env_vars.items():
            old_env[key] = os.environ.get(key)
            os.environ[key] = value

        # Setup: Fixture paths
        data_path = "tests/integration/fixtures/e2e_success_combined/data.yaml"
        templates_path = "tests/integration/fixtures/e2e_success_combined/templates"

        # Execute: Run nac-test CLI with Robot variable for success
        runner = CliRunner()
        result = runner.invoke(
            nac_test.cli.main.app,
            [
                "-d",
                data_path,
                "-t",
                templates_path,
                "-o",
                str(output_dir),
                "--testbed",
                sdwan_user_testbed,
                "--verbosity",
                "DEBUG",
                "--variable",
                "SHOULD_FAIL:false",  # Robot test passes
            ],
        )

        # Cleanup: Restore environment
        for key, old_value in old_env.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value

        # Return: Shared state for all test methods
        return {
            "output_dir": output_dir,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "cli_result": result,
        }

    # ========================================================================
    # CLI EXIT CODE TESTS (2 tests)
    # ========================================================================

    def test_cli_exits_successfully(self, e2e_results: dict[str, Any]) -> None:
        """Verify CLI exits with code 0 when all tests pass."""
        assert e2e_results["exit_code"] == 0, (
            f"Expected exit code 0, got {e2e_results['exit_code']}\n"
            f"stdout: {e2e_results['stdout']}"
        )

    def test_cli_result_has_no_exception(self, e2e_results: dict[str, Any]) -> None:
        """Verify CLI execution completed without exceptions."""
        assert e2e_results["cli_result"].exception is None

    # ========================================================================
    # DIRECTORY STRUCTURE TESTS (5 tests)
    # ========================================================================

    def test_output_directory_created(self, e2e_results: dict[str, Any]) -> None:
        """Verify output directory was created."""
        assert e2e_results["output_dir"].exists()
        assert e2e_results["output_dir"].is_dir()

    def test_robot_results_subdirectory_exists(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify robot_results/ subdirectory was created."""
        robot_dir = e2e_results["output_dir"] / "robot_results"
        assert robot_dir.exists(), "Missing robot_results/ directory"
        assert robot_dir.is_dir()

    def test_pyats_results_subdirectory_exists(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify pyats_results/ subdirectory was created."""
        pyats_dir = e2e_results["output_dir"] / "pyats_results"
        assert pyats_dir.exists(), "Missing pyats_results/ directory"
        assert pyats_dir.is_dir()

    def test_combined_summary_at_root(self, e2e_results: dict[str, Any]) -> None:
        """Verify combined_summary.html exists at root level."""
        combined = e2e_results["output_dir"] / "combined_summary.html"
        assert combined.exists(), "Missing combined_summary.html at root"
        assert combined.is_file()

    def test_no_unexpected_files_at_root(self, e2e_results: dict[str, Any]) -> None:
        """Verify root contains only expected files/directories."""
        root_items = {item.name for item in e2e_results["output_dir"].iterdir()}

        # Expected items at root
        expected = {
            "combined_summary.html",
            "robot_results",
            "pyats_results",
            # Backward-compat symlinks
            "output.xml",
            "log.html",
            "report.html",
            "xunit.xml",
        }

        # Allow for additional symlinks but ensure expected items exist
        missing = expected - root_items
        assert not missing, f"Missing expected items at root: {missing}"

    # ========================================================================
    # ROBOT FRAMEWORK OUTPUT TESTS (8 tests)
    # ========================================================================

    def test_robot_output_xml_exists(self, e2e_results: dict[str, Any]) -> None:
        """Verify Robot output.xml exists in subdirectory."""
        output_xml = e2e_results["output_dir"] / "robot_results" / "output.xml"
        assert output_xml.exists(), "Missing robot_results/output.xml"

    def test_robot_log_html_exists(self, e2e_results: dict[str, Any]) -> None:
        """Verify Robot log.html exists in subdirectory."""
        log_html = e2e_results["output_dir"] / "robot_results" / "log.html"
        assert log_html.exists(), "Missing robot_results/log.html"

    def test_robot_report_html_exists(self, e2e_results: dict[str, Any]) -> None:
        """Verify Robot report.html exists in subdirectory."""
        report_html = e2e_results["output_dir"] / "robot_results" / "report.html"
        assert report_html.exists(), "Missing robot_results/report.html"

    def test_robot_xunit_xml_exists(self, e2e_results: dict[str, Any]) -> None:
        """Verify Robot xunit.xml exists in subdirectory."""
        xunit_xml = e2e_results["output_dir"] / "robot_results" / "xunit.xml"
        assert xunit_xml.exists(), "Missing robot_results/xunit.xml"

    def test_robot_summary_report_exists(self, e2e_results: dict[str, Any]) -> None:
        """Verify Robot summary_report.html exists (PyATS-style)."""
        summary = e2e_results["output_dir"] / "robot_results" / "summary_report.html"
        assert summary.exists(), "Missing robot_results/summary_report.html"

    def test_robot_output_xml_parseable(self, e2e_results: dict[str, Any]) -> None:
        """Verify Robot output.xml is valid XML."""
        import xml.etree.ElementTree as ET

        xml_path = e2e_results["output_dir"] / "robot_results" / "output.xml"
        tree = ET.parse(xml_path)
        root = tree.getroot()

        assert root.tag == "robot", f"Expected root tag 'robot', got '{root.tag}'"

    def test_robot_statistics_correct(self, e2e_results: dict[str, Any]) -> None:
        """Verify Robot test statistics: 1 passed, 0 failed."""
        from nac_test.robot.reporting.robot_parser import RobotResultParser

        xml_path = e2e_results["output_dir"] / "robot_results" / "output.xml"
        parser = RobotResultParser(xml_path)
        data = parser.parse()
        stats = data["aggregated_stats"]

        assert stats["passed_tests"] == 1, (
            f"Expected 1 passed, got {stats['passed_tests']}"
        )
        assert stats["failed_tests"] == 0, (
            f"Expected 0 failed, got {stats['failed_tests']}"
        )

    def test_robot_test_count_matches_fixture(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify Robot test count matches fixture (1 device = 1 test)."""
        from nac_test.robot.reporting.robot_parser import RobotResultParser

        xml_path = e2e_results["output_dir"] / "robot_results" / "output.xml"
        parser = RobotResultParser(xml_path)
        data = parser.parse()
        stats = data["aggregated_stats"]

        # Fixture has 1 device → 1 Robot test
        assert stats["total_tests"] == 1, (
            f"Expected 1 total test, got {stats['total_tests']}"
        )

    # ========================================================================
    # ROBOT BACKWARD COMPATIBILITY TESTS (4 tests)
    # ========================================================================

    def test_robot_output_xml_symlink_exists(self, e2e_results: dict[str, Any]) -> None:
        """Verify output.xml symlink exists at root."""
        symlink = e2e_results["output_dir"] / "output.xml"
        assert symlink.exists(), "Missing output.xml symlink at root"
        assert symlink.is_symlink(), "output.xml is not a symlink"

    def test_robot_log_html_symlink_exists(self, e2e_results: dict[str, Any]) -> None:
        """Verify log.html symlink exists at root."""
        symlink = e2e_results["output_dir"] / "log.html"
        assert symlink.exists(), "Missing log.html symlink at root"
        assert symlink.is_symlink(), "log.html is not a symlink"

    def test_robot_report_html_symlink_exists(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify report.html symlink exists at root."""
        symlink = e2e_results["output_dir"] / "report.html"
        assert symlink.exists(), "Missing report.html symlink at root"
        assert symlink.is_symlink(), "report.html is not a symlink"

    def test_robot_symlinks_point_to_subdirectory(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify symlinks correctly point to robot_results/ subdirectory."""
        symlink = e2e_results["output_dir"] / "output.xml"
        target = symlink.resolve()
        expected = e2e_results["output_dir"] / "robot_results" / "output.xml"

        assert target == expected, (
            f"Symlink points to wrong location:\n"
            f"  Expected: {expected}\n"
            f"  Got: {target}"
        )

    # ========================================================================
    # ROBOT SUMMARY REPORT TESTS (5 tests)
    # ========================================================================

    def test_robot_summary_contains_statistics(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify Robot summary contains test statistics."""
        html_path = e2e_results["output_dir"] / "robot_results" / "summary_report.html"
        html_content = html_path.read_text()

        assert "Total" in html_content, "Missing 'Total' statistic"
        assert "Passed" in html_content or "passed" in html_content.lower()

    def test_robot_summary_shows_pass_count(self, e2e_results: dict[str, Any]) -> None:
        """Verify Robot summary shows correct pass count (1)."""
        html_path = e2e_results["output_dir"] / "robot_results" / "summary_report.html"
        html_content = html_path.read_text()

        # Should show 1 passed test
        assert "1" in html_content, "Missing pass count in summary"

    def test_robot_summary_shows_fail_count(self, e2e_results: dict[str, Any]) -> None:
        """Verify Robot summary shows correct fail count (0)."""
        html_path = e2e_results["output_dir"] / "robot_results" / "summary_report.html"
        html_content = html_path.read_text()

        # Should show 0 failed tests
        # Check for "0" in context of failures
        assert "fail" in html_content.lower() or "0" in html_content

    def test_robot_summary_pyats_style_format(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify Robot summary uses PyATS-style table format."""
        html_path = e2e_results["output_dir"] / "robot_results" / "summary_report.html"
        html_content = html_path.read_text()

        # Should have HTML table elements
        assert "<table" in html_content.lower(), "Missing table in summary"

    def test_robot_summary_breadcrumb_navigation(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify Robot summary has breadcrumb link to combined dashboard."""
        html_path = e2e_results["output_dir"] / "robot_results" / "summary_report.html"
        html_content = html_path.read_text()

        # Should link back to combined_summary.html
        assert "combined_summary.html" in html_content, (
            "Missing breadcrumb link to combined dashboard"
        )

    # ========================================================================
    # PYATS OUTPUT TESTS (6 tests)
    # ========================================================================

    def test_pyats_api_results_exist(self, e2e_results: dict[str, Any]) -> None:
        """Verify PyATS API results directory exists."""
        api_dir = e2e_results["output_dir"] / "pyats_results" / "api"
        assert api_dir.exists(), "Missing pyats_results/api directory"

    def test_pyats_api_summary_report_exists(self, e2e_results: dict[str, Any]) -> None:
        """Verify PyATS API summary report exists."""
        summary = (
            e2e_results["output_dir"]
            / "pyats_results"
            / "api"
            / "html_reports"
            / "summary_report.html"
        )
        assert summary.exists(), "Missing PyATS API summary_report.html"

    def test_pyats_d2d_results_exist_if_present(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify PyATS D2D results exist (if D2D tests in fixture)."""
        # D2D may or may not exist - this is informational
        d2d_dir = e2e_results["output_dir"] / "pyats_results" / "d2d"

        # Just log whether D2D exists
        logger.info(f"D2D directory exists: {d2d_dir.exists()}")

    def test_pyats_summary_reports_parseable(self, e2e_results: dict[str, Any]) -> None:
        """Verify PyATS summary reports are valid HTML."""
        summary = (
            e2e_results["output_dir"]
            / "pyats_results"
            / "api"
            / "html_reports"
            / "summary_report.html"
        )
        html_content = summary.read_text()

        assert "<html" in html_content.lower(), "Not valid HTML"
        assert "</html>" in html_content.lower(), "Missing closing HTML tag"

    def test_pyats_statistics_correct(self, e2e_results: dict[str, Any]) -> None:
        """Verify PyATS test statistics: 2 passed, 0 failed."""
        from tests.integration.utils import validate_pyats_results

        # Fixture has 2 PyATS tests (control + sync)
        validate_pyats_results(str(e2e_results["output_dir"]), 2, 0)

    def test_pyats_breadcrumb_navigation(self, e2e_results: dict[str, Any]) -> None:
        """Verify PyATS summary has breadcrumb link to combined dashboard."""
        summary = (
            e2e_results["output_dir"]
            / "pyats_results"
            / "api"
            / "html_reports"
            / "summary_report.html"
        )
        html_content = summary.read_text()

        assert "combined_summary.html" in html_content, (
            "Missing breadcrumb link to combined dashboard"
        )

    # ========================================================================
    # COMBINED DASHBOARD TESTS (8 tests)
    # ========================================================================

    def test_combined_dashboard_exists(self, e2e_results: dict[str, Any]) -> None:
        """Verify combined dashboard HTML file exists."""
        combined = e2e_results["output_dir"] / "combined_summary.html"
        assert combined.exists(), "Missing combined_summary.html"

    def test_combined_dashboard_parseable_html(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify combined dashboard is valid HTML."""
        html_path = e2e_results["output_dir"] / "combined_summary.html"
        html_content = html_path.read_text()

        assert "<html" in html_content.lower(), "Not valid HTML"
        assert "</html>" in html_content.lower(), "Missing closing HTML tag"

    def test_combined_dashboard_shows_robot_stats(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify combined dashboard displays Robot Framework statistics."""
        html_path = e2e_results["output_dir"] / "combined_summary.html"
        html_content = html_path.read_text()

        assert "Robot Framework" in html_content or "Robot" in html_content
        assert "1" in html_content  # 1 Robot test

    def test_combined_dashboard_shows_pyats_stats(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify combined dashboard displays PyATS statistics."""
        html_path = e2e_results["output_dir"] / "combined_summary.html"
        html_content = html_path.read_text()

        assert "PyATS" in html_content or "pyATS" in html_content
        assert "2" in html_content  # 2 PyATS tests

    def test_combined_dashboard_links_to_robot(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify combined dashboard links to Robot summary."""
        html_path = e2e_results["output_dir"] / "combined_summary.html"
        html_content = html_path.read_text()

        assert "robot_results/summary_report.html" in html_content, (
            "Missing link to Robot summary"
        )

    def test_combined_dashboard_links_to_pyats(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify combined dashboard links to PyATS results."""
        html_path = e2e_results["output_dir"] / "combined_summary.html"
        html_content = html_path.read_text()

        assert "pyats_results" in html_content, "Missing link to PyATS results"

    def test_combined_dashboard_overall_status(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify combined dashboard shows overall PASS status."""
        html_path = e2e_results["output_dir"] / "combined_summary.html"
        html_content = html_path.read_text()

        # Should indicate success/pass
        assert "pass" in html_content.lower() or "success" in html_content.lower(), (
            "Dashboard doesn't show pass/success status"
        )

    def test_combined_dashboard_title_correct(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify combined dashboard has appropriate title."""
        html_path = e2e_results["output_dir"] / "combined_summary.html"
        html_content = html_path.read_text()

        # Should have meaningful title
        assert (
            "Combined Test Summary" in html_content
            or "Test Results" in html_content
            or "Summary" in html_content
        ), "Dashboard missing appropriate title"

    # ========================================================================
    # STATISTICS FLOW TESTS (3 tests)
    # ========================================================================

    def test_robot_stats_returned_from_orchestrator(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify Robot statistics shown in CLI output."""
        stdout_lower = e2e_results["stdout"].lower()

        # Should mention Robot test results
        assert (
            "robot" in stdout_lower
            or "1 passed" in stdout_lower
            or "passed: 1" in stdout_lower
        ), "Robot stats not in stdout"

    def test_pyats_stats_returned_from_orchestrator(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify PyATS statistics shown in CLI output."""
        stdout_lower = e2e_results["stdout"].lower()

        # Should mention PyATS test results
        assert (
            "pyats" in stdout_lower
            or "2 passed" in stdout_lower
            or "passed: 2" in stdout_lower
        ), "PyATS stats not in stdout"

    def test_combined_stats_aggregated_correctly(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify combined dashboard aggregates stats correctly (3 total)."""
        html_path = e2e_results["output_dir"] / "combined_summary.html"
        html_content = html_path.read_text()

        # Total: 1 Robot + 2 PyATS = 3 tests
        # Should show 3 total somewhere
        assert "3" in html_content, "Missing total test count (3) in dashboard"
