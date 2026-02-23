# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""XUnit XML merger for combining test results from multiple sources.

This module provides functionality to merge xunit.xml files from Robot Framework
and PyATS into a single consolidated file for CI/CD pipeline integration.

The merged file follows the standard JUnit XML format:
- Root element: <testsuites> (wrapper for multiple <testsuite> elements)
- Each source file's <testsuite> elements are preserved with their test cases
- Aggregate statistics are computed for the root <testsuites> element
"""

import logging
from dataclasses import dataclass
from pathlib import Path

# lxml.etree is 2-5x faster than stdlib xml.etree.ElementTree and already an indirect dependency
from lxml import etree as ET

from nac_test.core.constants import (
    PYATS_RESULTS_DIRNAME,
    ROBOT_RESULTS_DIRNAME,
    XUNIT_XML,
)

logger = logging.getLogger(__name__)


@dataclass
class XUnitStats:
    """Aggregate statistics for xunit test results."""

    tests: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    time: float = 0.0

    def add(self, other: "XUnitStats") -> None:
        """Add statistics from another XUnitStats instance."""
        self.tests += other.tests
        self.failures += other.failures
        self.errors += other.errors
        self.skipped += other.skipped
        self.time += other.time


def _parse_xunit_file(file_path: Path) -> tuple[list[ET.Element], XUnitStats]:
    """Parse an xunit.xml file and extract testsuite elements and statistics.

    Args:
        file_path: Path to the xunit.xml file.

    Returns:
        Tuple of (list of testsuite elements, aggregated statistics).

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ET.ParseError: If the XML is malformed.
    """
    tree = ET.parse(file_path)  # nosec B314 - parsing trusted internal xunit files
    root = tree.getroot()

    testsuites: list[ET.Element] = []
    stats = XUnitStats()

    # Handle both <testsuites> wrapper and direct <testsuite> root
    if root.tag == "testsuites":
        # Multiple testsuites wrapped in <testsuites>
        for testsuite in root.findall("testsuite"):
            testsuites.append(testsuite)
            stats.add(_extract_testsuite_stats(testsuite))
    elif root.tag == "testsuite":
        # Single testsuite as root
        testsuites.append(root)
        stats.add(_extract_testsuite_stats(root))
    else:
        # I feel an unexpected XML format shouldn't cause
        # the pipeline to fail, so only warn and skip this file
        logger.warning(f"Unexpected root element '{root.tag}' in {file_path}")

    return testsuites, stats


def _extract_testsuite_stats(testsuite: ET.Element) -> XUnitStats:
    """Extract statistics from a testsuite element.

    Args:
        testsuite: The testsuite XML element.

    Returns:
        XUnitStats with the testsuite's statistics.
    """
    return XUnitStats(
        tests=int(testsuite.get("tests", 0)),
        failures=int(testsuite.get("failures", 0)),
        errors=int(testsuite.get("errors", 0)),
        skipped=int(testsuite.get("skipped", 0)),
        time=float(testsuite.get("time", 0.0)),
    )


def _add_source_attribute(testsuite: ET.Element, source: str) -> None:
    """Add a source attribute to identify where the testsuite came from.

    Args:
        testsuite: The testsuite XML element.
        source: Source identifier (e.g., "robot", "pyats_api", "pyats_d2d").
    """
    # Preserve original name but add source for traceability
    original_name = testsuite.get("name", "unknown")
    testsuite.set("name", f"{source}: {original_name}")


def merge_xunit_files(
    xunit_files: list[tuple[Path, str]],
    output_path: Path,
) -> Path | None:
    """Merge multiple xunit.xml files into a single consolidated file.

    Args:
        xunit_files: List of tuples (file_path, source_identifier).
            source_identifier is used to prefix testsuite names for traceability
            (e.g., "robot", "pyats_api", "pyats_d2d/<device>").
        output_path: Path where the merged xunit.xml should be written.

    Returns:
        Path to the merged file if successful, None if no valid files to merge.

    Example:
        >>> merge_xunit_files([
        ...     (Path("robot_results/xunit.xml"), "robot"),
        ...     (Path("pyats_results/api/xunit.xml"), "pyats_api"),
        ...     (Path("pyats_results/d2d/device1/xunit.xml"), "pyats_d2d/device1"),
        ... ], Path("output/xunit.xml"))
    """
    all_testsuites: list[ET.Element] = []
    total_stats = XUnitStats()
    files_processed = 0

    for file_path, source in xunit_files:
        if not file_path.is_file():
            logger.debug(f"Skipping non-existent or non-file xunit path: {file_path}")
            continue

        try:
            testsuites, stats = _parse_xunit_file(file_path)
            for testsuite in testsuites:
                _add_source_attribute(testsuite, source)
                all_testsuites.append(testsuite)
            total_stats.add(stats)
            files_processed += 1
            logger.debug(
                f"Parsed {file_path}: {stats.tests} tests, "
                f"{stats.failures} failures, {stats.errors} errors"
            )
        except ET.ParseError as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            continue
        except ValueError as e:
            # Malformed xunit with non-numeric attribute values (e.g., tests="abc")
            logger.warning(f"Invalid attribute values in {file_path}: {e}")
            continue
        except OSError as e:
            logger.warning(f"Failed to read {file_path}: {type(e).__name__}: {e}")
            continue

    if not all_testsuites:
        logger.info("No valid xunit files to merge")
        return None

    # Create merged XML with <testsuites> wrapper
    root = ET.Element("testsuites")
    root.set("tests", str(total_stats.tests))
    root.set("failures", str(total_stats.failures))
    root.set("errors", str(total_stats.errors))
    root.set("skipped", str(total_stats.skipped))
    root.set("time", f"{total_stats.time:.3f}")

    for testsuite in all_testsuites:
        root.append(testsuite)

    # Write merged file
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")  # Pretty print

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output_path, encoding="UTF-8", xml_declaration=True)

    logger.info(
        f"Merged {files_processed} xunit files into {output_path}: "
        f"{total_stats.tests} tests, {total_stats.failures} failures, "
        f"{total_stats.errors} errors, {total_stats.skipped} skipped"
    )

    return output_path


def collect_xunit_files(output_dir: Path) -> list[tuple[Path, str]]:
    """Collect all xunit.xml files from the standard output directory structure.

    Searches for:
    - robot_results/xunit.xml (Robot Framework)
    - pyats_results/api/xunit.xml (PyATS API tests)
    - pyats_results/d2d/<device>/xunit.xml (PyATS D2D tests per device)

    Args:
        output_dir: The base output directory.

    Returns:
        List of tuples (file_path, source_identifier) for all found xunit files.
    """
    xunit_files: list[tuple[Path, str]] = []

    # Robot Framework xunit
    robot_xunit = output_dir / ROBOT_RESULTS_DIRNAME / XUNIT_XML
    if robot_xunit.is_file():
        xunit_files.append((robot_xunit, "robot"))
        logger.debug(f"Found Robot xunit: {robot_xunit}")

    # PyATS API xunit
    pyats_api_xunit = output_dir / PYATS_RESULTS_DIRNAME / "api" / XUNIT_XML
    if pyats_api_xunit.is_file():
        xunit_files.append((pyats_api_xunit, "pyats_api"))
        logger.debug(f"Found PyATS API xunit: {pyats_api_xunit}")

    # PyATS D2D xunit files (one per device)
    pyats_d2d_dir = output_dir / PYATS_RESULTS_DIRNAME / "d2d"
    if pyats_d2d_dir.is_dir():
        for device_dir in sorted(pyats_d2d_dir.iterdir()):
            if device_dir.is_dir():
                d2d_xunit = device_dir / XUNIT_XML
                if d2d_xunit.is_file():
                    device_name = device_dir.name
                    xunit_files.append((d2d_xunit, f"pyats_d2d/{device_name}"))
                    logger.debug(
                        f"Found PyATS D2D xunit for {device_name}: {d2d_xunit}"
                    )

    logger.info(f"Collected {len(xunit_files)} xunit files from {output_dir}")
    return xunit_files


def merge_xunit_results(output_dir: Path) -> Path | None:
    """Convenience function to collect and merge all xunit files in output directory.

    This is the main entry point for the xunit merger. It:
    1. Collects all xunit.xml files from standard locations
    2. Merges them into a single file at output_dir/xunit.xml

    Args:
        output_dir: The base output directory containing test results.

    Returns:
        Path to the merged xunit.xml file, or None if no files to merge.
    """
    xunit_files = collect_xunit_files(output_dir)
    if not xunit_files:
        logger.info("No xunit files found to merge")
        return None

    merged_path = output_dir / XUNIT_XML
    return merge_xunit_files(xunit_files, merged_path)
