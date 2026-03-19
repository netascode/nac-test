#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""
PyATS to Robot Framework XML Converter

This module converts pyATS results.json files to Robot Framework output.xml format,
preserving test structure, timing, and log details for visualization in Robot's
reporting tools.

Usage:
    # As a module
    from pyats_to_robot_converter import PyATSToRobotConverter
    converter = PyATSToRobotConverter("/path/to/pyats_results")
    converter.convert_all()

    # As a standalone script
    python pyats_to_robot_converter.py /path/to/pyats_results
"""

import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from xml.dom import minidom


class PyATSToRobotConverter:
    """Converts pyATS results.json to Robot Framework output.xml format."""

    # Status mapping from pyATS to Robot Framework
    STATUS_MAP = {
        "passed": "PASS",
        "failed": "FAIL",
        "errored": "FAIL",
        "aborted": "FAIL",
        "blocked": "SKIP",
        "skipped": "SKIP",
        "passx": "PASS",
    }

    def __init__(self, results_dir: str):
        """
        Initialize the converter.

        Args:
            results_dir: Root directory containing pyATS results (can contain subdirectories)
        """
        self.results_dir = Path(results_dir)
        if not self.results_dir.exists():
            raise ValueError(f"Results directory does not exist: {results_dir}")

    def find_results_files(self) -> List[Path]:
        """
        Find all results.json files in the results directory and subdirectories.

        Returns:
            List of paths to results.json files
        """
        results_files = list(self.results_dir.rglob("results.json"))
        if not results_files:
            print(f"Warning: No results.json files found in {self.results_dir}")
        return results_files

    def convert_all(self) -> int:
        """
        Convert all results.json files found in the results directory.

        Returns:
            Number of files converted
        """
        results_files = self.find_results_files()
        converted_count = 0

        for results_file in results_files:
            try:
                print(f"Converting: {results_file}")
                self.convert_file(results_file)
                converted_count += 1
                print(f"  → Generated: {results_file.parent / 'output.xml'}")
            except Exception as e:
                print(f"  ✗ Error converting {results_file}: {e}", file=sys.stderr)
                import traceback

                traceback.print_exc()

        print(f"\nConverted {converted_count} of {len(results_files)} files")
        return converted_count

    def convert_file(self, results_json_path: Path) -> Path:
        """
        Convert a single results.json file to output.xml.

        Args:
            results_json_path: Path to results.json file

        Returns:
            Path to generated output.xml file
        """
        # Store the results directory for log file resolution
        self.current_results_dir = results_json_path.parent

        # Load results.json
        with open(results_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Create XML structure
        root = self._create_robot_root(data)

        # Add the main test suite
        self._add_suite(root, data["report"], parent_id="")

        # Add statistics
        self._add_statistics(root, data["report"])

        # Add errors section (empty for now)
        ET.SubElement(root, "errors")

        # Write to output.xml
        output_path = results_json_path.parent / "output.xml"
        self._write_pretty_xml(root, output_path)

        return output_path

    def _create_robot_root(self, data: Dict) -> ET.Element:
        """Create the root <robot> element with attributes."""
        report = data["report"]

        root = ET.Element("robot")
        root.set("generator", "PyATS-to-Robot Converter v1.0")
        root.set(
            "generated",
            self._convert_timestamp(report.get("stoptime", report.get("starttime"))),
        )
        root.set("rpa", "false")
        root.set("schemaversion", "5")

        return root

    def _add_suite(
        self, parent: ET.Element, suite_data: Dict, parent_id: str, index: int = 1
    ) -> ET.Element:
        """
        Add a test suite element to the XML tree.

        Args:
            parent: Parent XML element
            suite_data: PyATS suite/task data
            parent_id: Parent suite ID (for hierarchical ID generation)
            index: Suite index within parent

        Returns:
            Created suite element
        """
        # Generate suite ID
        if parent_id:
            suite_id = f"{parent_id}-s{index}"
        else:
            suite_id = f"s{index}"

        # Create suite element
        suite = ET.SubElement(parent, "suite")
        suite.set("id", suite_id)
        suite.set("name", suite_data.get("name", "Unknown Suite"))

        # Add source if available
        source = suite_data.get("testscript") or suite_data.get("jobfile")
        if source:
            suite.set("source", source)

        # Add suite documentation if description exists
        description = suite_data.get("description", "").strip()
        if description:
            doc = ET.SubElement(suite, "doc")
            doc.text = description

        # Handle different suite types
        suite_type = suite_data.get("type", "")

        if suite_type == "TestSuite":
            # Top-level job - contains tasks
            tasks = suite_data.get("tasks", [])
            for task_idx, task in enumerate(tasks, start=1):
                self._add_suite(suite, task, suite_id, task_idx)

        elif suite_type == "Task":
            # Task - contains testcases
            sections = suite_data.get("sections", [])
            for test_idx, testcase in enumerate(sections, start=1):
                if testcase.get("type") == "Testcase":
                    self._add_test(suite, testcase, suite_id, test_idx)

        # Add suite status
        self._add_status(suite, suite_data)

        return suite

    def _add_test(
        self, parent: ET.Element, testcase_data: Dict, parent_id: str, index: int
    ) -> ET.Element:
        """
        Add a test case element to the XML tree.

        Args:
            parent: Parent suite element
            testcase_data: PyATS testcase data
            parent_id: Parent suite ID
            index: Test index within suite

        Returns:
            Created test element
        """
        # Generate test ID
        test_id = f"{parent_id}-t{index}"

        # Create test element
        test = ET.SubElement(parent, "test")
        test.set("id", test_id)
        test.set("name", testcase_data.get("name", "Unknown Test"))

        # Add line number if available in xref
        xref = testcase_data.get("xref", {})
        if "line" in xref:
            test.set("line", str(xref["line"]))

        # Add test documentation
        description = testcase_data.get("description", "").strip()
        if description:
            doc = ET.SubElement(test, "doc")
            doc.text = description

        # Get the test's log file path for log extraction
        log_file_name = testcase_data.get("logs", {}).get("file")
        log_file_path = None
        if log_file_name:
            # Try to find the log file in the same directory as results.json
            log_file_path = self.current_results_dir / log_file_name
            if not log_file_path.exists():
                # Fallback: look in parent directory
                log_file_path = self.current_results_dir.parent / log_file_name
                if not log_file_path.exists():
                    log_file_path = None

        # Process sections: setup, test methods, cleanup
        sections = testcase_data.get("sections", [])
        for section in sections:
            section_type = section.get("type", "")

            if section_type == "SetupSection":
                self._add_keyword(
                    test, section, kw_type="SETUP", log_file_path=log_file_path
                )
            elif section_type == "TestSection":
                self._add_keyword(
                    test, section, kw_type="KEYWORD", log_file_path=log_file_path
                )
            elif section_type == "CleanupSection":
                self._add_keyword(
                    test, section, kw_type="TEARDOWN", log_file_path=log_file_path
                )

        # Add test status
        self._add_status(test, testcase_data)

        return test

    def _add_keyword(
        self,
        parent: ET.Element,
        section_data: Dict,
        kw_type: str = "KEYWORD",
        log_file_path: Optional[Path] = None,
    ) -> ET.Element:
        """
        Add a keyword element (represents a section or step).

        Args:
            parent: Parent test/keyword element
            section_data: PyATS section/step data
            kw_type: Keyword type (SETUP, KEYWORD, TEARDOWN)
            log_file_path: Path to log file for excerpt extraction

        Returns:
            Created keyword element
        """
        kw = ET.SubElement(parent, "kw")
        kw.set("name", section_data.get("name", section_data.get("id", "Unknown")))
        kw.set("type", kw_type)
        kw.set("owner", "PyATS")

        # Add keyword documentation
        description = section_data.get("description", "").strip()
        if description:
            doc = ET.SubElement(kw, "doc")
            doc.text = description

        # Extract and add log messages
        self._add_log_messages(kw, section_data, log_file_path)

        # Process nested steps if this is a TestSection
        nested_sections = section_data.get("sections", [])
        for nested_section in nested_sections:
            if nested_section.get("type") == "Step":
                self._add_keyword(
                    kw, nested_section, kw_type="KEYWORD", log_file_path=log_file_path
                )

        # Add keyword status
        self._add_status(kw, section_data)

        return kw

    def _add_log_messages(
        self, kw: ET.Element, section_data: Dict, log_file_path: Optional[Path]
    ) -> None:
        """
        Add log messages to a keyword element.

        Args:
            kw: Keyword element
            section_data: PyATS section/step data
            log_file_path: Path to log file for excerpt extraction
        """
        result = section_data.get("result", {})
        details = section_data.get("details", [])

        # Add start message
        start_time = section_data.get("starttime")
        if start_time:
            msg = ET.SubElement(kw, "msg")
            msg.set("time", self._convert_timestamp(start_time))
            msg.set("level", "INFO")
            msg.text = f"Starting: {section_data.get('name', 'step')}"

        # Extract log excerpt if available
        if log_file_path and log_file_path.exists():
            log_excerpt = self._extract_log_excerpt(
                log_file_path, section_data.get("logs", {})
            )
            if log_excerpt:
                msg = ET.SubElement(kw, "msg")
                msg.set(
                    "time", self._convert_timestamp(section_data.get("starttime", ""))
                )
                msg.set("level", "DEBUG")
                msg.text = log_excerpt

        # Add failure reason as a FAIL message
        reason = result.get("reason", "").strip()
        if reason:
            msg = ET.SubElement(kw, "msg")
            stop_time = section_data.get("stoptime", section_data.get("starttime"))
            msg.set("time", self._convert_timestamp(stop_time))
            msg.set("level", "FAIL")
            msg.text = reason

        # Add detail messages
        for detail in details:
            if detail and isinstance(detail, str):
                msg = ET.SubElement(kw, "msg")
                msg.set(
                    "time", self._convert_timestamp(section_data.get("stoptime", ""))
                )
                msg.set("level", "INFO" if result.get("value") == "passed" else "WARN")
                msg.text = detail.strip()

    def _extract_log_excerpt(
        self, log_file_path: Path, logs_info: Dict
    ) -> Optional[str]:
        """
        Extract a log excerpt from the task log file.

        Args:
            log_file_path: Path to the log file
            logs_info: Log metadata with 'begin' and 'size' byte offsets

        Returns:
            Extracted log text or None if not available
        """
        if not logs_info or "begin" not in logs_info or "size" not in logs_info:
            return None

        try:
            begin = logs_info["begin"]
            size = logs_info["size"]

            # Limit excerpt size to avoid huge messages
            max_size = 10000  # 10KB max
            if size > max_size:
                size = max_size

            with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(begin)
                excerpt = f.read(size)

                # Clean up the excerpt - remove excessive debug lines
                lines = excerpt.split("\n")
                filtered_lines = []
                for line in lines:
                    # Skip very verbose debug lines but keep important ones
                    if "%LOG-7-DEBUG" in line or "%UTILS-7-DEBUG" in line:
                        continue
                    if "%GIT-7-DEBUG" in line:
                        continue
                    filtered_lines.append(line)

                result = "\n".join(filtered_lines).strip()

                # Return only if we have meaningful content
                if len(result) > 50:  # Arbitrary minimum length
                    return result

        except Exception as e:
            print(f"Warning: Could not extract log excerpt: {e}", file=sys.stderr)

        return None

    def _add_status(self, element: ET.Element, data: Dict) -> ET.Element:
        """
        Add status element with timing information.

        Args:
            element: Parent element (suite/test/keyword)
            data: PyATS data containing result, starttime, stoptime, runtime

        Returns:
            Created status element
        """
        status = ET.SubElement(element, "status")

        # Map PyATS status to Robot status
        result = data.get("result", {})
        pyats_status = result.get("value", "unknown")
        robot_status = self.STATUS_MAP.get(pyats_status, "FAIL")
        status.set("status", robot_status)

        # Add timing information
        start_time = data.get("starttime")
        if start_time:
            status.set("start", self._convert_timestamp(start_time))

        # Calculate elapsed time in seconds
        runtime = data.get("runtime")
        if runtime is not None:
            # Robot expects elapsed time as string with decimal
            status.set("elapsed", f"{runtime:.6f}")

        # Add failure message as status text if failed
        if robot_status in ("FAIL", "SKIP"):
            reason = result.get("reason", "").strip()
            if reason:
                # Truncate very long messages
                if len(reason) > 500:
                    reason = reason[:497] + "..."
                status.text = reason

        return status

    def _add_statistics(self, root: ET.Element, report: Dict) -> ET.Element:
        """
        Add statistics section to the XML.

        Args:
            root: Root robot element
            report: PyATS report data

        Returns:
            Created statistics element
        """
        statistics = ET.SubElement(root, "statistics")

        # Total statistics
        total = ET.SubElement(statistics, "total")
        summary = report.get("summary", {})

        stat = ET.SubElement(total, "stat")
        stat.set("pass", str(summary.get("passed", 0)))
        stat.set(
            "fail",
            str(
                summary.get("failed", 0)
                + summary.get("errored", 0)
                + summary.get("aborted", 0)
            ),
        )
        stat.set("skip", str(summary.get("skipped", 0) + summary.get("blocked", 0)))
        stat.text = "All Tests"

        # Tag statistics (empty for now)
        ET.SubElement(statistics, "tag")

        # Suite statistics
        suite_stats = ET.SubElement(statistics, "suite")
        self._add_suite_stats(suite_stats, report, "")

        return statistics

    def _add_suite_stats(
        self, parent: ET.Element, suite_data: Dict, parent_id: str, index: int = 1
    ) -> None:
        """
        Recursively add suite statistics.

        Args:
            parent: Parent statistics element
            suite_data: PyATS suite/task data
            parent_id: Parent suite ID
            index: Suite index
        """
        # Generate suite ID
        if parent_id:
            suite_id = f"{parent_id}-s{index}"
        else:
            suite_id = f"s{index}"

        summary = suite_data.get("summary", {})
        stat = ET.SubElement(parent, "stat")
        stat.set("name", suite_data.get("name", "Unknown"))
        stat.set("id", suite_id)
        stat.set("pass", str(summary.get("passed", 0)))
        stat.set(
            "fail",
            str(
                summary.get("failed", 0)
                + summary.get("errored", 0)
                + summary.get("aborted", 0)
            ),
        )
        stat.set("skip", str(summary.get("skipped", 0) + summary.get("blocked", 0)))
        stat.text = suite_data.get("name", "Unknown")

        # Add child suite stats for tasks
        if suite_data.get("type") == "TestSuite":
            tasks = suite_data.get("tasks", [])
            for task_idx, task in enumerate(tasks, start=1):
                self._add_suite_stats(parent, task, suite_id, task_idx)

    def _convert_timestamp(self, timestamp: str) -> str:
        """
        Convert PyATS timestamp to Robot Framework format.

        PyATS format: "2026-01-26 12:31:37.586710+01:00"
        Robot format: "2026-01-26T12:31:37.586710"

        Args:
            timestamp: PyATS timestamp string

        Returns:
            Robot-formatted timestamp string
        """
        if not timestamp:
            return ""

        try:
            # Parse the timestamp (handles timezone)
            if "+" in timestamp or timestamp.endswith("Z"):
                # Has timezone - parse and convert
                dt = datetime.fromisoformat(timestamp)
            else:
                # No timezone - parse directly
                dt = datetime.fromisoformat(timestamp)

            # Format without timezone in Robot format
            return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")
        except Exception as e:
            print(
                f"Warning: Could not parse timestamp '{timestamp}': {e}",
                file=sys.stderr,
            )
            # Fallback: simple string replacement
            return (
                timestamp.replace(" ", "T").split("+")[0].split("-", 3)[-1]
                if "+" in timestamp
                else timestamp.replace(" ", "T")
            )

    def _write_pretty_xml(self, root: ET.Element, output_path: Path) -> None:
        """
        Write XML to file with pretty formatting.

        Args:
            root: Root XML element
            output_path: Path to output file
        """
        # Convert to string
        xml_str = ET.tostring(root, encoding="unicode")

        # Pretty print
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="  ", encoding="UTF-8")

        # Write to file
        with open(output_path, "wb") as f:
            f.write(pretty_xml)


def main():
    """Main entry point for standalone execution."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert PyATS results.json files to Robot Framework output.xml format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert all results in a directory
  %(prog)s /path/to/pyats_results

  # Convert results in multiple directories
  %(prog)s /path/to/results1 /path/to/results2

  # Convert with verbose output
  %(prog)s -v /path/to/pyats_results
        """,
    )

    parser.add_argument(
        "results_dirs",
        nargs="+",
        help="Directory/directories containing PyATS results.json files",
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    total_converted = 0
    total_files = 0

    for results_dir in args.results_dirs:
        print(f"\n{'=' * 60}")
        print(f"Processing: {results_dir}")
        print(f"{'=' * 60}")

        try:
            converter = PyATSToRobotConverter(results_dir)
            converted = converter.convert_all()
            total_converted += converted
            total_files += len(converter.find_results_files())
        except Exception as e:
            print(f"Error processing {results_dir}: {e}", file=sys.stderr)
            if args.verbose:
                import traceback

                traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"Summary: Converted {total_converted} of {total_files} total files")
    print(f"{'=' * 60}")

    return 0 if total_converted == total_files else 1


if __name__ == "__main__":
    sys.exit(main())
