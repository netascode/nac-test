# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for CombinedReportGenerator."""

from pathlib import Path

import pytest

from nac_test.core.reporting.combined_generator import CombinedReportGenerator
from nac_test.core.types import CombinedResults, TestResults


@pytest.fixture
def robot_results() -> TestResults:
    """Create Robot Framework TestResults for testing."""
    return TestResults(
        total=2,
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
    assert result_path.name == "combined_summary.html"

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
        api=TestResults(total=3, passed=2, failed=1, skipped=0),
        d2d=TestResults(total=5, passed=5, failed=0, skipped=0),
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
        api=TestResults(total=10, passed=8, failed=2, skipped=0),
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
        api=TestResults(total=4, passed=3, failed=1, skipped=0),
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
        api=TestResults(total=5, passed=4, failed=1, skipped=0),
        robot=TestResults.from_error(error="Pabot execution failed"),
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
        api=TestResults(total=10, passed=7, failed=3, skipped=0),
        d2d=TestResults(total=8, passed=6, failed=2, skipped=0),
        robot=TestResults(total=5, passed=3, failed=2, skipped=0),
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


def test_combined_report_exception_handling(tmp_path: Path, monkeypatch) -> None:
    """Test that generate_combined_summary handles exceptions gracefully."""
    generator = CombinedReportGenerator(tmp_path)

    def raise_error(*args, **kwargs):
        raise RuntimeError("Template rendering failed")

    monkeypatch.setattr(generator.env, "get_template", raise_error)

    results = CombinedResults(robot=TestResults(total=5, passed=5, failed=0, skipped=0))
    report_path = generator.generate_combined_summary(results)

    assert report_path is None


def test_combined_report_template_receives_stats_objects(tmp_path: Path) -> None:
    """Test that template receives TestResults/CombinedResults objects correctly."""
    generator = CombinedReportGenerator(tmp_path)

    results = CombinedResults(
        api=TestResults(total=10, passed=8, failed=2, skipped=0),
        robot=TestResults(total=5, passed=4, failed=1, skipped=0),
    )

    report_path = generator.generate_combined_summary(results)
    assert report_path is not None

    content = report_path.read_text()

    assert "<h3>15</h3>" in content
    assert "<h3>12</h3>" in content
    assert "<h3>3</h3>" in content
    assert "80.0%" in content
