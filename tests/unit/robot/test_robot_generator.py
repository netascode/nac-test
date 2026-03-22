# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# mypy: disable-error-code="no-untyped-def,method-assign"
# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for Robot Framework report generator."""

from pathlib import Path

import pytest

from nac_test.core.constants import (
    OUTPUT_XML,
    ROBOT_RESULTS_DIRNAME,
    SUMMARY_REPORT_FILENAME,
)
from nac_test.robot.reporting.robot_generator import RobotReportGenerator


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    robot_results = output_dir / ROBOT_RESULTS_DIRNAME
    robot_results.mkdir()
    return output_dir


@pytest.fixture
def mock_robot_output_xml(temp_output_dir: Path) -> Path:
    """Create a minimal mock Robot output.xml file."""
    output_xml = temp_output_dir / ROBOT_RESULTS_DIRNAME / OUTPUT_XML
    output_xml.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.1.1 (Python 3.12.10 on darwin)" generated="2025-02-01T12:00:00.000000">
  <suite name="Test Suite" id="s1">
    <test name="Test Case 1" id="s1-t1">
      <status status="PASS" start="2025-02-01T12:00:01.000000" elapsed="0.5"/>
    </test>
    <test name="Test Case 2" id="s1-t2">
      <status status="FAIL" start="2025-02-01T12:00:02.000000" elapsed="1.0">AssertionError: Expected value</status>
    </test>
    <status status="FAIL" start="2025-02-01T12:00:00.000000" elapsed="2.0"/>
  </suite>
  <statistics>
    <total>
      <stat pass="1" fail="1" skip="0">All Tests</stat>
    </total>
  </statistics>
</robot>
""")
    return output_xml


def test_generator_initialization(temp_output_dir) -> None:
    """Test generator initialization."""
    generator = RobotReportGenerator(temp_output_dir)
    assert generator.output_dir == temp_output_dir
    assert generator.robot_results_dir == temp_output_dir / ROBOT_RESULTS_DIRNAME
    assert generator.env is not None


def test_generate_summary_report_success(
    temp_output_dir, mock_robot_output_xml
) -> None:
    """Test generating summary report HTML."""
    generator = RobotReportGenerator(temp_output_dir)
    report_path, stats = generator.generate_summary_report()

    assert report_path is not None
    assert report_path.exists()
    assert report_path.name == SUMMARY_REPORT_FILENAME
    assert report_path.parent == temp_output_dir / ROBOT_RESULTS_DIRNAME

    # Verify stats are returned correctly
    assert stats.total == 2
    assert stats.passed == 1
    assert stats.failed == 1
    assert stats.skipped == 0

    # Verify HTML content contains expected elements
    content = report_path.read_text()
    assert "Network as Code Test Results Summary" in content
    assert "Test Case 1" in content
    assert "Test Case 2" in content


def test_generate_summary_report_missing_output_xml(temp_output_dir) -> None:
    """Test generating summary report when output.xml is missing."""
    generator = RobotReportGenerator(temp_output_dir)
    report_path, stats = generator.generate_summary_report()

    # Should return None path and empty stats when no output.xml exists
    assert report_path is None
    assert stats.total == 0
    assert stats.passed == 0
    assert stats.failed == 0
    assert stats.skipped == 0


def test_deep_link_generation(
    temp_output_dir: Path, mock_robot_output_xml: Path
) -> None:
    """Test that deep links to Robot log.html are generated correctly."""
    generator = RobotReportGenerator(temp_output_dir)
    report_path, _ = generator.generate_summary_report()
    assert report_path is not None
    content = report_path.read_text()
    # Deep links should point to log.html with test IDs
    assert "log.html#" in content


def test_status_mapping(temp_output_dir) -> None:
    """Test that Robot statuses (PASS/FAIL/SKIP) map correctly to display."""
    output_xml = temp_output_dir / ROBOT_RESULTS_DIRNAME / OUTPUT_XML
    output_xml.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.1.1" generated="2025-02-01T12:00:00.000000">
  <suite name="Suite" id="s1">
    <test name="Passed Test" id="s1-t1">
      <status status="PASS" start="2025-02-01T12:00:00.000000" elapsed="0.1"/>
    </test>
    <test name="Failed Test" id="s1-t2">
      <status status="FAIL" start="2025-02-01T12:00:01.000000" elapsed="0.1">Test failed</status>
    </test>
    <test name="Skipped Test" id="s1-t3">
      <status status="SKIP" start="2025-02-01T12:00:02.000000" elapsed="0.0"/>
    </test>
    <status status="FAIL" start="2025-02-01T12:00:00.000000" elapsed="0.2"/>
  </suite>
  <statistics>
    <total>
      <stat pass="1" fail="1" skip="1">All Tests</stat>
    </total>
  </statistics>
</robot>
""")

    generator = RobotReportGenerator(temp_output_dir)
    _, stats = generator.generate_summary_report()

    assert stats.total == 3
    assert stats.passed == 1
    assert stats.failed == 1
    assert stats.skipped == 1


def test_generate_summary_report_no_tests(temp_output_dir) -> None:
    """Test that generate_summary_report returns None when output.xml has zero tests."""
    output_xml = temp_output_dir / ROBOT_RESULTS_DIRNAME / OUTPUT_XML
    output_xml.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.1.1" generated="2025-02-01T12:00:00.000000">
  <suite name="Empty Suite" id="s1">
    <status status="PASS" start="2025-02-01T12:00:00.000000" elapsed="0.0"/>
  </suite>
  <statistics>
    <total>
      <stat pass="0" fail="0" skip="0">All Tests</stat>
    </total>
  </statistics>
</robot>
""")

    generator = RobotReportGenerator(temp_output_dir)
    report_path, stats = generator.generate_summary_report()

    assert report_path is None
    assert stats.total == 0


def test_generate_summary_report_exception_handling(temp_output_dir) -> None:
    """Test that generate_summary_report captures errors in TestResults."""
    output_xml = temp_output_dir / ROBOT_RESULTS_DIRNAME / OUTPUT_XML
    output_xml.write_text("invalid xml content that will cause parsing error")

    generator = RobotReportGenerator(temp_output_dir)
    report_path, stats = generator.generate_summary_report()

    assert report_path is None
    assert stats.total == 0
    assert stats.has_error is True
    assert stats.reason is not None
    assert "Failed to parse output.xml" in stats.reason


def test_template_receives_stats_object(temp_output_dir, mock_robot_output_xml) -> None:
    """Test that template receives TestResults object and renders stats correctly."""
    generator = RobotReportGenerator(temp_output_dir)
    report_path, _ = generator.generate_summary_report()

    assert report_path is not None
    content = report_path.read_text()

    assert "<h3>2</h3>" in content
    assert "<h3>1</h3>" in content
    assert "50.0%" in content
