# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""E2E Integration Tests - Combined Reporting.

This module contains end-to-end tests for the combined reporting workflow.
Tests are organized using a base class pattern:

- E2ECombinedTestBase: Contains all common tests that apply to every scenario
- TestE2ESuccess, TestE2EAllFail, TestE2EMixed: Inherit from base, provide
  scenario-specific fixture and any scenario-specific tests

This approach:
- Eliminates code duplication across scenarios
- Preserves class-scoped fixture caching (each scenario runs once)
- Makes it easy to add new scenarios (just create a new subclass)
- Allows scenario-specific tests where needed
"""

import logging
import xml.etree.ElementTree as ET

import pytest

from nac_test.robot.reporting.robot_output_parser import RobotResultParser
from tests.e2e.conftest import E2EResults
from tests.e2e.html_helpers import (
    assert_combined_stats,
    assert_report_stats,
    extract_summary_stats_from_combined,
    load_html_file,
    verify_breadcrumb_link,
    verify_html_structure,
    verify_table_structure,
    verify_view_details_links_resolve,
)

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.e2e


# =============================================================================
# BASE TEST CLASS - Common tests for all scenarios
# =============================================================================


class E2ECombinedTestBase:
    """Base class containing common E2E tests that apply to all scenarios.

    Subclasses must provide a `results` fixture that returns E2EResults
    for their specific scenario.

    Test categories:
    - CLI behavior (exit code matches expectation)
    - Directory structure (output dirs created)
    - Robot Framework outputs (files exist, parseable, stats correct)
    - PyATS API outputs (files exist, stats correct)
    - PyATS D2D outputs (files exist, stats correct)
    - Combined dashboard (files exist, stats correct, links work)
    """

    @pytest.fixture
    def results(self) -> E2EResults:
        """Override in subclass to provide scenario-specific results."""
        raise NotImplementedError("Subclass must provide results fixture")

    # -------------------------------------------------------------------------
    # CLI Behavior Tests
    # -------------------------------------------------------------------------

    def test_cli_exit_code_matches_expectation(self, results: E2EResults) -> None:
        """Verify CLI exit code matches scenario expectation."""
        expected = results.scenario.expected_exit_code
        assert results.exit_code == expected, (
            f"Expected exit code {expected}, got {results.exit_code}\n"
            f"stdout: {results.stdout}"
        )

    def test_cli_has_no_exception(self, results: E2EResults) -> None:
        """Verify CLI execution completed without unexpected exceptions.

        Note: SystemExit is expected when tests fail (non-zero exit code).
        Typer's CliRunner captures this as an exception, but it's not an error.
        """
        exception = results.cli_result.exception
        if exception is not None:
            # SystemExit is expected for non-zero exit codes (test failures)
            assert isinstance(exception, SystemExit), (
                f"CLI raised unexpected exception: {type(exception).__name__}: {exception}"
            )
            # Verify the exit code matches what we expect
            assert exception.code == results.scenario.expected_exit_code, (
                f"SystemExit code {exception.code} doesn't match expected "
                f"{results.scenario.expected_exit_code}"
            )

    # -------------------------------------------------------------------------
    # Directory Structure Tests
    # -------------------------------------------------------------------------

    def test_output_directory_created(self, results: E2EResults) -> None:
        """Verify output directory was created."""
        assert results.output_dir.exists()
        assert results.output_dir.is_dir()

    def test_combined_summary_at_root(self, results: E2EResults) -> None:
        """Verify combined_summary.html exists at root level."""
        combined = results.output_dir / "combined_summary.html"
        assert combined.exists(), "Missing combined_summary.html at root"
        assert combined.is_file()

    # -------------------------------------------------------------------------
    # Robot Framework Output Tests
    # -------------------------------------------------------------------------

    def test_robot_results_directory_exists(self, results: E2EResults) -> None:
        """Verify robot_results/ subdirectory was created."""
        if not results.scenario.has_robot_tests:
            pytest.skip("No Robot tests in this scenario")
        robot_dir = results.output_dir / "robot_results"
        assert robot_dir.exists(), "Missing robot_results/ directory"
        assert robot_dir.is_dir()

    def test_robot_output_xml_exists(self, results: E2EResults) -> None:
        """Verify Robot output.xml exists."""
        if not results.scenario.has_robot_tests:
            pytest.skip("No Robot tests in this scenario")
        output_xml = results.output_dir / "robot_results" / "output.xml"
        assert output_xml.exists(), "Missing robot_results/output.xml"

    def test_robot_log_html_exists(self, results: E2EResults) -> None:
        """Verify Robot log.html exists."""
        if not results.scenario.has_robot_tests:
            pytest.skip("No Robot tests in this scenario")
        log_html = results.output_dir / "robot_results" / "log.html"
        assert log_html.exists(), "Missing robot_results/log.html"

    def test_robot_report_html_exists(self, results: E2EResults) -> None:
        """Verify Robot report.html exists."""
        if not results.scenario.has_robot_tests:
            pytest.skip("No Robot tests in this scenario")
        report_html = results.output_dir / "robot_results" / "report.html"
        assert report_html.exists(), "Missing robot_results/report.html"

    def test_robot_summary_report_exists(self, results: E2EResults) -> None:
        """Verify Robot summary_report.html exists."""
        if not results.scenario.has_robot_tests:
            pytest.skip("No Robot tests in this scenario")
        summary = results.output_dir / "robot_results" / "summary_report.html"
        assert summary.exists(), "Missing robot_results/summary_report.html"

    def test_robot_output_xml_parseable(self, results: E2EResults) -> None:
        """Verify Robot output.xml is valid XML."""
        if not results.scenario.has_robot_tests:
            pytest.skip("No Robot tests in this scenario")
        xml_path = results.output_dir / "robot_results" / "output.xml"
        tree = ET.parse(xml_path)
        root = tree.getroot()
        assert root.tag == "robot", f"Expected root tag 'robot', got '{root.tag}'"

    def test_robot_statistics_correct(self, results: E2EResults) -> None:
        """Verify Robot test statistics match scenario expectations."""
        if not results.scenario.has_robot_tests:
            pytest.skip("No Robot tests in this scenario")
        xml_path = results.output_dir / "robot_results" / "output.xml"
        parser = RobotResultParser(xml_path)
        data = parser.parse()
        stats = data["aggregated_stats"]
        scenario = results.scenario

        assert stats.passed == scenario.expected_robot_passed, (
            f"Robot passed: expected {scenario.expected_robot_passed}, "
            f"got {stats.passed}"
        )
        assert stats.failed == scenario.expected_robot_failed, (
            f"Robot failed: expected {scenario.expected_robot_failed}, "
            f"got {stats.failed}"
        )

    # -------------------------------------------------------------------------
    # Robot Backward Compatibility Tests (symlinks)
    # -------------------------------------------------------------------------

    def test_robot_output_xml_symlink_exists(self, results: E2EResults) -> None:
        """Verify output.xml symlink exists at root."""
        if not results.scenario.has_robot_tests:
            pytest.skip("No Robot tests in this scenario")
        symlink = results.output_dir / "output.xml"
        assert symlink.exists(), "Missing output.xml symlink at root"
        assert symlink.is_symlink(), "output.xml is not a symlink"

    def test_robot_symlinks_point_correctly(self, results: E2EResults) -> None:
        """Verify symlinks correctly point to robot_results/ subdirectory."""
        if not results.scenario.has_robot_tests:
            pytest.skip("No Robot tests in this scenario")
        symlink = results.output_dir / "output.xml"
        target = symlink.resolve()
        expected = results.output_dir / "robot_results" / "output.xml"
        assert target == expected, (
            f"Symlink points to wrong location:\n"
            f"  Expected: {expected}\n"
            f"  Got: {target}"
        )

    # -------------------------------------------------------------------------
    # Robot Summary Report Tests
    # -------------------------------------------------------------------------

    def test_robot_summary_has_valid_html(self, results: E2EResults) -> None:
        """Verify Robot summary report is valid HTML."""
        if not results.scenario.has_robot_tests:
            pytest.skip("No Robot tests in this scenario")
        html_path = results.output_dir / "robot_results" / "summary_report.html"
        html_content = load_html_file(html_path)
        verify_html_structure(html_content)

    def test_robot_summary_has_table(self, results: E2EResults) -> None:
        """Verify Robot summary has results table."""
        if not results.scenario.has_robot_tests:
            pytest.skip("No Robot tests in this scenario")
        html_path = results.output_dir / "robot_results" / "summary_report.html"
        html_content = load_html_file(html_path)
        verify_table_structure(html_content)

    def test_robot_summary_has_breadcrumb(self, results: E2EResults) -> None:
        """Verify Robot summary has breadcrumb to combined dashboard."""
        if not results.scenario.has_robot_tests:
            pytest.skip("No Robot tests in this scenario")
        html_path = results.output_dir / "robot_results" / "summary_report.html"
        html_content = load_html_file(html_path)
        verify_breadcrumb_link(html_content, "combined_summary.html")

    def test_robot_summary_stats_correct(self, results: E2EResults) -> None:
        """Verify Robot summary statistics are correct."""
        if not results.scenario.has_robot_tests:
            pytest.skip("No Robot tests in this scenario")
        html_path = results.output_dir / "robot_results" / "summary_report.html"
        scenario = results.scenario
        assert_report_stats(
            html_path,
            expected_total=scenario.expected_robot_total,
            expected_passed=scenario.expected_robot_passed,
            expected_failed=scenario.expected_robot_failed,
            expected_skipped=scenario.expected_robot_skipped,
        )

    def test_robot_summary_view_details_links_resolve(
        self, results: E2EResults
    ) -> None:
        """Verify Robot summary View Details links point to existing files."""
        if not results.scenario.has_robot_tests:
            pytest.skip("No Robot tests in this scenario")
        html_path = results.output_dir / "robot_results" / "summary_report.html"
        verified_links = verify_view_details_links_resolve(html_path)
        assert len(verified_links) > 0, "No View Details links found in Robot summary"

    # -------------------------------------------------------------------------
    # PyATS Results Directory Tests
    # -------------------------------------------------------------------------

    def test_pyats_results_directory_exists(self, results: E2EResults) -> None:
        """Verify pyats_results/ subdirectory was created."""
        if not results.scenario.has_pyats_tests:
            pytest.skip("No PyATS tests in this scenario")
        pyats_dir = results.output_dir / "pyats_results"
        assert pyats_dir.exists(), "Missing pyats_results/ directory"
        assert pyats_dir.is_dir()

    # -------------------------------------------------------------------------
    # PyATS API Output Tests
    # -------------------------------------------------------------------------

    def test_pyats_api_results_exist(self, results: E2EResults) -> None:
        """Verify PyATS API results directory exists."""
        if not results.scenario.has_pyats_api_tests:
            pytest.skip("No PyATS API tests in this scenario")
        api_dir = results.output_dir / "pyats_results" / "api"
        assert api_dir.exists(), "Missing pyats_results/api directory"

    def test_pyats_api_summary_report_exists(self, results: E2EResults) -> None:
        """Verify PyATS API summary report exists."""
        if not results.scenario.has_pyats_api_tests:
            pytest.skip("No PyATS API tests in this scenario")
        summary = (
            results.output_dir
            / "pyats_results"
            / "api"
            / "html_reports"
            / "summary_report.html"
        )
        assert summary.exists(), "Missing PyATS API summary_report.html"

    def test_pyats_api_summary_has_valid_html(self, results: E2EResults) -> None:
        """Verify PyATS API summary is valid HTML."""
        if not results.scenario.has_pyats_api_tests:
            pytest.skip("No PyATS API tests in this scenario")
        summary = (
            results.output_dir
            / "pyats_results"
            / "api"
            / "html_reports"
            / "summary_report.html"
        )
        html_content = load_html_file(summary)
        verify_html_structure(html_content)

    def test_pyats_api_summary_has_breadcrumb(self, results: E2EResults) -> None:
        """Verify PyATS API summary has breadcrumb to combined dashboard."""
        if not results.scenario.has_pyats_api_tests:
            pytest.skip("No PyATS API tests in this scenario")
        summary = (
            results.output_dir
            / "pyats_results"
            / "api"
            / "html_reports"
            / "summary_report.html"
        )
        html_content = load_html_file(summary)
        verify_breadcrumb_link(html_content, "combined_summary.html")

    def test_pyats_api_summary_stats_correct(self, results: E2EResults) -> None:
        """Verify PyATS API summary statistics are correct."""
        if not results.scenario.has_pyats_api_tests:
            pytest.skip("No PyATS API tests in this scenario")
        summary = (
            results.output_dir
            / "pyats_results"
            / "api"
            / "html_reports"
            / "summary_report.html"
        )
        scenario = results.scenario
        assert_report_stats(
            summary,
            expected_total=scenario.expected_pyats_api_total,
            expected_passed=scenario.expected_pyats_api_passed,
            expected_failed=scenario.expected_pyats_api_failed,
            expected_skipped=scenario.expected_pyats_api_skipped,
        )

    def test_pyats_api_summary_view_details_links_resolve(
        self, results: E2EResults
    ) -> None:
        """Verify PyATS API summary View Details links point to existing files."""
        if not results.scenario.has_pyats_api_tests:
            pytest.skip("No PyATS API tests in this scenario")
        summary = (
            results.output_dir
            / "pyats_results"
            / "api"
            / "html_reports"
            / "summary_report.html"
        )
        verified_links = verify_view_details_links_resolve(summary)
        assert len(verified_links) > 0, (
            "No View Details links found in PyATS API summary"
        )

    # -------------------------------------------------------------------------
    # PyATS D2D Output Tests
    # -------------------------------------------------------------------------

    def test_pyats_d2d_results_exist(self, results: E2EResults) -> None:
        """Verify PyATS D2D results directory exists."""
        if not results.scenario.has_pyats_d2d_tests:
            pytest.skip("No PyATS D2D tests in this scenario")
        d2d_dir = results.output_dir / "pyats_results" / "d2d"
        assert d2d_dir.exists(), "Missing pyats_results/d2d directory"

    def test_pyats_d2d_summary_report_exists(self, results: E2EResults) -> None:
        """Verify PyATS D2D summary report exists."""
        if not results.scenario.has_pyats_d2d_tests:
            pytest.skip("No PyATS D2D tests in this scenario")
        summary = (
            results.output_dir
            / "pyats_results"
            / "d2d"
            / "html_reports"
            / "summary_report.html"
        )
        assert summary.exists(), "Missing PyATS D2D summary_report.html"

    def test_pyats_d2d_summary_has_valid_html(self, results: E2EResults) -> None:
        """Verify PyATS D2D summary is valid HTML."""
        if not results.scenario.has_pyats_d2d_tests:
            pytest.skip("No PyATS D2D tests in this scenario")
        summary = (
            results.output_dir
            / "pyats_results"
            / "d2d"
            / "html_reports"
            / "summary_report.html"
        )
        html_content = load_html_file(summary)
        verify_html_structure(html_content)

    def test_pyats_d2d_summary_has_breadcrumb(self, results: E2EResults) -> None:
        """Verify PyATS D2D summary has breadcrumb to combined dashboard."""
        if not results.scenario.has_pyats_d2d_tests:
            pytest.skip("No PyATS D2D tests in this scenario")
        summary = (
            results.output_dir
            / "pyats_results"
            / "d2d"
            / "html_reports"
            / "summary_report.html"
        )
        html_content = load_html_file(summary)
        verify_breadcrumb_link(html_content, "combined_summary.html")

    def test_pyats_d2d_summary_stats_correct(self, results: E2EResults) -> None:
        """Verify PyATS D2D summary statistics are correct."""
        if not results.scenario.has_pyats_d2d_tests:
            pytest.skip("No PyATS D2D tests in this scenario")
        summary = (
            results.output_dir
            / "pyats_results"
            / "d2d"
            / "html_reports"
            / "summary_report.html"
        )
        scenario = results.scenario
        assert_report_stats(
            summary,
            expected_total=scenario.expected_pyats_d2d_total,
            expected_passed=scenario.expected_pyats_d2d_passed,
            expected_failed=scenario.expected_pyats_d2d_failed,
            expected_skipped=scenario.expected_pyats_d2d_skipped,
        )

    def test_pyats_d2d_summary_view_details_links_resolve(
        self, results: E2EResults
    ) -> None:
        """Verify PyATS D2D summary View Details links point to existing files."""
        if not results.scenario.has_pyats_d2d_tests:
            pytest.skip("No PyATS D2D tests in this scenario")
        summary = (
            results.output_dir
            / "pyats_results"
            / "d2d"
            / "html_reports"
            / "summary_report.html"
        )
        verified_links = verify_view_details_links_resolve(summary)
        assert len(verified_links) > 0, (
            "No View Details links found in PyATS D2D summary"
        )

    # -------------------------------------------------------------------------
    # Combined Dashboard Tests
    # -------------------------------------------------------------------------

    def test_combined_dashboard_has_valid_html(self, results: E2EResults) -> None:
        """Verify combined dashboard is valid HTML."""
        html_path = results.output_dir / "combined_summary.html"
        html_content = load_html_file(html_path)
        verify_html_structure(html_content)

    def test_combined_dashboard_links_to_robot(self, results: E2EResults) -> None:
        """Verify combined dashboard links to Robot summary."""
        if not results.scenario.has_robot_tests:
            pytest.skip("No Robot tests in this scenario")
        html_path = results.output_dir / "combined_summary.html"
        html_content = load_html_file(html_path)
        assert "robot_results/summary_report.html" in html_content, (
            "Missing link to Robot summary"
        )

    def test_combined_dashboard_links_to_pyats(self, results: E2EResults) -> None:
        """Verify combined dashboard links to PyATS results."""
        if not results.scenario.has_pyats_tests:
            pytest.skip("No PyATS tests in this scenario")
        html_path = results.output_dir / "combined_summary.html"
        html_content = load_html_file(html_path)
        assert "pyats_results" in html_content, "Missing link to PyATS results"

    def test_combined_stats_correct(self, results: E2EResults) -> None:
        """Verify combined dashboard statistics are correct."""
        html_path = results.output_dir / "combined_summary.html"
        scenario = results.scenario
        assert_combined_stats(
            html_path,
            expected_total=scenario.expected_total_tests,
            expected_passed=scenario.expected_total_passed,
            expected_failed=scenario.expected_total_failed,
            expected_skipped=scenario.expected_total_skipped,
        )

    def test_combined_stats_internal_consistency(self, results: E2EResults) -> None:
        """Verify combined stats are internally consistent."""
        html_path = results.output_dir / "combined_summary.html"
        html_content = load_html_file(html_path)
        stats = extract_summary_stats_from_combined(html_content)

        # Total should equal passed + failed + skipped
        computed_total = stats.passed + stats.failed + stats.skipped
        assert stats.total == computed_total, (
            f"Stats inconsistency: passed({stats.passed}) + failed({stats.failed}) + "
            f"skipped({stats.skipped}) = {computed_total}, but total = {stats.total}"
        )

    def test_combined_success_rate_matches_expectation(
        self, results: E2EResults
    ) -> None:
        """Verify combined dashboard success rate matches expected value."""
        html_path = results.output_dir / "combined_summary.html"
        html_content = load_html_file(html_path)
        stats = extract_summary_stats_from_combined(html_content)
        scenario = results.scenario

        # Calculate expected rate
        if scenario.expected_total_tests > 0:
            expected_rate = (
                scenario.expected_total_passed / scenario.expected_total_tests
            ) * 100
        else:
            expected_rate = 0.0

        assert abs(stats.success_rate - expected_rate) < 0.1, (
            f"Expected {expected_rate:.1f}% success rate, got {stats.success_rate}%"
        )


# =============================================================================
# SUCCESS SCENARIO TESTS
# =============================================================================


class TestE2ESuccess(E2ECombinedTestBase):
    """E2E tests for the success scenario (all tests pass).

    Scenario: Robot (1 pass) + PyATS API (1 pass) + PyATS D2D (1 pass)
    Expected: CLI exits with code 0, 100% success rate
    """

    @pytest.fixture
    def results(self, e2e_success_results: E2EResults) -> E2EResults:
        """Provide success scenario results."""
        return e2e_success_results

    # -------------------------------------------------------------------------
    # Success-specific tests
    # -------------------------------------------------------------------------

    def test_expected_files_at_root(self, results: E2EResults) -> None:
        """Verify root contains expected files/directories including symlinks."""
        root_items = {item.name for item in results.output_dir.iterdir()}
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
        missing = expected - root_items
        assert not missing, f"Missing expected items at root: {missing}"


# =============================================================================
# ALL FAIL SCENARIO TESTS
# =============================================================================


class TestE2EAllFail(E2ECombinedTestBase):
    """E2E tests for the all-fail scenario.

    Scenario: Robot (1 fail) + PyATS API (1 fail) + PyATS D2D (1 fail)
    Expected: CLI exits with code 1, 0% success rate
    """

    @pytest.fixture
    def results(self, e2e_failure_results: E2EResults) -> E2EResults:
        """Provide failure scenario results."""
        return e2e_failure_results


# =============================================================================
# MIXED SCENARIO TESTS
# =============================================================================


class TestE2EMixed(E2ECombinedTestBase):
    """E2E tests for the mixed pass/fail scenario.

    Scenario: Robot (1 pass, 1 fail) + PyATS API (0 pass, 1 fail) + PyATS D2D (1 pass)
    Expected: CLI exits with code 1 (any failure = non-zero)
    """

    @pytest.fixture
    def results(self, e2e_mixed_results: E2EResults) -> E2EResults:
        """Provide mixed scenario results."""
        return e2e_mixed_results

    # -------------------------------------------------------------------------
    # Mixed-specific tests
    # -------------------------------------------------------------------------

    def test_robot_summary_shows_both_pass_and_fail(self, results: E2EResults) -> None:
        """Verify Robot summary shows both passing and failing tests."""
        html_path = results.output_dir / "robot_results" / "summary_report.html"
        html_content = load_html_file(html_path)

        assert "pass" in html_content.lower(), "Passing tests not shown"
        assert "fail" in html_content.lower(), "Failing tests not shown"

    def test_combined_dashboard_shows_both_pass_and_fail(
        self, results: E2EResults
    ) -> None:
        """Verify combined dashboard shows both passed and failed tests."""
        html_path = results.output_dir / "combined_summary.html"
        html_content = load_html_file(html_path)

        assert "pass" in html_content.lower(), "Dashboard missing pass indicators"
        assert "fail" in html_content.lower(), "Dashboard missing fail indicators"


# =============================================================================
# ROBOT-ONLY SCENARIO TESTS
# =============================================================================


class TestE2ERobotOnly(E2ECombinedTestBase):
    """E2E tests for the robot-only scenario.

    Scenario: Robot (1 pass), no PyATS tests
    Expected: CLI exits with code 0, 100% success rate
    """

    @pytest.fixture
    def results(self, e2e_robot_only_results: E2EResults) -> E2EResults:
        """Provide robot-only scenario results."""
        return e2e_robot_only_results


# =============================================================================
# PYATS API-ONLY SCENARIO TESTS
# =============================================================================


class TestE2EPyatsApiOnly(E2ECombinedTestBase):
    """E2E tests for the PyATS API-only scenario.

    Scenario: PyATS API (1 pass), no Robot or D2D tests
    Expected: CLI exits with code 0, 100% success rate
    """

    @pytest.fixture
    def results(self, e2e_pyats_api_only_results: E2EResults) -> E2EResults:
        """Provide PyATS API-only scenario results."""
        return e2e_pyats_api_only_results


# =============================================================================
# PYATS D2D-ONLY SCENARIO TESTS
# =============================================================================


class TestE2EPyatsD2dOnly(E2ECombinedTestBase):
    """E2E tests for the PyATS D2D-only scenario.

    Scenario: PyATS D2D (1 pass), no Robot or API tests
    Expected: CLI exits with code 0, 100% success rate
    """

    @pytest.fixture
    def results(self, e2e_pyats_d2d_only_results: E2EResults) -> E2EResults:
        """Provide PyATS D2D-only scenario results."""
        return e2e_pyats_d2d_only_results


# =============================================================================
# PYATS CATALYST CENTER (API + D2D) SCENARIO TESTS
# =============================================================================


class TestE2EPyatsCc(E2ECombinedTestBase):
    """E2E tests for the Catalyst Center scenario.

    Scenario: PyATS API (1 pass) + PyATS D2D (2 pass), no Robot tests
    Expected: CLI exits with code 0, 100% success rate
    """

    @pytest.fixture
    def results(self, e2e_pyats_cc_results: E2EResults) -> E2EResults:
        """Provide PyATS Catalyst Center scenario results."""
        return e2e_pyats_cc_results
