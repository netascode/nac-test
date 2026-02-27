# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Cleanup utilities for nac-test framework."""

import logging
import shutil
from pathlib import Path

from nac_test.core.constants import PYATS_RESULTS_DIRNAME
from nac_test.pyats_core.discovery.test_type_resolver import VALID_TEST_TYPES

logger = logging.getLogger(__name__)


def cleanup_pyats_runtime(workspace_path: Path | None = None) -> None:
    """Clean up PyATS runtime directories before test execution.

    Essential for CI/CD environments to prevent disk exhaustion.

    Args:
        workspace_path: Path to workspace directory. Defaults to current directory.
    """
    if workspace_path is None:
        workspace_path = Path.cwd()

    pyats_dir = workspace_path / ".pyats"

    if pyats_dir.exists():
        try:
            # Log size before cleanup for monitoring
            size_mb = sum(f.stat().st_size for f in pyats_dir.rglob("*")) / (
                1024 * 1024
            )
            logger.info(f"Cleaning PyATS runtime directory ({size_mb:.1f} MB)")

            # Remove entire .pyats directory
            shutil.rmtree(pyats_dir, ignore_errors=True)
            logger.info("PyATS runtime directory cleaned successfully")

        except Exception as e:
            logger.warning(f"Failed to clean PyATS directory: {e}")


def cleanup_pyats_output_dir(output_dir: Path) -> None:
    """Clean up PyATS output directory before starting tests.

    This removes stale artifacts from previous runs that could be picked up
    by the archive inspector when generating reports. Essential for scenarios
    where nac-test is interrupted (e.g., Ctrl+C) and restarted with the same
    output directory.

    Removes:
        - Old archive files (nac_test_job_*.zip) from output directory
        - The pyats_results/ subdirectory containing previous HTML reports
        - Stale JSONL result files from interrupted test runs

    Args:
        output_dir: Base output directory for test results.
    """
    if not output_dir.exists():
        return

    # Clean up old archive files that could be picked up by ArchiveInspector
    archive_pattern = "nac_test_job_*.zip"
    archives_removed = 0

    for archive in output_dir.glob(archive_pattern):
        try:
            archive.unlink()
            archives_removed += 1
            logger.debug(f"Removed stale archive: {archive.name}")
        except Exception as e:
            logger.warning(f"Failed to remove archive {archive.name}: {e}")

    if archives_removed > 0:
        logger.info(f"Cleaned up {archives_removed} stale PyATS archive(s)")

    # Clean up pyats_results and test type directories (api/, d2d/, default/)
    # "default" is a safety net for tests run outside orchestration (see base_test.py)
    dirs_to_clean = (PYATS_RESULTS_DIRNAME, *VALID_TEST_TYPES, "default")
    for dir_name in dirs_to_clean:
        dir_path = output_dir / dir_name
        if dir_path.exists():
            try:
                shutil.rmtree(dir_path, ignore_errors=True)
                logger.info(f"Cleaned up directory: {dir_path}")
            except Exception as e:
                logger.warning(f"Failed to clean directory {dir_path}: {e}")
