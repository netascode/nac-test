"""Utility for inspecting PyATS archive contents without full extraction.

This module provides lightweight inspection of PyATS archives to display
their contents without the overhead of full extraction.
"""

import zipfile
from pathlib import Path
from typing import Dict, List, Optional
import logging

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
    def inspect_archive(archive_path: Path) -> Dict[str, Optional[str]]:
        """Inspect a PyATS archive and return paths of key files.

        Args:
            archive_path: Path to the archive to inspect

        Returns:
            Dictionary mapping file types to their paths within the archive.
            Returns None for files that don't exist.
        """
        results: Dict[str, Optional[str]] = {
            key: None for key in ArchiveInspector.PYATS_FILES
        }

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
    def find_archives(output_dir: Path) -> Dict[str, List[Path]]:
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
