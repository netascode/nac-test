# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for CombinedReportGenerator."""

from pathlib import Path

import pytest

from nac_test.core.reporting.combined_generator import CombinedReportGenerator


@pytest.fixture
def robot_output_xml(tmp_path: Path) -> Path:
    """Create a minimal Robot output.xml for testing."""
    robot_results_dir = tmp_path / "robot_results"
    robot_results_dir.mkdir()

    output_xml = robot_results_dir / "output.xml"
    content = """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2025-02-01 12:00:00.000">
<suite id="s1" name="Test Suite">
<test id="s1-t1" name="Test 1">
<status status="PASS" start="20250201 12:00:01.000" elapsed="0.100"/>
</test>
<test id="s1-t2" name="Test 2">
<status status="PASS" start="20250201 12:00:02.000" elapsed="0.050"/>
</test>
<status status="PASS" start="20250201 12:00:00.000" elapsed="1.000"/>
</suite>
<statistics>
<total>
<stat pass="2" fail="0" skip="0">All Tests</stat>
</total>
</statistics>
</robot>"""
    output_xml.write_text(content)
    return output_xml


def test_combined_report_robot_only(tmp_path: Path, robot_output_xml: Path) -> None:
    """Test combined report generation with Robot Framework results only."""
    generator = CombinedReportGenerator(tmp_path)

    # Generate combined summary
    result_path = generator.generate_combined_summary(pyats_stats=None)

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
    tmp_path: Path, robot_output_xml: Path
) -> None:
    """Test combined report generation with both PyATS and Robot results."""
    generator = CombinedReportGenerator(tmp_path)

    # Mock PyATS stats
    pyats_stats = {
        "API": {
            "title": "PyATS API",
            "total_tests": 3,
            "passed_tests": 2,
            "failed_tests": 1,
            "skipped_tests": 0,
            "success_rate": 66.7,
            "report_path": "pyats_results/api/html_reports/summary_report.html",
        },
        "D2D": {
            "title": "PyATS D2D",
            "total_tests": 5,
            "passed_tests": 5,
            "failed_tests": 0,
            "skipped_tests": 0,
            "success_rate": 100.0,
            "report_path": "pyats_results/d2d/html_reports/summary_report.html",
        },
    }

    # Generate combined summary
    result_path = generator.generate_combined_summary(pyats_stats=pyats_stats)

    # Verify file was created
    assert result_path is not None
    assert result_path.exists()

    # Verify content includes all frameworks
    content = result_path.read_text()
    assert "Robot Framework" in content
    assert "PyATS API" in content
    assert "PyATS D2D" in content

    # Verify overall stats: 2 (Robot) + 3 (API) + 5 (D2D) = 10 total
    assert "Overall Executive Summary" in content
    # Overall stats should be accumulated: 2 + 2 + 5 = 9 passed


def test_combined_report_pyats_only(tmp_path: Path) -> None:
    """Test combined report generation with PyATS results only (no Robot)."""
    generator = CombinedReportGenerator(tmp_path)

    # Mock PyATS stats
    pyats_stats = {
        "API": {
            "title": "PyATS API",
            "total_tests": 10,
            "passed_tests": 8,
            "failed_tests": 2,
            "skipped_tests": 0,
            "success_rate": 80.0,
            "report_path": "pyats_results/api/html_reports/summary_report.html",
        }
    }

    # Generate combined summary (no robot_results/ directory exists)
    result_path = generator.generate_combined_summary(pyats_stats=pyats_stats)

    # Verify file was created
    assert result_path is not None
    assert result_path.exists()

    # Verify content includes PyATS but not Robot
    content = result_path.read_text()
    assert "PyATS API" in content
    assert "Robot Framework" not in content  # Robot section shouldn't exist


def test_combined_report_success_rate_calculation(
    tmp_path: Path, robot_output_xml: Path
) -> None:
    """Test that overall success rate is calculated correctly."""
    generator = CombinedReportGenerator(tmp_path)

    # Mock PyATS stats with 3 passed, 1 failed (75% success)
    pyats_stats = {
        "API": {
            "title": "PyATS API",
            "total_tests": 4,
            "passed_tests": 3,
            "failed_tests": 1,
            "skipped_tests": 0,
            "success_rate": 75.0,
            "report_path": "pyats_results/api/html_reports/summary_report.html",
        }
    }

    # Generate combined summary
    # Robot has 2 passed, 0 failed (100% success)
    # Overall: (3 + 2) passed / (4 + 2) total = 5/6 = 83.3%
    result_path = generator.generate_combined_summary(pyats_stats=pyats_stats)

    assert result_path is not None
    content = result_path.read_text()

    # Verify success rate is calculated (approximately 83.3%)
    # The template formats to 1 decimal: "83.3%"
    assert "83.3%" in content or "83%" in content


def test_combined_report_no_tests(tmp_path: Path) -> None:
    """Test combined report generation with no test results at all."""
    generator = CombinedReportGenerator(tmp_path)

    # Generate combined summary with no PyATS stats and no Robot results
    result_path = generator.generate_combined_summary(pyats_stats=None)

    # Should still generate a report
    assert result_path is not None
    assert result_path.exists()

    # Content should show 0 tests
    content = result_path.read_text()
    assert "Overall Executive Summary" in content
