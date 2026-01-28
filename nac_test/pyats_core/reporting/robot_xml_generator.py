# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Robot Framework XML generator for nac-test PyATS framework.

This module generates Robot Framework output.xml files from JSONL test results,
enabling use of Robot's standard reporting tools (rebot) instead of custom HTML.

Usage:
    generator = RobotXMLGenerator(output_dir, pyats_results_dir)
    await generator.generate_robot_xml()
"""

import json
import logging
import xml.etree.ElementTree as ET  # nosec B405 - We generate XML, not parse untrusted input
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from xml.dom import minidom  # nosec B408 - We generate XML, not parse untrusted input

import aiofiles  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class RobotXMLGenerator:
    """Generates Robot Framework output.xml from JSONL test results.

    This class reads JSONL files produced by TestResultCollector during test
    execution and converts them to Robot Framework's standard output.xml format.
    The resulting XML can be processed with 'rebot' to generate log.html and
    report.html files.

    Attributes:
        output_dir: Base output directory containing test results
        pyats_results_dir: Directory where PyATS results are extracted
        test_counter: Counter for generating unique test IDs
        failed_conversions: List of test IDs that failed to convert
    """

    # Status mapping from nac-test to Robot Framework
    STATUS_MAP = {
        "passed": "PASS",
        "failed": "FAIL",
        "errored": "FAIL",
        "aborted": "FAIL",
        "blocked": "SKIP",
        "skipped": "SKIP",
        "info": "PASS",
    }

    def __init__(
        self,
        output_dir: Path,
        pyats_results_dir: Path,
        truncator: Callable[[str], str] | None = None,
    ) -> None:
        """Initialize the Robot XML generator.

        Args:
            output_dir: Base output directory containing test results
            pyats_results_dir: Directory where PyATS results are extracted
            truncator: Optional truncation function for command outputs
        """
        self.output_dir = output_dir
        self.pyats_results_dir = pyats_results_dir
        self.report_dir = pyats_results_dir / "html_reports"
        self.html_report_data_dir = self.report_dir / "html_report_data"
        self.temp_data_dir = output_dir / "html_report_data_temp"
        self.test_counter = 0
        self.failed_conversions: list[str] = []
        self.truncator = truncator

    async def generate_robot_xml(
        self, result_files: list[Path] | None = None
    ) -> dict[str, Any]:
        """Generate Robot Framework output.xml from all JSONL files.

        This is the main entry point. It finds all JSONL test result files,
        converts them to Robot XML format, and writes output.xml.

        Args:
            result_files: Optional list of JSONL files to process. If None, will glob for files.

        Returns:
            Dictionary containing:
                - status: "success" or "no_results"
                - duration: Total generation time in seconds
                - total_tests: Number of test results found
                - successful_conversions: Number of successfully converted tests
                - failed_conversions: Number of failed conversions
                - output_file: Path to generated output.xml
        """
        start_time = datetime.now()

        # Use provided result_files or discover them
        if result_files is None:
            # JSONL files have already been moved by ReportGenerator
            # Just read them from the final location
            result_files = list(self.html_report_data_dir.glob("*.jsonl"))

        if not result_files:
            logger.warning("No test results found to generate Robot XML")
            return {"status": "no_results", "duration": 0}

        logger.info(f"Found {len(result_files)} test results to convert to Robot XML")

        # Create root Robot XML structure
        root = self._create_robot_root()

        # Create top-level suite with consistent name for merging
        # Note: All archives must have the same root suite name to be merged by rebot
        suite = ET.SubElement(root, "suite")
        suite.set("id", "s1")
        suite.set("name", "pyATS Test Execution")
        suite.set("source", str(self.pyats_results_dir))

        # Convert each JSONL file to a test
        suite_start = None
        suite_end = None

        for result_file in sorted(result_files):
            try:
                test_data = await self._read_jsonl_results(result_file)
                self._add_test_to_suite(suite, test_data)

                # Track suite timing
                if suite_start is None or test_data["start_time"] < suite_start:
                    suite_start = test_data["start_time"]
                if (
                    suite_end is None
                    or test_data.get("end_time", test_data["start_time"]) > suite_end
                ):
                    suite_end = test_data.get("end_time", test_data["start_time"])

            except Exception as e:
                logger.error(f"Failed to convert {result_file}: {e}")
                self.failed_conversions.append(result_file.stem)
                continue

        # Add suite status
        if suite_start and suite_end:
            suite_duration = (
                datetime.fromisoformat(suite_end) - datetime.fromisoformat(suite_start)
            ).total_seconds()
        else:
            suite_duration = 0

        suite_status = ET.SubElement(suite, "status")
        # Determine suite status based on test results
        has_failure = any(
            test.find("status").get("status") == "FAIL"  # type: ignore[union-attr]
            for test in suite.findall("test")
            if test.find("status") is not None
        )
        suite_status.set("status", "FAIL" if has_failure else "PASS")
        if suite_start:
            suite_status.set("start", self._format_robot_timestamp(suite_start))
        suite_status.set("elapsed", str(suite_duration))

        # Add statistics
        self._add_statistics(root, suite)

        # Add errors section (required by Robot schema)
        ET.SubElement(root, "errors")

        # Write output.xml
        output_path = self.pyats_results_dir / "output.xml"
        self._write_pretty_xml(root, output_path)

        logger.info(f"Generated Robot Framework XML: {output_path}")

        # Note: JSONL cleanup is handled by ReportGenerator.cleanup_jsonl_files()
        # after all generators have finished

        duration = (datetime.now() - start_time).total_seconds()

        return {
            "status": "success",
            "duration": duration,
            "total_tests": len(result_files),
            "successful_conversions": len(result_files) - len(self.failed_conversions),
            "failed_conversions": len(self.failed_conversions),
            "output_file": str(output_path),
        }

    def assemble_xml_from_elements(
        self, test_elements: list[ET.Element], result_files: list[Path]
    ) -> dict[str, Any]:
        """Assemble final Robot XML from pre-generated test elements.

        This is the fast, sequential assembly step after parallel test element
        generation. It combines independent test elements into a suite and writes
        the final output.xml file.

        Args:
            test_elements: List of pre-generated <test> Elements
            result_files: Original result file paths (for metadata)

        Returns:
            Robot XML generation result dict
        """
        start_time = datetime.now()

        if not test_elements:
            logger.warning("No test elements to assemble")
            return {"status": "no_results", "duration": 0}

        logger.info(f"Assembling Robot XML from {len(test_elements)} test elements")

        # Create root and suite
        root = self._create_robot_root()
        suite = ET.SubElement(root, "suite")
        suite.set("id", "s1")
        suite.set("name", "pyATS Test Execution")
        suite.set("source", str(self.pyats_results_dir))

        # Add all test elements to suite
        for test_elem in test_elements:
            suite.append(test_elem)

        # Calculate suite timing from test elements
        suite_start = None
        suite_end = None
        for test_elem in test_elements:
            status_elem = test_elem.find("status")
            if status_elem is not None:
                test_start = status_elem.get("start")
                if test_start is None:
                    continue

                # Calculate end time from start + elapsed
                elapsed_str = status_elem.get("elapsed", "0")
                try:
                    elapsed = float(elapsed_str)
                    test_start_dt = datetime.fromisoformat(
                        test_start.replace("T", " ").replace(".", " ").split()[0]
                        + "T"
                        + test_start.split("T")[1]
                    )
                    test_end_dt = test_start_dt + timedelta(seconds=elapsed)
                    test_end = test_end_dt.isoformat()

                    if suite_start is None or test_start < suite_start:
                        suite_start = test_start
                    if suite_end is None or test_end > suite_end:
                        suite_end = test_end
                except (ValueError, AttributeError, IndexError):
                    pass

        # Add suite status
        if suite_start and suite_end:
            try:
                start_dt = datetime.fromisoformat(
                    suite_start.replace("T", " ", 1).split(".")[0]
                )
                end_dt = datetime.fromisoformat(
                    suite_end.replace("T", " ", 1).split(".")[0]
                )
                suite_duration = (end_dt - start_dt).total_seconds()
            except (ValueError, AttributeError):
                suite_duration = 0
        else:
            suite_duration = 0

        suite_status = ET.SubElement(suite, "status")
        # Determine suite status based on test results
        has_failure = any(
            test.find("status").get("status") == "FAIL"  # type: ignore[union-attr]
            for test in test_elements
            if test.find("status") is not None
        )
        suite_status.set("status", "FAIL" if has_failure else "PASS")
        if suite_start:
            suite_status.set("start", suite_start)
        suite_status.set("elapsed", str(suite_duration))

        # Add statistics
        self._add_statistics(root, suite)

        # Add errors section (required by Robot schema)
        ET.SubElement(root, "errors")

        # Write output.xml
        output_path = self.pyats_results_dir / "output.xml"
        self._write_pretty_xml(root, output_path)

        logger.info(f"Generated Robot Framework XML: {output_path}")

        duration = (datetime.now() - start_time).total_seconds()

        return {
            "status": "success",
            "duration": duration,
            "total_tests": len(test_elements),
            "successful_conversions": len(test_elements),
            "failed_conversions": 0,
            "output_file": str(output_path),
        }

    def _add_test_to_suite(self, suite: ET.Element, test_data: dict[str, Any]) -> None:
        """Convert test data from JSONL to Robot <test> element and add to suite.

        Deprecated: Use _create_test_element() for parallel processing.
        This method is kept for backward compatibility.

        Args:
            suite: Parent suite element
            test_data: Test data from JSONL
        """
        test_elem = self._create_test_element(test_data)
        suite.append(test_elem)

    def _create_robot_root(self) -> ET.Element:
        """Create the root <robot> element with required attributes.

        Returns:
            Root XML element
        """
        root = ET.Element("robot")
        root.set("generator", "nac-test Robot XML Generator v1.0")
        root.set("generated", datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3])
        root.set("rpa", "false")
        root.set("schemaversion", "5")
        return root

    async def _read_jsonl_results(self, jsonl_path: Path) -> dict[str, Any]:
        """Read JSONL file and reconstruct test data structure.

        Args:
            jsonl_path: Path to JSONL file

        Returns:
            Dictionary with test data
        """
        results = []
        command_executions = []
        metadata = {}
        summary = {}

        try:
            async with aiofiles.open(jsonl_path) as f:
                async for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        record = json.loads(line)
                        record_type = record.get("type")

                        if record_type == "metadata":
                            metadata = record
                        elif record_type == "result":
                            results.append(record)
                        elif record_type == "command_execution":
                            command_executions.append(record)
                        elif record_type == "summary":
                            summary = record
                        elif record_type == "emergency_close":
                            logger.debug(f"Found emergency close in {jsonl_path}")

                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Skipping malformed JSONL line in {jsonl_path}: {e}"
                        )
                        continue

        except Exception as e:
            logger.error(f"Failed to read JSONL file {jsonl_path}: {e}")
            raise

        return {
            "test_id": metadata.get("test_id") or summary.get("test_id"),
            "start_time": metadata.get("start_time") or summary.get("start_time"),
            "end_time": summary.get("end_time"),
            "duration": summary.get("duration"),
            "results": results,
            "command_executions": command_executions,
            "overall_status": summary.get("overall_status"),
            "metadata": summary.get("metadata", {}),
        }

    def _create_test_element(self, test_data: dict[str, Any]) -> ET.Element:
        """Create an independent Robot <test> element from test data.

        Returns a complete test element that can be added to any suite.
        Does NOT mutate any shared state - enables parallel processing.

        Args:
            test_data: Test data from JSONL

        Returns:
            Complete test Element ready to be added to a suite
        """
        self.test_counter += 1

        # Create test element (independent, not attached to suite yet)
        test = ET.Element("test")
        test.set("id", f"s1-t{self.test_counter}")
        test.set("name", test_data["metadata"].get("title", test_data["test_id"]))

        # Add documentation (combine metadata - HTML is allowed in Robot doc)
        doc_text = self._build_documentation(test_data["metadata"])
        if doc_text:
            doc = ET.SubElement(test, "doc")
            doc.text = doc_text

        # Group results and commands by test_context
        keyword_groups = self._group_by_context(
            test_data["results"], test_data["command_executions"]
        )

        # Create keywords for each context group
        for context_name, items in keyword_groups.items():
            self._add_keyword(test, context_name, items)

        # Collect status messages from results (primarily for failed/errored tests)
        status_messages = []
        for result in test_data["results"]:
            msg = result.get("message", "")
            if msg:
                status_messages.append(msg)

        # Add test status
        status = ET.SubElement(test, "status")
        status.set("status", self.STATUS_MAP.get(test_data["overall_status"], "FAIL"))
        if test_data["start_time"]:
            status.set("start", self._format_robot_timestamp(test_data["start_time"]))
        if test_data["duration"]:
            status.set("elapsed", str(test_data["duration"]))

        # Add status messages as text content
        if status_messages:
            status.text = "\n\n".join(status_messages)

        return test

    def _build_documentation(self, metadata: dict[str, str]) -> str:
        """Build documentation text from metadata.

        Uses Robot Framework formatted text which has already been converted
        from markdown with proper lists, bold, code formatting, etc.

        Args:
            metadata: Metadata dictionary with robot-formatted text fields

        Returns:
            Combined documentation text in Robot Framework format
        """
        parts = []

        # Add description (use Robot Framework formatted text)
        if metadata.get("description_robot"):
            parts.append(metadata["description_robot"])

        # Add setup info with Robot Framework section heading
        if metadata.get("setup_robot"):
            parts.append("\n\n== Setup ==\n\n" + metadata["setup_robot"])

        # Add procedure with Robot Framework section heading
        if metadata.get("procedure_robot"):
            parts.append("\n\n== Procedure ==\n\n" + metadata["procedure_robot"])

        # Add criteria with Robot Framework section heading
        if metadata.get("criteria_robot"):
            parts.append(
                "\n\n== Pass/Fail Criteria ==\n\n" + metadata["criteria_robot"]
            )

        return "\n".join(parts)

    def _group_by_context(
        self, results: list[dict[str, Any]], command_executions: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Group results and commands by test_context for keyword organization.

        Args:
            results: List of result records
            command_executions: List of command execution records

        Returns:
            Dictionary mapping context name to list of items
        """
        groups: dict[str, list[dict[str, Any]]] = {}

        # Combine results and commands, preserving order by timestamp
        all_items = []
        for result in results:
            all_items.append({**result, "item_type": "result"})
        for cmd in command_executions:
            all_items.append({**cmd, "item_type": "command"})

        # Sort by timestamp
        all_items.sort(key=lambda x: x.get("timestamp", ""))

        # Group by context (use "Test Execution" as default)
        for item in all_items:
            context = (
                item.get("test_context") or item.get("context") or "Test Execution"
            )
            if context not in groups:
                groups[context] = []
            groups[context].append(item)

        # If no groups created, create default
        if not groups:
            groups["Test Execution"] = all_items

        return groups

    def _add_keyword(
        self, test: ET.Element, context_name: str, items: list[dict[str, Any]]
    ) -> None:
        """Add a keyword element with messages for a context group.

        Args:
            test: Parent test element
            context_name: Name for this keyword (context string)
            items: List of result/command items for this context
        """
        kw = ET.SubElement(test, "kw")
        kw.set("name", context_name)
        kw.set("type", "KEYWORD")

        # Track keyword timing and status
        kw_start = None
        kw_end = None
        kw_has_failure = False

        for item in items:
            timestamp = item.get("timestamp", "")

            if item["item_type"] == "result":
                # Track failure status (but don't add message - that goes in test status)
                result_status = item.get("status", "info")
                if result_status in ["failed", "errored"]:
                    kw_has_failure = True

            elif item["item_type"] == "command":
                # Add command execution as message
                msg = ET.SubElement(kw, "msg")
                msg.set("time", self._format_robot_timestamp(timestamp))
                msg.set("level", "INFO")

                # Format command execution message
                device = item.get("device_name", "unknown")
                command = item.get("command", "")
                output = item.get("output", "")

                # Apply truncation if available
                if self.truncator:
                    output = self.truncator(output)

                msg_text = f"Device: {device}\nCommand: {command}\n\n{output}"
                msg.text = msg_text

            # Track timing
            if timestamp:
                if kw_start is None or timestamp < kw_start:
                    kw_start = timestamp
                if kw_end is None or timestamp > kw_end:
                    kw_end = timestamp

        # Add keyword status
        status = ET.SubElement(kw, "status")
        status.set("status", "FAIL" if kw_has_failure else "PASS")
        if kw_start:
            status.set("start", self._format_robot_timestamp(kw_start))
        if kw_start and kw_end:
            try:
                elapsed = (
                    datetime.fromisoformat(kw_end) - datetime.fromisoformat(kw_start)
                ).total_seconds()
                status.set("elapsed", str(elapsed))
            except ValueError:
                status.set("elapsed", "0")

    def _status_to_log_level(self, status: str) -> str:
        """Map result status to Robot log level.

        Args:
            status: Status string from result record

        Returns:
            Robot log level (INFO, FAIL, WARN)
        """
        if status in ["failed", "errored"]:
            return "FAIL"
        elif status == "skipped":
            return "WARN"
        else:
            return "INFO"

    def _format_robot_timestamp(self, timestamp: str) -> str:
        """Convert ISO timestamp to Robot Framework format.

        Args:
            timestamp: ISO format timestamp

        Returns:
            Robot-compatible timestamp (YYYY-MM-DDTHH:MM:SS.mmm)
        """
        try:
            dt = datetime.fromisoformat(timestamp)
            return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        except (ValueError, AttributeError):
            return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

    def _add_statistics(self, root: ET.Element, suite: ET.Element) -> None:
        """Add statistics section to Robot XML.

        Args:
            root: Root robot element
            suite: Suite element containing tests
        """
        statistics = ET.SubElement(root, "statistics")

        # Count test results
        tests = suite.findall("test")
        passed = len(
            [
                t
                for t in tests
                if t.find("status") is not None
                and t.find("status").get("status") == "PASS"  # type: ignore[union-attr]
            ]
        )
        failed = len(
            [
                t
                for t in tests
                if t.find("status") is not None
                and t.find("status").get("status") == "FAIL"  # type: ignore[union-attr]
            ]
        )
        skipped = len(
            [
                t
                for t in tests
                if t.find("status") is not None
                and t.find("status").get("status") == "SKIP"  # type: ignore[union-attr]
            ]
        )

        # Total statistics
        total = ET.SubElement(statistics, "total")
        stat = ET.SubElement(total, "stat")
        stat.set("pass", str(passed))
        stat.set("fail", str(failed))
        stat.set("skip", str(skipped))
        stat.text = "All Tests"

        # Tag statistics (empty for now)
        ET.SubElement(statistics, "tag")

        # Suite statistics
        suite_stats = ET.SubElement(statistics, "suite")
        stat = ET.SubElement(suite_stats, "stat")
        stat.set("pass", str(passed))
        stat.set("fail", str(failed))
        stat.set("skip", str(skipped))
        stat.set("id", "s1")
        stat.set("name", "NAC Test Execution")
        stat.text = "NAC Test Execution"

    def _write_pretty_xml(self, root: ET.Element, output_path: Path) -> None:
        """Write XML to file with pretty formatting.

        Args:
            root: Root XML element
            output_path: Path to write XML file
        """
        # Convert to string
        xml_string = ET.tostring(root, encoding="unicode")

        # Pretty print - nosec B318: We're formatting our own generated XML, not parsing untrusted input
        dom = minidom.parseString(xml_string)  # nosec B318
        pretty_xml = dom.toprettyxml(indent="  ", encoding="UTF-8")

        # Write to file
        with open(output_path, "wb") as f:
            f.write(pretty_xml)
