# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# -*- coding: utf-8 -*-

"""Archive aggregation utilities for PyATS device-centric testing.

This module handles aggregation of multiple device-specific archives into
a single consolidated archive for D2D (direct-to-device) test results.
"""

import logging
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class ArchiveAggregator:
    """Handles aggregation of multiple PyATS device archives."""

    @staticmethod
    async def aggregate_device_archives(
        device_archives: list[Path], output_dir: Path
    ) -> Path | None:
        """Aggregate multiple device-specific PyATS archives into a single D2D archive.

        This method takes individual device archives and combines them into a single
        archive with proper structure preservation. Each device's results are kept
        in separate subdirectories to maintain clarity.

        Args:
            device_archives: List of Path objects pointing to individual device archives
            output_dir: Directory where the aggregated archive will be created

        Returns:
            Path to the aggregated D2D archive, or None if aggregation fails
        """
        if not device_archives:
            logger.warning("No device archives to aggregate")
            return None

        logger.info(f"Aggregating {len(device_archives)} device archives")

        # Create timestamp for the aggregated archive
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        aggregated_archive_name = f"nac_test_job_d2d_{timestamp}.zip"
        aggregated_archive_path = output_dir / aggregated_archive_name

        # Create temporary directory for extraction
        temp_dir = output_dir / f"d2d_aggregate_temp_{timestamp}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Extract all device archives into subdirectories
            for idx, device_archive in enumerate(device_archives):
                if not device_archive.exists():
                    logger.warning(f"Device archive not found: {device_archive}")
                    continue

                # Extract device name from archive path if possible
                device_name = (
                    device_archive.stem.split("_")[-1]
                    if "_" in device_archive.stem
                    else f"device_{idx}"
                )
                device_dir = temp_dir / device_name
                device_dir.mkdir(exist_ok=True)

                try:
                    with zipfile.ZipFile(device_archive, "r") as zf:
                        zf.extractall(device_dir)
                    logger.debug(f"Extracted {device_archive} to {device_dir}")
                except Exception as e:
                    logger.error(f"Failed to extract {device_archive}: {e}")
                    continue

            # Create the aggregated archive
            with zipfile.ZipFile(
                aggregated_archive_path, "w", zipfile.ZIP_DEFLATED
            ) as zf:
                for root, _dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = Path(root) / file
                        # Calculate archive name relative to temp_dir
                        archive_name = str(file_path.relative_to(temp_dir))
                        zf.write(file_path, archive_name)

            logger.info(f"Created aggregated D2D archive: {aggregated_archive_path}")

            # Clean up individual device archives
            for device_archive in device_archives:
                try:
                    if device_archive.exists():
                        os.unlink(device_archive)
                except Exception as e:
                    logger.warning(
                        f"Failed to clean up device archive {device_archive}: {e}"
                    )

            return aggregated_archive_path

        except Exception as e:
            logger.error(f"Failed to create aggregated archive: {e}")
            return None

        finally:
            # Clean up temporary directory
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
