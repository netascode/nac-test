# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
E2E Integration Tests - Combined Reporting Failure Scenarios

Tests the complete combined reporting workflow when tests fail.
Uses class-scoped fixtures to run expensive E2E tests once per scenario
and share results across all test methods.
"""

import logging
from typing import Any

import pytest
from typer.testing import CliRunner

import nac_test.cli.main
from tests.integration.mocks.mock_server import MockAPIServer

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.integration


class TestCombinedReportingAllFail:
    """
    E2E test class for combined reporting - all tests fail scenario.

    Runs E2E test ONCE using class-scoped fixture, then executes
    focused test methods against the shared results.
    """

    @pytest.fixture(scope="class")
    def e2e_results(
        self,
        mock_api_server: MockAPIServer,
        sdwan_user_testbed: str,
        tmp_path_factory: pytest.TempPathFactory,
        class_mocker: pytest.MonkeyPatch,
    ) -> dict[str, Any]:
        """
        Class-scoped fixture: Run E2E test once (all fail), share results.

        Executes nac-test CLI with failure fixture (all tests fail):
        - Robot: 1 test fails (SHOULD_FAIL=true)
        - PyATS: 2 tests fail (non-existent command + wrong endpoint)

        Returns:
            dict: Shared E2E results containing output_dir, exit_code, stdout, etc.
        """
        output_dir = tmp_path_factory.mktemp("e2e_all_fail")

        # Setup environment using monkeypatch (auto-cleanup)
        class_mocker.setenv("SDWAN_URL", mock_api_server.url)
        class_mocker.setenv("SDWAN_USERNAME", "mock_user")
        class_mocker.setenv("SDWAN_PASSWORD", "mock_pass")
        class_mocker.setenv("IOSXE_USERNAME", "mock_user")
        class_mocker.setenv("IOSXE_PASSWORD", "mock_pass")

        data_path = "tests/integration/fixtures/e2e_failure_combined/data.yaml"
        templates_path = "tests/integration/fixtures/e2e_failure_combined/templates"

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
                "SHOULD_FAIL:true",  # Robot test fails
            ],
        )

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

    def test_cli_exits_with_failure_code(self, e2e_results: dict[str, Any]) -> None:
        """Verify CLI exits with non-zero code when tests fail."""
        assert e2e_results["exit_code"] != 0, (
            f"Expected non-zero exit code, got 0\nstdout: {e2e_results['stdout']}"
        )

    def test_cli_exit_code_is_one(self, e2e_results: dict[str, Any]) -> None:
        """Verify CLI exits with code 1 for test failures."""
        assert e2e_results["exit_code"] == 1, (
            f"Expected exit code 1, got {e2e_results['exit_code']}"
        )

    # ========================================================================
    # REPORTS STILL GENERATED (5 tests)
    # ========================================================================

    def test_robot_reports_generated_despite_failures(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify Robot reports generated even when tests fail."""
        assert (e2e_results["output_dir"] / "robot_results" / "output.xml").exists()
        assert (e2e_results["output_dir"] / "robot_results" / "log.html").exists()
        assert (e2e_results["output_dir"] / "robot_results" / "report.html").exists()

    def test_pyats_reports_generated_despite_failures(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify PyATS reports generated even when tests fail."""
        summary = (
            e2e_results["output_dir"]
            / "pyats_results"
            / "api"
            / "html_reports"
            / "summary_report.html"
        )
        assert summary.exists(), "PyATS summary not generated despite failures"

    def test_combined_dashboard_generated_despite_failures(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify combined dashboard generated even when tests fail."""
        combined = e2e_results["output_dir"] / "combined_summary.html"
        assert combined.exists(), "Combined dashboard not generated despite failures"

    def test_robot_summary_shows_failures(self, e2e_results: dict[str, Any]) -> None:
        """Verify Robot summary report shows failure information."""
        html_path = e2e_results["output_dir"] / "robot_results" / "summary_report.html"
        html_content = html_path.read_text()

        assert "fail" in html_content.lower(), "Summary doesn't show failures"
        assert "1" in html_content  # 1 failed test

    def test_pyats_summary_shows_failures(self, e2e_results: dict[str, Any]) -> None:
        """Verify PyATS summary report shows failure information."""
        summary = (
            e2e_results["output_dir"]
            / "pyats_results"
            / "api"
            / "html_reports"
            / "summary_report.html"
        )
        html_content = summary.read_text()

        assert "fail" in html_content.lower(), "PyATS summary doesn't show failures"

    # ========================================================================
    # FAILURE STATISTICS TESTS (5 tests)
    # ========================================================================

    def test_robot_statistics_show_failures(self, e2e_results: dict[str, Any]) -> None:
        """Verify Robot statistics: 0 passed, 1 failed."""
        from nac_test.robot.reporting.robot_parser import RobotResultParser

        xml_path = e2e_results["output_dir"] / "robot_results" / "output.xml"
        parser = RobotResultParser(xml_path)
        data = parser.parse()
        stats = data["aggregated_stats"]

        assert stats["passed_tests"] == 0, (
            f"Expected 0 passed, got {stats['passed_tests']}"
        )
        assert stats["failed_tests"] == 1, (
            f"Expected 1 failed, got {stats['failed_tests']}"
        )

    def test_pyats_statistics_show_failures(self, e2e_results: dict[str, Any]) -> None:
        """Verify PyATS statistics show failures (2 failed tests)."""
        summary = (
            e2e_results["output_dir"]
            / "pyats_results"
            / "api"
            / "html_reports"
            / "summary_report.html"
        )
        html_content = summary.read_text()

        # Should show 2 failed PyATS tests
        assert "2" in html_content, "Missing PyATS failure count"
        assert "fail" in html_content.lower()

    def test_combined_dashboard_shows_all_failures(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify combined dashboard shows all test failures."""
        html_path = e2e_results["output_dir"] / "combined_summary.html"
        html_content = html_path.read_text()

        # Should show failures from both Robot and PyATS
        assert "fail" in html_content.lower(), "Dashboard doesn't show failures"

    def test_combined_dashboard_overall_status_failed(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify combined dashboard shows overall FAILED status."""
        html_path = e2e_results["output_dir"] / "combined_summary.html"
        html_content = html_path.read_text()

        # Should indicate failure/error
        assert "fail" in html_content.lower() or "error" in html_content.lower(), (
            "Dashboard doesn't show failed status"
        )

    def test_exit_code_reflects_test_failures(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify exit code is non-zero when tests fail."""
        assert e2e_results["exit_code"] != 0, (
            "Exit code should be non-zero for failures"
        )

    # ========================================================================
    # DIRECTORY STRUCTURE STILL CORRECT (3 tests)
    # ========================================================================

    def test_robot_results_subdirectory_exists(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify robot_results/ subdirectory exists despite failures."""
        robot_dir = e2e_results["output_dir"] / "robot_results"
        assert robot_dir.exists(), "Missing robot_results/ despite failures"

    def test_backward_compat_symlinks_created(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify backward-compatibility symlinks created despite failures."""
        symlink = e2e_results["output_dir"] / "output.xml"
        assert symlink.is_symlink(), "Missing output.xml symlink despite failures"

    def test_all_expected_files_present(self, e2e_results: dict[str, Any]) -> None:
        """Verify all expected files generated despite failures."""
        combined = e2e_results["output_dir"] / "combined_summary.html"
        robot_summary = (
            e2e_results["output_dir"] / "robot_results" / "summary_report.html"
        )

        assert combined.exists(), "Missing combined dashboard despite failures"
        assert robot_summary.exists(), "Missing Robot summary despite failures"


class TestCombinedReportingMixedResults:
    """
    E2E test class for combined reporting - mixed pass/fail scenario.

    Runs E2E test ONCE using class-scoped fixture, then executes
    focused test methods against the shared results.
    """

    @pytest.fixture(scope="class")
    def e2e_results(
        self,
        mock_api_server: MockAPIServer,
        sdwan_user_testbed: str,
        tmp_path_factory: pytest.TempPathFactory,
        class_mocker: pytest.MonkeyPatch,
    ) -> dict[str, Any]:
        """
        Class-scoped fixture: Run E2E test once (mixed results), share results.

        Executes nac-test CLI with mixed fixture:
        - Robot: 1 pass, 1 fail (explicit test cases)
        - PyATS: 1 pass, 1 fail (mix of good/bad endpoints)

        Returns:
            dict: Shared E2E results containing output_dir, exit_code, stdout, etc.
        """
        output_dir = tmp_path_factory.mktemp("e2e_mixed")

        # Setup environment using monkeypatch (auto-cleanup)
        class_mocker.setenv("SDWAN_URL", mock_api_server.url)
        class_mocker.setenv("SDWAN_USERNAME", "mock_user")
        class_mocker.setenv("SDWAN_PASSWORD", "mock_pass")
        class_mocker.setenv("IOSXE_USERNAME", "mock_user")
        class_mocker.setenv("IOSXE_PASSWORD", "mock_pass")

        data_path = "tests/integration/fixtures/e2e_mixed_combined/data.yaml"
        templates_path = "tests/integration/fixtures/e2e_mixed_combined/templates"

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
                # No --variable needed (test file has explicit pass/fail tests)
            ],
        )

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

    def test_cli_exits_with_failure_code(self, e2e_results: dict[str, Any]) -> None:
        """Verify CLI exits with failure code when ANY test fails."""
        assert e2e_results["exit_code"] != 0, (
            "Expected non-zero exit code when tests fail, got 0"
        )

    def test_cli_exit_code_nonzero_when_any_fail(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify CLI exits with code 1 even if only some tests fail."""
        assert e2e_results["exit_code"] == 1, (
            f"Expected exit code 1, got {e2e_results['exit_code']}"
        )

    # ========================================================================
    # MIXED STATISTICS TESTS (6 tests)
    # ========================================================================

    def test_robot_statistics_show_mixed(self, e2e_results: dict[str, Any]) -> None:
        """Verify Robot statistics show mixed results: 1 pass, 1 fail."""
        from nac_test.robot.reporting.robot_parser import RobotResultParser

        xml_path = e2e_results["output_dir"] / "robot_results" / "output.xml"
        parser = RobotResultParser(xml_path)
        data = parser.parse()
        stats = data["aggregated_stats"]

        assert stats["passed_tests"] == 1, (
            f"Expected 1 passed, got {stats['passed_tests']}"
        )
        assert stats["failed_tests"] == 1, (
            f"Expected 1 failed, got {stats['failed_tests']}"
        )

    def test_pyats_statistics_show_mixed(self, e2e_results: dict[str, Any]) -> None:
        """Verify PyATS statistics show mixed results."""
        summary = (
            e2e_results["output_dir"]
            / "pyats_results"
            / "api"
            / "html_reports"
            / "summary_report.html"
        )
        html_content = summary.read_text()

        # Should show both pass and fail
        assert "pass" in html_content.lower(), "Missing pass indicators"
        assert "fail" in html_content.lower(), "Missing fail indicators"

    def test_combined_dashboard_shows_mixed_results(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify combined dashboard shows both passed and failed tests."""
        html_path = e2e_results["output_dir"] / "combined_summary.html"
        html_content = html_path.read_text()

        # Should show both pass and fail
        assert "pass" in html_content.lower(), "Dashboard missing pass indicators"
        assert "fail" in html_content.lower(), "Dashboard missing fail indicators"

    def test_combined_dashboard_overall_status_failed(
        self, e2e_results: dict[str, Any]
    ) -> None:
        """Verify combined dashboard overall status is FAILED (any failure = failed)."""
        html_path = e2e_results["output_dir"] / "combined_summary.html"
        html_content = html_path.read_text()

        # Overall should be FAILED if any test fails
        assert "fail" in html_content.lower(), (
            "Dashboard should show failed overall status"
        )

    def test_pass_count_aggregated_correctly(self, e2e_results: dict[str, Any]) -> None:
        """Verify total pass count is sum of Robot + PyATS passes."""
        html_path = e2e_results["output_dir"] / "combined_summary.html"
        html_content = html_path.read_text()

        # Total passes: 1 Robot + 1 PyATS = 2
        # Should show 2 passed tests somewhere
        assert "2" in html_content, "Missing total pass count (2)"

    def test_fail_count_aggregated_correctly(self, e2e_results: dict[str, Any]) -> None:
        """Verify total fail count is sum of Robot + PyATS failures."""
        html_path = e2e_results["output_dir"] / "combined_summary.html"
        html_content = html_path.read_text()

        # Total failures: 1 Robot + 1 PyATS = 2
        # Should show 2 failed tests somewhere
        assert "2" in html_content, "Missing total fail count (2)"

    # ========================================================================
    # REPORTS GENERATED (3 tests)
    # ========================================================================

    def test_all_reports_generated(self, e2e_results: dict[str, Any]) -> None:
        """Verify all reports generated with mixed results."""
        combined = e2e_results["output_dir"] / "combined_summary.html"
        robot_summary = (
            e2e_results["output_dir"] / "robot_results" / "summary_report.html"
        )
        pyats_summary = (
            e2e_results["output_dir"]
            / "pyats_results"
            / "api"
            / "html_reports"
            / "summary_report.html"
        )

        assert combined.exists(), "Missing combined dashboard"
        assert robot_summary.exists(), "Missing Robot summary"
        assert pyats_summary.exists(), "Missing PyATS summary"

    def test_passing_tests_shown_in_reports(self, e2e_results: dict[str, Any]) -> None:
        """Verify passing tests are shown in reports."""
        html_path = e2e_results["output_dir"] / "robot_results" / "summary_report.html"
        html_content = html_path.read_text()

        # Should list passing tests
        assert "pass" in html_content.lower(), "Passing tests not shown"

    def test_failing_tests_shown_in_reports(self, e2e_results: dict[str, Any]) -> None:
        """Verify failing tests are shown in reports."""
        html_path = e2e_results["output_dir"] / "robot_results" / "summary_report.html"
        html_content = html_path.read_text()

        # Should list failing tests
        assert "fail" in html_content.lower(), "Failing tests not shown"
