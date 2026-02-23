# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from nac_test.core.constants import XUNIT_XML
from nac_test.utils.xunit_merger import (
    XUnitStats,
    collect_xunit_files,
    merge_xunit_files,
    merge_xunit_results,
)


class TestXUnitStats:
    def test_default_values(self) -> None:
        stats = XUnitStats()
        assert stats.tests == 0
        assert stats.failures == 0
        assert stats.errors == 0
        assert stats.skipped == 0
        assert stats.time == 0.0

    def test_add_aggregates_values(self) -> None:
        stats1 = XUnitStats(tests=5, failures=1, errors=0, skipped=1, time=10.5)
        stats2 = XUnitStats(tests=3, failures=0, errors=1, skipped=0, time=5.25)

        stats1.add(stats2)

        assert stats1.tests == 8
        assert stats1.failures == 1
        assert stats1.errors == 1
        assert stats1.skipped == 1
        assert stats1.time == 15.75


class TestMergeXunitFiles:
    def test_merge_single_testsuite_file(self, tmp_path: Path) -> None:
        xunit_content = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="Robot.Suite" tests="3" failures="1" errors="0" skipped="1" time="5.500">
  <testcase name="test1" classname="Robot.Suite" time="1.5"/>
  <testcase name="test2" classname="Robot.Suite" time="2.0">
    <failure message="assertion failed" type="AssertionError"/>
  </testcase>
  <testcase name="test3" classname="Robot.Suite" time="2.0">
    <skipped message="skip reason"/>
  </testcase>
</testsuite>"""

        xunit_file = tmp_path / "xunit.xml"
        xunit_file.write_text(xunit_content)
        output_file = tmp_path / "merged.xml"

        result = merge_xunit_files([(xunit_file, "robot")], output_file)

        assert result == output_file
        assert output_file.exists()

        tree = ET.parse(output_file)
        root = tree.getroot()

        assert root.tag == "testsuites"
        assert root.get("tests") == "3"
        assert root.get("failures") == "1"
        assert root.get("errors") == "0"
        assert root.get("skipped") == "1"
        assert float(root.get("time") or 0) == pytest.approx(5.5, rel=0.01)

        testsuites = root.findall("testsuite")
        assert len(testsuites) == 1
        assert testsuites[0].get("name") == "robot: Robot.Suite"

    def test_merge_testsuites_wrapper_file(self, tmp_path: Path) -> None:
        xunit_content = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="Suite1" tests="2" failures="0" errors="0" skipped="0" time="1.0">
    <testcase name="test1" classname="Suite1" time="0.5"/>
    <testcase name="test2" classname="Suite1" time="0.5"/>
  </testsuite>
  <testsuite name="Suite2" tests="1" failures="1" errors="0" skipped="0" time="2.0">
    <testcase name="test3" classname="Suite2" time="2.0">
      <failure message="failed"/>
    </testcase>
  </testsuite>
</testsuites>"""

        xunit_file = tmp_path / "xunit.xml"
        xunit_file.write_text(xunit_content)
        output_file = tmp_path / "merged.xml"

        result = merge_xunit_files([(xunit_file, "pyats")], output_file)

        assert result == output_file
        tree = ET.parse(output_file)
        root = tree.getroot()

        assert root.get("tests") == "3"
        assert root.get("failures") == "1"

        testsuites = root.findall("testsuite")
        assert len(testsuites) == 2
        assert testsuites[0].get("name") == "pyats: Suite1"
        assert testsuites[1].get("name") == "pyats: Suite2"

    def test_merge_multiple_files(self, tmp_path: Path) -> None:
        robot_content = """<?xml version="1.0"?>
<testsuite name="Robot" tests="5" failures="1" errors="0" skipped="0" time="10.0">
  <testcase name="robot_test" classname="Robot" time="10.0"/>
</testsuite>"""

        pyats_content = """<?xml version="1.0"?>
<testsuite name="PyATS" tests="3" failures="0" errors="1" skipped="1" time="5.0">
  <testcase name="pyats_test" classname="PyATS" time="5.0"/>
</testsuite>"""

        robot_file = tmp_path / "robot_xunit.xml"
        robot_file.write_text(robot_content)

        pyats_file = tmp_path / "pyats_xunit.xml"
        pyats_file.write_text(pyats_content)

        output_file = tmp_path / "merged.xml"

        result = merge_xunit_files(
            [(robot_file, "robot"), (pyats_file, "pyats_api")],
            output_file,
        )

        assert result == output_file
        tree = ET.parse(output_file)
        root = tree.getroot()

        assert root.get("tests") == "8"
        assert root.get("failures") == "1"
        assert root.get("errors") == "1"
        assert root.get("skipped") == "1"
        assert float(root.get("time") or 0) == pytest.approx(15.0, rel=0.01)

        testsuites = root.findall("testsuite")
        assert len(testsuites) == 2

    def test_skips_nonexistent_files(self, tmp_path: Path) -> None:
        existing_content = """<?xml version="1.0"?>
<testsuite name="Existing" tests="1" failures="0" errors="0" skipped="0" time="1.0">
  <testcase name="test" classname="Existing" time="1.0"/>
</testsuite>"""

        existing_file = tmp_path / "existing.xml"
        existing_file.write_text(existing_content)
        nonexistent_file = tmp_path / "nonexistent.xml"
        output_file = tmp_path / "merged.xml"

        result = merge_xunit_files(
            [(existing_file, "existing"), (nonexistent_file, "missing")],
            output_file,
        )

        assert result == output_file
        tree = ET.parse(output_file)
        root = tree.getroot()
        assert root.get("tests") == "1"

    def test_skips_directory_instead_of_file(self, tmp_path: Path) -> None:
        """Directories should be skipped even if path exists."""
        existing_content = """<?xml version="1.0"?>
<testsuite name="Existing" tests="1" failures="0" errors="0" skipped="0" time="1.0">
  <testcase name="test" classname="Existing" time="1.0"/>
</testsuite>"""

        existing_file = tmp_path / "existing.xml"
        existing_file.write_text(existing_content)
        directory_path = tmp_path / "actually_a_dir.xml"
        directory_path.mkdir()
        output_file = tmp_path / "merged.xml"

        result = merge_xunit_files(
            [(existing_file, "existing"), (directory_path, "directory")],
            output_file,
        )

        assert result == output_file
        tree = ET.parse(output_file)
        root = tree.getroot()
        assert root.get("tests") == "1"
        testsuites = root.findall("testsuite")
        assert len(testsuites) == 1
        assert testsuites[0].get("name") == "existing: Existing"

    def test_returns_none_for_no_valid_files(self, tmp_path: Path) -> None:
        output_file = tmp_path / "merged.xml"
        result = merge_xunit_files([], output_file)
        assert result is None
        assert not output_file.exists()

    def test_returns_none_for_only_nonexistent_files(self, tmp_path: Path) -> None:
        output_file = tmp_path / "merged.xml"
        result = merge_xunit_files(
            [(tmp_path / "a.xml", "a"), (tmp_path / "b.xml", "b")],
            output_file,
        )
        assert result is None

    def test_skips_malformed_xml(self, tmp_path: Path) -> None:
        valid_content = """<?xml version="1.0"?>
<testsuite name="Valid" tests="1" failures="0" errors="0" skipped="0" time="1.0">
  <testcase name="test" classname="Valid" time="1.0"/>
</testsuite>"""

        malformed_content = """<?xml version="1.0"?>
<testsuite name="Invalid" tests="1"
  <testcase name="test"/>
</testsuite>"""

        valid_file = tmp_path / "valid.xml"
        valid_file.write_text(valid_content)

        malformed_file = tmp_path / "malformed.xml"
        malformed_file.write_text(malformed_content)

        output_file = tmp_path / "merged.xml"

        result = merge_xunit_files(
            [(valid_file, "valid"), (malformed_file, "malformed")],
            output_file,
        )

        assert result == output_file
        tree = ET.parse(output_file)
        root = tree.getroot()
        assert root.get("tests") == "1"
        assert len(root.findall("testsuite")) == 1


class TestCollectXunitFiles:
    def test_collects_robot_xunit(self, tmp_path: Path) -> None:
        robot_dir = tmp_path / "robot_results"
        robot_dir.mkdir()
        (robot_dir / XUNIT_XML).write_text("<testsuite/>")

        files = collect_xunit_files(tmp_path)

        assert len(files) == 1
        assert files[0] == (robot_dir / XUNIT_XML, "robot")

    def test_collects_pyats_api_xunit(self, tmp_path: Path) -> None:
        api_dir = tmp_path / "pyats_results" / "api"
        api_dir.mkdir(parents=True)
        (api_dir / XUNIT_XML).write_text("<testsuite/>")

        files = collect_xunit_files(tmp_path)

        assert len(files) == 1
        assert files[0] == (api_dir / XUNIT_XML, "pyats_api")

    def test_collects_pyats_d2d_xunit_per_device(self, tmp_path: Path) -> None:
        d2d_dir = tmp_path / "pyats_results" / "d2d"
        for device in ["router1", "router2"]:
            device_dir = d2d_dir / device
            device_dir.mkdir(parents=True)
            (device_dir / XUNIT_XML).write_text("<testsuite/>")

        files = collect_xunit_files(tmp_path)

        assert len(files) == 2
        paths = [f[0] for f in files]
        sources = [f[1] for f in files]

        assert d2d_dir / "router1" / XUNIT_XML in paths
        assert d2d_dir / "router2" / XUNIT_XML in paths
        assert "pyats_d2d/router1" in sources
        assert "pyats_d2d/router2" in sources

    def test_collects_all_xunit_sources(self, tmp_path: Path) -> None:
        (tmp_path / "robot_results").mkdir()
        (tmp_path / "robot_results" / XUNIT_XML).write_text("<testsuite/>")

        (tmp_path / "pyats_results" / "api").mkdir(parents=True)
        (tmp_path / "pyats_results" / "api" / XUNIT_XML).write_text("<testsuite/>")

        (tmp_path / "pyats_results" / "d2d" / "device1").mkdir(parents=True)
        (tmp_path / "pyats_results" / "d2d" / "device1" / XUNIT_XML).write_text(
            "<testsuite/>"
        )

        files = collect_xunit_files(tmp_path)

        assert len(files) == 3
        sources = [f[1] for f in files]
        assert "robot" in sources
        assert "pyats_api" in sources
        assert "pyats_d2d/device1" in sources

    def test_returns_empty_for_no_xunit_files(self, tmp_path: Path) -> None:
        files = collect_xunit_files(tmp_path)
        assert files == []


class TestMergeXunitResults:
    def test_merges_all_collected_files(self, tmp_path: Path) -> None:
        robot_dir = tmp_path / "robot_results"
        robot_dir.mkdir()
        (robot_dir / XUNIT_XML).write_text(
            """<?xml version="1.0"?>
<testsuite name="Robot" tests="2" failures="0" errors="0" skipped="0" time="1.0">
  <testcase name="test1" classname="Robot" time="0.5"/>
  <testcase name="test2" classname="Robot" time="0.5"/>
</testsuite>"""
        )

        api_dir = tmp_path / "pyats_results" / "api"
        api_dir.mkdir(parents=True)
        (api_dir / XUNIT_XML).write_text(
            """<?xml version="1.0"?>
<testsuite name="PyATS.API" tests="1" failures="1" errors="0" skipped="0" time="2.0">
  <testcase name="api_test" classname="PyATS.API" time="2.0">
    <failure message="failed"/>
  </testcase>
</testsuite>"""
        )

        result = merge_xunit_results(tmp_path)

        assert result is not None
        assert result == tmp_path / XUNIT_XML
        assert result.exists()

        tree = ET.parse(result)
        root = tree.getroot()
        assert root.get("tests") == "3"
        assert root.get("failures") == "1"

    def test_returns_none_for_empty_output_dir(self, tmp_path: Path) -> None:
        result = merge_xunit_results(tmp_path)
        assert result is None
        assert not (tmp_path / XUNIT_XML).exists()
