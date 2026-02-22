# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# mypy: disable-error-code="no-untyped-def,method-assign"
# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for Robot Framework result parser."""

from pathlib import Path

import pytest
from robot.errors import DataError

from nac_test.robot.reporting.robot_output_parser import RobotResultParser


@pytest.fixture
def sample_output_xml(tmp_path: Path) -> Path:
    """Create a sample output.xml file for testing.

    Creates a minimal Robot Framework output.xml with:
    - 2 passed tests
    - 1 failed test
    - 1 skipped test
    """
    output_xml = tmp_path / "output.xml"
    content = """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2025-02-01T12:00:00.000" rpa="false" schemaversion="5">
<suite id="s1" name="Test Suite" source="/path/to/tests">
<test id="s1-t1" name="Test Case 1" line="10">
<kw name="Log" owner="BuiltIn">
<arg>Test message</arg>
<status status="PASS" start="2025-02-01T12:00:01.000" elapsed="0.100"/>
</kw>
<status status="PASS" start="2025-02-01T12:00:01.000" elapsed="0.100">Test passed</status>
</test>
<test id="s1-t2" name="Test Case 2" line="15">
<kw name="Fail" owner="BuiltIn">
<arg>Expected failure</arg>
<status status="FAIL" start="2025-02-01T12:00:02.000" elapsed="0.050"/>
</kw>
<status status="FAIL" start="2025-02-01T12:00:02.000" elapsed="0.050">Expected failure</status>
</test>
<test id="s1-t3" name="Test Case 3" line="20">
<kw name="Pass Execution" owner="BuiltIn">
<arg>Skipped test</arg>
<status status="PASS" start="2025-02-01T12:00:03.000" elapsed="0.010"/>
</kw>
<status status="SKIP" start="2025-02-01T12:00:03.000" elapsed="0.010">Skipped test</status>
</test>
<test id="s1-t4" name="Test Case 4" line="25">
<kw name="Log" owner="BuiltIn">
<arg>Another passing test</arg>
<status status="PASS" start="2025-02-01T12:00:04.000" elapsed="0.200"/>
</kw>
<status status="PASS" start="2025-02-01T12:00:04.000" elapsed="0.200">Another pass</status>
</test>
<status status="FAIL" start="2025-02-01T12:00:00.000" elapsed="5.000"/>
</suite>
<statistics>
<total>
<stat pass="2" fail="1" skip="1">All Tests</stat>
</total>
<tag>
</tag>
<suite>
<stat pass="2" fail="1" skip="1" id="s1" name="Test Suite">Test Suite</stat>
</suite>
</statistics>
</robot>"""
    output_xml.write_text(content)
    return output_xml


def test_parser_initialization(sample_output_xml: Path) -> None:
    """Test parser can be initialized with a valid path."""
    parser = RobotResultParser(sample_output_xml)
    assert parser.output_xml_path == sample_output_xml


def test_parser_missing_file() -> None:
    """Test parser raises FileNotFoundError for missing file."""
    parser = RobotResultParser(Path("/nonexistent/output.xml"))
    with pytest.raises(FileNotFoundError, match="output.xml not found"):
        parser.parse()


def test_parser_basic_stats(sample_output_xml: Path) -> None:
    """Test parser extracts correct statistics."""
    parser = RobotResultParser(sample_output_xml)
    data = parser.parse()

    stats = data["aggregated_stats"]
    assert stats.total == 4
    assert stats.passed == 2
    assert stats.failed == 1
    assert stats.skipped == 1
    # Success rate = passed / (total - skipped) = 2 / 3 = 66.67%
    assert abs(stats.success_rate - 66.67) < 0.1


def test_parser_test_list(sample_output_xml: Path) -> None:
    """Test parser extracts test list with correct data."""
    parser = RobotResultParser(sample_output_xml)
    data = parser.parse()

    tests = data["tests"]
    assert len(tests) == 4

    # Tests should be sorted with failed tests first
    assert tests[0]["status"] == "FAIL"
    assert tests[0]["name"] == "Test Case 2"
    assert tests[0]["test_id"] == "s1-t2"
    assert tests[0]["message"] == "Expected failure"

    # Check duration conversion (milliseconds to seconds)
    assert abs(tests[0]["duration"] - 0.050) < 0.001


def test_parser_test_sorting(sample_output_xml: Path) -> None:
    """Test that failed tests are sorted first."""
    parser = RobotResultParser(sample_output_xml)
    data = parser.parse()

    tests = data["tests"]

    # First test should be the failed one
    assert tests[0]["status"] == "FAIL"

    # Rest should be PASS or SKIP, sorted by name
    other_tests = tests[1:]
    assert all(t["status"] in ["PASS", "SKIP"] for t in other_tests)


def test_parser_timestamp_parsing(sample_output_xml: Path) -> None:
    """Test timestamp parsing from Robot format."""
    parser = RobotResultParser(sample_output_xml)
    data = parser.parse()

    tests = data["tests"]

    # Check that timestamps are in ISO format
    for test in tests:
        if test["start_time"]:
            # Should be ISO format like '2025-02-01T12:00:01'
            assert "T" in test["start_time"]
            assert len(test["start_time"]) >= 19  # YYYY-MM-DDTHH:MM:SS


def test_parser_all_passed(tmp_path: Path) -> None:
    """Test parser with all tests passing."""
    output_xml = tmp_path / "output.xml"
    content = """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2025-02-01T12:00:00.000">
<suite id="s1" name="Test Suite">
<test id="s1-t1" name="Test 1" line="10">
<status status="PASS" start="2025-02-01T12:00:01" elapsed="100"/>
</test>
<test id="s1-t2" name="Test 2" line="15">
<status status="PASS" start="2025-02-01T12:00:02" elapsed="150"/>
</test>
<status status="PASS" start="2025-02-01T12:00:00" elapsed="300"/>
</suite>
<statistics>
<total>
<stat pass="2" fail="0" skip="0">All Tests</stat>
</total>
</statistics>
</robot>"""
    output_xml.write_text(content)

    parser = RobotResultParser(output_xml)
    data = parser.parse()

    stats = data["aggregated_stats"]
    assert stats.total == 2
    assert stats.passed == 2
    assert stats.failed == 0
    assert stats.skipped == 0
    assert stats.success_rate == 100.0


def test_parser_suite_name_extraction(sample_output_xml: Path) -> None:
    """Test that suite names are extracted correctly."""
    parser = RobotResultParser(sample_output_xml)
    data = parser.parse()

    tests = data["tests"]

    # All tests should have suite name "Test Suite"
    for test in tests:
        assert test["suite_name"] == "Test Suite"


def test_parser_test_id_for_deep_linking(sample_output_xml: Path) -> None:
    """Test that test IDs are extracted for deep linking."""
    parser = RobotResultParser(sample_output_xml)
    data = parser.parse()

    tests = data["tests"]

    # Check test IDs follow Robot's format (s1-t1, s1-t2, etc.)
    test_ids = [t["test_id"] for t in tests]
    assert "s1-t1" in test_ids
    assert "s1-t2" in test_ids
    assert "s1-t3" in test_ids
    assert "s1-t4" in test_ids


def test_collector_empty_results(tmp_path: Path) -> None:
    """Test parser with no tests."""
    output_xml = tmp_path / "output.xml"
    content = """<?xml version="1.0" encoding="UTF-8"?>
<robot generator="Robot 7.0" generated="2025-02-01T12:00:00.000">
<suite id="s1" name="Empty Suite">
<status status="PASS" start="2025-02-01T12:00:00" elapsed="0"/>
</suite>
<statistics>
<total>
<stat pass="0" fail="0" skip="0">All Tests</stat>
</total>
</statistics>
</robot>"""
    output_xml.write_text(content)

    parser = RobotResultParser(output_xml)
    data = parser.parse()

    stats = data["aggregated_stats"]
    assert stats.total == 0
    assert stats.passed == 0
    assert stats.failed == 0
    assert stats.skipped == 0
    assert stats.success_rate == 0.0

    assert len(data["tests"]) == 0


def test_parse_corrupted_xml_structure(tmp_path: Path) -> None:
    """Test parser with valid XML but corrupted structure.

    This test creates XML that is syntactically valid but lacks the expected
    Robot Framework elements (no root <robot> element). ExecutionResult should
    raise an exception when it cannot parse the expected structure.
    """
    output_xml = tmp_path / "output.xml"
    # Valid XML but missing the expected <robot> root element
    # ExecutionResult expects a <robot> element at the root
    content = """<?xml version="1.0" encoding="UTF-8"?>
<invalid_root generator="Robot 7.0" generated="2025-02-01T12:00:00.000">
<suite id="s1" name="Test Suite">
<test id="s1-t1" name="Test Case 1" line="10">
<status status="PASS" start="2025-02-01T12:00:01.000" elapsed="0.100"/>
</test>
<status status="PASS" start="2025-02-01T12:00:00.000" elapsed="0.100"/>
</suite>
</invalid_root>"""
    output_xml.write_text(content)

    parser = RobotResultParser(output_xml)
    # ExecutionResult raises DataError when XML structure is invalid
    with pytest.raises(DataError):
        parser.parse()
