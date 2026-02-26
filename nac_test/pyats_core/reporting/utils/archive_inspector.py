# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Utility for inspecting PyATS archive contents without full extraction.

This module provides lightweight inspection of PyATS archives to display
their contents without the overhead of full extraction.
"""

import json
import logging
import zipfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ArchiveInspector:
    """Lightweight archive inspection without full extraction."""

    # Standard PyATS output files we care about
    PYATS_FILES = {
        "results_json": "results.json",
        "results_xml": "ResultsDetails.xml",
        "summary_xml": "ResultsSummary.xml",
        "report": ".report",  # Extension pattern
    }

    @staticmethod
    def inspect_archive(archive_path: Path) -> dict[str, str | None]:
        """Inspect a PyATS archive and return paths of key files.

        Args:
            archive_path: Path to the archive to inspect

        Returns:
            Dictionary mapping file types to their paths within the archive.
            Returns None for files that don't exist.
        """
        results: dict[str, str | None] = dict.fromkeys(ArchiveInspector.PYATS_FILES)

        try:
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                # Get all file names in the archive
                file_list = zip_ref.namelist()

                # Find each type of file
                for file_type, pattern in ArchiveInspector.PYATS_FILES.items():
                    for file_path in file_list:
                        file_name = Path(file_path).name

                        if file_type == "report":
                            # Special handling for .report files
                            if file_name.endswith(pattern):
                                results[file_type] = file_path
                                break
                        else:
                            # Exact match for other files
                            if file_name == pattern:
                                results[file_type] = file_path
                                break

        except Exception as e:
            logger.error(f"Failed to inspect archive {archive_path}: {e}")

        return results

    @staticmethod
    def get_archive_type(archive_path: Path) -> str:
        """Determine the type of archive from its filename.

        Args:
            archive_path: Path to the archive file

        Returns:
            Archive type: 'api', 'd2d', or 'legacy'
        """
        name = archive_path.name.lower()
        if "_api_" in name:
            return "api"
        elif "_d2d_" in name:
            return "d2d"
        else:
            return "legacy"

    @staticmethod
    def extract_test_results(archive_path: Path) -> dict[str, dict[str, Any]]:
        """Extract test results from a PyATS archive's results.json.

        This method parses the results.json file within a PyATS archive and returns
        a mapping of test names to their result information. It handles the PyATS
        result format and normalizes status values.

        Args:
            archive_path: Path to the PyATS archive zip file

        Returns:
            Dictionary mapping test names to result info containing:
                - status: Normalized status (passed/failed/errored/skipped/blocked)
                - duration: Test runtime in seconds
                - title: Test title (from section description or task name)
                - test_id: Fallback test ID (always 0 for archive-extracted results)

        Raises:
            zipfile.BadZipFile: If the archive is corrupted or invalid
            FileNotFoundError: If the archive path doesn't exist
        """
        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        results: dict[str, dict[str, Any]] = {}

        with zipfile.ZipFile(archive_path, "r") as zf:
            # Find results.json in the archive
            results_json_path = None
            for name in zf.namelist():
                if name.endswith("results.json"):
                    results_json_path = name
                    break

            if not results_json_path:
                logger.debug("No results.json found in archive")
                return results

            with zf.open(results_json_path) as f:
                results_data = json.load(f)

        # Parse tasks from results
        report = results_data.get("report", {})
        tasks = report.get("tasks", [])

        # Map PyATS result values to our status format
        status_map = {
            "passed": "passed",
            "failed": "failed",
            "errored": "errored",
            "skipped": "skipped",
            "blocked": "blocked",
        }

        for task in tasks:
            task_name = task.get("name", "")
            if not task_name:
                continue

            # Generate test name from testscript path to match plugin format.
            # The PyATS plugin uses the testscript path (e.g., "tests/nrfu/foo.py")
            # to generate test names like "nrfu.foo", but results.json only stores
            # the task name (e.g., "foo"). Using testscript ensures key consistency
            # between progress events and archive fallback.
            test_key = ArchiveInspector._derive_test_name_from_path(
                task.get("testscript", ""), task_name
            )

            # Extract result from results.json
            result_value = task.get("result", {}).get("value", "unknown")
            runtime = task.get("runtime", 0)

            # Normalize status
            status = status_map.get(result_value.lower(), result_value)

            # Get title from testcase description or task name
            title = task_name
            sections = task.get("sections", [])
            if sections:
                section_title = sections[0].get("description", task_name)
                if section_title:
                    title = section_title.strip().split("\n")[0]  # First line only

            results[test_key] = {
                "status": status,
                "duration": runtime,
                "title": title,
                "test_id": 0,  # Fallback ID for archive-extracted results
            }

            logger.debug(f"Extracted test result: {test_key} = {status}")

        return results

    @staticmethod
    def _derive_test_name_from_path(testscript: str, fallback_name: str) -> str:
        """Derive a test name from the testscript path.

        This mirrors the logic in the PyATS progress plugin's _get_test_name()
        method to ensure consistent key generation between progress events
        and archive-extracted results.

        Args:
            testscript: Full path to the test script file
            fallback_name: Fallback name if path cannot be parsed

        Returns:
            Dot-notation test name (e.g., "nrfu.verify_device_status")
        """
        if not testscript:
            return fallback_name

        try:
            path = Path(testscript)
            parts = path.parts

            # Find where 'tests' directory starts
            try:
                test_idx = parts.index("tests")
                relevant_parts = parts[test_idx + 1 :]
            except ValueError:
                # If no 'tests' dir, use the whole path
                relevant_parts = parts

            # Remove .py extension and join with dots
            name_parts = list(relevant_parts[:-1]) + [path.stem]
            return ".".join(name_parts)
        except Exception:
            return fallback_name

    @staticmethod
    def find_archives(output_dir: Path) -> dict[str, list[Path]]:
        """Find all PyATS archives in the output directory.

        Args:
            output_dir: Directory to search for archives

        Returns:
            Dictionary mapping archive types to lists of archive paths,
            sorted by modification time (newest first)
        """
        archives: dict[str, list[Path]] = {"api": [], "d2d": [], "legacy": []}

        # Find all archives
        all_archives = list(output_dir.glob("**/nac_test_job_*.zip"))

        # Categorize archives
        for archive in all_archives:
            archive_type = ArchiveInspector.get_archive_type(archive)
            archives[archive_type].append(archive)

        # Sort each category by modification time (newest first)
        for archive_type in archives:
            archives[archive_type].sort(key=lambda f: f.stat().st_mtime, reverse=True)

        return archives
