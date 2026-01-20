# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Archive extraction utilities for PyATS reporting.

This module handles extraction of PyATS archives and preservation of HTML reports
when updating archives.
"""

import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)


class ArchiveExtractor:
    """Handles extraction of PyATS archives for reporting purposes."""

    @staticmethod
    def extract_archive_to_directory(
        archive_path: Path, output_dir: Path, target_subdir: str = "pyats_results/api"
    ) -> Path | None:
        """Extract PyATS archive to a specific directory.

        This is a generic extraction method that works with our multi-archive architecture.
        It can extract API archives to pyats_results/api/ or SSH archives to pyats_results/d2d/.

        Args:
            archive_path: Path to the archive to extract
            output_dir: Base output directory
            target_subdir: Target subdirectory under output_dir (e.g., "pyats_results/api" or "pyats_results/d2d")

        Returns:
            Path to the extraction directory if successful, None otherwise
        """
        if not archive_path.exists():
            logger.error(f"Archive not found: {archive_path}")
            return None

        # Create extraction directory
        extract_dir = output_dir / target_subdir

        # If extraction directory already exists with HTML reports, update the previous archive
        if extract_dir.exists() and (extract_dir / "html_reports").exists():
            ArchiveExtractor.update_previous_archive_with_html_reports(
                extract_dir, current_archive=archive_path, output_dir=output_dir
            )

        extract_dir.mkdir(parents=True, exist_ok=True)

        # Clear previous results (but preserve directory structure)
        for item in extract_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

        # Extract archive
        try:
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
            logger.info(f"Extracted {archive_path} to {extract_dir}")
            return extract_dir
        except Exception as e:
            logger.error(f"Failed to extract {archive_path}: {e}")
            return None

    @staticmethod
    def update_previous_archive_with_html_reports(
        pyats_results_dir: Path, current_archive: Path, output_dir: Path
    ) -> None:
        """Update the most recent archive with HTML reports before overwriting.

        This preserves HTML reports by adding them to the previous archive before
        we extract a new one, ensuring reports are not lost.

        Args:
            pyats_results_dir: Directory containing current pyats results and HTML reports
            current_archive: The current archive being processed (to exclude from search)
            output_dir: Base output directory where archives are stored
        """
        # Find the most recent archive of the same type (excluding the current one)
        archive_pattern = (
            "nac_test_job_api_*.zip"
            if "_api_" in current_archive.name
            else "nac_test_job_d2d_*.zip"
        )
        archives = sorted(
            [
                f
                for f in output_dir.glob(archive_pattern)
                if f.name != current_archive.name
            ],
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )

        if not archives:
            return

        latest_archive = archives[0]
        logger.info(
            f"Updating previous archive {latest_archive.name} with HTML reports"
        )

        # Create a temporary directory for updating the archive
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Extract the existing archive
            with zipfile.ZipFile(latest_archive, "r") as zip_ref:
                zip_ref.extractall(temp_path)

            # Copy HTML reports into the extracted content
            html_reports_src = pyats_results_dir / "html_reports"
            if html_reports_src.exists():
                html_reports_dst = temp_path / "html_reports"
                if html_reports_dst.exists():
                    shutil.rmtree(html_reports_dst)
                shutil.copytree(html_reports_src, html_reports_dst)
                logger.info(f"Added HTML reports to {latest_archive.name}")

            # Re-create the archive with HTML reports included
            with zipfile.ZipFile(latest_archive, "w", zipfile.ZIP_DEFLATED) as zip_ref:
                for root, _dirs, files in os.walk(temp_path):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(temp_path)
                        zip_ref.write(file_path, arcname)
