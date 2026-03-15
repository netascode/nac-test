# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for CombinedReportGenerator."""

from pathlib import Path

import pytest

from nac_test.core.constants import COMBINED_SUMMARY_FILENAME
from nac_test.core.reporting.combined_generator import (
    CombinedReportGenerator,
    _get_curl_example,
)
from nac_test.core.types import (
    CombinedResults,
    ExecutionState,
    PreFlightFailure,
    TestResults,
)


@pytest.fixture
def robot_results() -> TestResults:
    """Create Robot Framework TestResults for testing."""
    return TestResults(
        passed=2,
        failed=0,
        skipped=0,
    )


def test_combined_report_robot_only(tmp_path: Path, robot_results: TestResults) -> None:
    """Test combined report generation with Robot Framework results only."""
    generator = CombinedReportGenerator(tmp_path)

    # Generate combined summary with Robot stats only
    results = CombinedResults(robot=robot_results)
    result_path = generator.generate_combined_summary(results)

    # Verify file was created
    assert result_path is not None
    assert result_path.exists()
    assert result_path.name == COMBINED_SUMMARY_FILENAME

    # Verify content
    content = result_path.read_text()
    assert "Robot Framework" in content
    assert "Total Tests" in content
    assert "<h3>2</h3>" in content  # 2 total tests


def test_combined_report_with_pyats_and_robot(
    tmp_path: Path, robot_results: TestResults
) -> None:
    """Test combined report generation with both PyATS and Robot results."""
    generator = CombinedReportGenerator(tmp_path)

    # Combine PyATS and Robot stats using CombinedResults
    results = CombinedResults(
        api=TestResults(passed=2, failed=1, skipped=0),
        d2d=TestResults(passed=5, failed=0, skipped=0),
        robot=robot_results,
    )

    # Generate combined summary
    result_path = generator.generate_combined_summary(results)

    # Verify file was created
    assert result_path is not None
    assert result_path.exists()

    # Verify content includes all frameworks
    content = result_path.read_text()
    assert "Robot Framework" in content
    assert "PyATS API" in content
    assert "PyATS Direct-to-Device (D2D)" in content

    # Verify overall stats: 2 (Robot) + 3 (API) + 5 (D2D) = 10 total
    assert "Overall Executive Summary" in content
    # Overall stats should be accumulated: 2 + 2 + 5 = 9 passed


def test_combined_report_pyats_only(tmp_path: Path) -> None:
    """Test combined report generation with PyATS results only (no Robot)."""
    generator = CombinedReportGenerator(tmp_path)

    # PyATS stats only
    results = CombinedResults(
        api=TestResults(passed=8, failed=2, skipped=0),
    )

    # Generate combined summary (no Robot stats passed)
    result_path = generator.generate_combined_summary(results)

    # Verify file was created
    assert result_path is not None
    assert result_path.exists()

    # Verify content includes PyATS but not Robot
    content = result_path.read_text()
    assert "PyATS API" in content
    assert "Robot Framework" not in content  # Robot section shouldn't exist


def test_combined_report_success_rate_calculation(
    tmp_path: Path, robot_results: TestResults
) -> None:
    """Test that overall success rate is calculated correctly."""
    generator = CombinedReportGenerator(tmp_path)

    # Combine PyATS stats (3 passed, 1 failed = 75% success) with Robot stats (2 passed, 0 failed = 100%)
    # Overall: (3 + 2) passed / (4 + 2) total = 5/6 = 83.3%
    results = CombinedResults(
        api=TestResults(passed=3, failed=1, skipped=0),
        robot=robot_results,
    )

    # Generate combined summary
    result_path = generator.generate_combined_summary(results)

    assert result_path is not None
    content = result_path.read_text()

    # Verify success rate is calculated (approximately 83.3%)
    # The template formats to 1 decimal: "83.3%"
    assert "83.3%" in content or "83%" in content


def test_combined_report_no_tests(tmp_path: Path) -> None:
    """Test combined report generation with no test results at all."""
    generator = CombinedReportGenerator(tmp_path)

    # Generate combined summary with None
    result_path = generator.generate_combined_summary(results=None)

    # Should still generate a report
    assert result_path is not None
    assert result_path.exists()

    # Content should show 0 tests
    content = result_path.read_text()
    assert "Overall Executive Summary" in content


def test_combined_report_empty_results(tmp_path: Path) -> None:
    """Test combined report generation with empty CombinedResults."""
    generator = CombinedReportGenerator(tmp_path)

    # Generate combined summary with empty CombinedResults
    result_path = generator.generate_combined_summary(CombinedResults())

    # Should still generate a report
    assert result_path is not None
    assert result_path.exists()

    # Content should show 0 tests
    content = result_path.read_text()
    assert "Overall Executive Summary" in content
    assert ">0<" in content  # 0 total tests


def test_combined_results_with_robot_error(tmp_path: Path) -> None:
    """Test CombinedResults when Robot has error but PyATS succeeds."""
    # Create results: PyATS API succeeds, Robot has framework error
    results = CombinedResults(
        api=TestResults(passed=4, failed=1, skipped=0),
        robot=TestResults.from_error("Pabot execution failed"),
    )

    # Verify computed properties handle error correctly
    assert results.has_errors is True
    assert results.total == 5  # Robot error contributes 0 to total
    assert results.passed == 4
    assert results.failed == 1
    assert results.success_rate == 80.0  # 4/5 * 100

    # Verify report generation still works with error results
    generator = CombinedReportGenerator(tmp_path)
    report_path = generator.generate_combined_summary(results)

    assert report_path is not None
    assert report_path.exists()

    content = report_path.read_text()
    assert "PyATS API" in content
    assert "Robot Framework" in content  # with zero stats due to error


def test_combined_results_with_partial_failures(tmp_path: Path) -> None:
    """Test CombinedResults aggregation with mixed pass/fail across frameworks."""
    # Create mixed results: some pass, some fail in each framework
    results = CombinedResults(
        api=TestResults(passed=7, failed=3, skipped=0),
        d2d=TestResults(passed=6, failed=2, skipped=0),
        robot=TestResults(passed=3, failed=2, skipped=0),
    )

    # Verify aggregation
    assert results.has_errors is False  # No framework errors
    assert results.total == 23  # 10 + 8 + 5
    assert results.passed == 16  # 7 + 6 + 3
    assert results.failed == 7  # 3 + 2 + 2
    assert results.skipped == 0

    # Success rate: 16/23 = 69.57%
    expected_rate = (16 / 23) * 100
    assert abs(results.success_rate - expected_rate) < 0.01

    # Verify report generation with mixed results
    generator = CombinedReportGenerator(tmp_path)
    report_path = generator.generate_combined_summary(results)

    assert report_path is not None
    content = report_path.read_text()
    assert "PyATS API" in content
    assert "PyATS Direct-to-Device (D2D)" in content
    assert "Robot Framework" in content


def test_combined_report_exception_handling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that generate_combined_summary handles exceptions gracefully."""
    generator = CombinedReportGenerator(tmp_path)

    def raise_error(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Template rendering failed")

    monkeypatch.setattr(generator.env, "get_template", raise_error)

    results = CombinedResults(robot=TestResults(passed=5, failed=0, skipped=0))
    report_path = generator.generate_combined_summary(results)

    assert report_path is None


def test_combined_report_template_receives_stats_objects(tmp_path: Path) -> None:
    """Test that template receives TestResults/CombinedResults objects correctly."""
    generator = CombinedReportGenerator(tmp_path)

    results = CombinedResults(
        api=TestResults(passed=8, failed=2, skipped=0),
        robot=TestResults(passed=4, failed=1, skipped=0),
    )

    report_path = generator.generate_combined_summary(results)
    assert report_path is not None

    content = report_path.read_text()

    assert "<h3>15</h3>" in content
    assert "<h3>12</h3>" in content
    assert "<h3>3</h3>" in content
    assert "80.0%" in content


class TestGetCurlExample:
    """Tests for the _get_curl_example helper function."""

    def test_aci_curl_example(self) -> None:
        """ACI curl example generates complete auth command with JSON payload."""
        result = _get_curl_example("ACI", "https://apic.local")
        assert result.startswith("https://apic.local/api/aaaLogin.json")
        assert "-X POST" in result
        assert '-H "Content-Type: application/json"' in result
        assert '"aaaUser"' in result
        assert '"name":"USERNAME"' in result
        assert '"pwd":"PASSWORD"' in result

    def test_sdwan_curl_example(self) -> None:
        """SDWAN curl example generates form-encoded auth command."""
        result = _get_curl_example("SDWAN", "https://sdwan.local")
        assert result.startswith("https://sdwan.local/j_security_check")
        assert "-X POST" in result
        assert "j_username=USERNAME" in result
        assert "j_password=PASSWORD" in result

    def test_cc_curl_example(self) -> None:
        """CC curl example generates basic-auth command against token endpoint."""
        result = _get_curl_example("CC", "https://catc.local")
        assert result.startswith("https://catc.local/dna/system/api/v1/auth/token")
        assert "-X POST" in result
        assert '-u "USERNAME:PASSWORD"' in result

    def test_unknown_controller_returns_url_only(self) -> None:
        """Unknown controller types return just the URL as fallback."""
        result = _get_curl_example("MERAKI", "https://meraki.local")
        assert result == "https://meraki.local"


class TestPreFlightFailureReport:
    """Tests for pre-flight failure report generation."""

    def test_auth_failure_generates_report(self, tmp_path: Path) -> None:
        """Auth failure produces combined_summary.html with failure details."""
        failure = PreFlightFailure(
            failure_type="auth",
            controller_type="ACI",
            controller_url="https://apic.test.local",
            detail="HTTP 401: Unauthorized",
            status_code=401,
        )
        results = CombinedResults(pre_flight_failure=failure)
        generator = CombinedReportGenerator(tmp_path)

        report_path = generator.generate_combined_summary(results)

        assert report_path is not None
        assert report_path.name == COMBINED_SUMMARY_FILENAME
        content = report_path.read_text()
        assert "apic.test.local" in content
        assert "401" in content

    def test_401_failure_does_not_render_privileges_guidance(
        self, tmp_path: Path
    ) -> None:
        """HTTP 401 must NOT trigger the 403-specific privileges/role guidance."""
        failure = PreFlightFailure(
            failure_type="auth",
            controller_type="ACI",
            controller_url="https://apic.test.local",
            detail="HTTP 401: Unauthorized",
            status_code=401,
        )
        results = CombinedResults(pre_flight_failure=failure)
        generator = CombinedReportGenerator(tmp_path)

        report_path = generator.generate_combined_summary(results)

        assert report_path is not None
        content = report_path.read_text()
        # 403-specific guidance must NOT appear for 401 errors
        assert "sufficient privileges" not in content
        assert "role and permissions" not in content

    def test_unreachable_failure_generates_report(self, tmp_path: Path) -> None:
        """Unreachable failure produces report with connection error context."""
        failure = PreFlightFailure(
            failure_type="unreachable",
            controller_type="SDWAN",
            controller_url="https://sdwan.test.local",
            detail="Connection timed out",
        )
        results = CombinedResults(pre_flight_failure=failure)
        generator = CombinedReportGenerator(tmp_path)

        report_path = generator.generate_combined_summary(results)

        assert report_path is not None
        content = report_path.read_text()
        assert "sdwan.test.local" in content
        assert "timed out" in content

    def test_403_failure_renders_privileges_guidance(self, tmp_path: Path) -> None:
        """HTTP 403 in detail triggers the is_403 template branch with role/permissions advice."""
        failure = PreFlightFailure(
            failure_type="auth",
            controller_type="CC",
            controller_url="https://catc.test.local",
            detail="HTTP 403: Forbidden",
            status_code=403,
        )
        results = CombinedResults(pre_flight_failure=failure)
        generator = CombinedReportGenerator(tmp_path)

        report_path = generator.generate_combined_summary(results)

        assert report_path is not None
        content = report_path.read_text()
        assert "catc.test.local" in content
        # 403-specific template content: privileges callout and role guidance
        assert "sufficient privileges" in content
        assert "role and permissions" in content

    def test_no_legacy_auth_failure_report_generated(self, tmp_path: Path) -> None:
        """Pre-flight failure must NOT produce the legacy auth_failure_report.html."""
        failure = PreFlightFailure(
            failure_type="auth",
            controller_type="ACI",
            controller_url="https://apic.test.local",
            detail="HTTP 401: Unauthorized",
            status_code=401,
        )
        results = CombinedResults(pre_flight_failure=failure)
        generator = CombinedReportGenerator(tmp_path)

        report_path = generator.generate_combined_summary(results)

        assert report_path is not None
        # Only combined_summary.html should exist — no legacy standalone report
        generated_files = [f.name for f in tmp_path.iterdir() if f.is_file()]
        assert COMBINED_SUMMARY_FILENAME in generated_files
        assert "auth_failure_report.html" not in generated_files

    def test_pre_flight_failure_exception_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Template rendering failure returns None gracefully."""
        generator = CombinedReportGenerator(tmp_path)

        def raise_error(*args: object, **kwargs: object) -> None:
            raise RuntimeError("Template rendering failed")

        monkeypatch.setattr(generator.env, "get_template", raise_error)

        failure = PreFlightFailure(
            failure_type="auth",
            controller_type="ACI",
            controller_url="https://apic.test.local",
            detail="HTTP 401: Unauthorized",
            status_code=401,
        )
        results = CombinedResults(pre_flight_failure=failure)
        report_path = generator.generate_combined_summary(results)

        assert report_path is None


class TestHasReportFlag:
    """Tests for has_report flag in framework_data dictionary."""

    def test_has_report_true_when_test_results_has_tests(self, tmp_path: Path) -> None:
        """has_report is True when TestResults exists with total > 0."""
        generator = CombinedReportGenerator(tmp_path)

        test_results = TestResults(passed=5, failed=0, skipped=0)
        results = CombinedResults(api=test_results)

        report_path = generator.generate_combined_summary(results)
        assert report_path is not None
        content = report_path.read_text()
        assert "PyATS API" in content
        assert "View Detailed Report" in content

    def test_has_report_false_when_test_results_is_none(self, tmp_path: Path) -> None:
        """has_report is False when TestResults is None."""
        generator = CombinedReportGenerator(tmp_path)

        test_results = TestResults(passed=2, failed=0, skipped=0)
        results = CombinedResults(robot=test_results)

        report_path = generator.generate_combined_summary(results)
        assert report_path is not None
        content = report_path.read_text()
        assert "PyATS API" not in content

    def test_has_report_false_when_test_results_is_empty(self, tmp_path: Path) -> None:
        """has_report is False when TestResults.is_empty (total=0)."""
        generator = CombinedReportGenerator(tmp_path)

        empty_results = TestResults.empty()
        results = CombinedResults(api=empty_results)

        report_path = generator.generate_combined_summary(results)
        assert report_path is not None
        content = report_path.read_text()
        assert "PyATS API Test Results" in content
        assert "View Detailed Report →" not in content

    @pytest.mark.parametrize(
        "execution_state",
        [
            ExecutionState.SUCCESS,
            ExecutionState.EMPTY,
            ExecutionState.ERROR,
            ExecutionState.SKIPPED,
        ],
    )
    def test_has_report_false_for_all_execution_states_with_zero_tests(
        self, tmp_path: Path, execution_state: ExecutionState
    ) -> None:
        """has_report is False for all ExecutionState values when total=0."""
        generator = CombinedReportGenerator(tmp_path)

        test_results = TestResults(state=execution_state)
        assert test_results.is_empty
        results = CombinedResults(api=test_results)

        report_path = generator.generate_combined_summary(results)
        assert report_path is not None
        content = report_path.read_text()
        assert "PyATS API Test Results" in content
        assert "View Detailed Report →" not in content

    @pytest.mark.parametrize(
        ("execution_state", "test_values"),
        [
            (ExecutionState.SUCCESS, {"passed": 5, "failed": 0, "skipped": 0}),
            (ExecutionState.EMPTY, {"passed": 0, "failed": 0, "skipped": 0}),
            (ExecutionState.ERROR, {"passed": 0, "failed": 0, "skipped": 0}),
            (ExecutionState.SKIPPED, {"passed": 0, "failed": 0, "skipped": 0}),
        ],
    )
    def test_has_report_respects_is_empty_across_all_states(
        self,
        tmp_path: Path,
        execution_state: ExecutionState,
        test_values: dict[str, int],
    ) -> None:
        """has_report depends on is_empty property across all ExecutionState values."""
        generator = CombinedReportGenerator(tmp_path)

        test_results = TestResults(
            state=execution_state,
            passed=test_values["passed"],
            failed=test_values["failed"],
            skipped=test_values["skipped"],
        )
        results = CombinedResults(api=test_results)

        report_path = generator.generate_combined_summary(results)
        assert report_path is not None

        content = report_path.read_text()
        if test_results.total > 0:
            assert "View Detailed Report →" in content
        else:
            assert "View Detailed Report →" not in content
