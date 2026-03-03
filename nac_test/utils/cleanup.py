# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Cleanup utilities for nac-test framework."""

import logging
import shutil
import time
from pathlib import Path

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


def cleanup_old_test_outputs(output_dir: Path, days: int = 7) -> None:
    """Clean up old test output files in CI/CD.

    Args:
        output_dir: Directory containing test outputs.
        days: Remove files older than this many days.
    """
    if not output_dir.exists():
        return

    current_time = time.time()
    cutoff_time = current_time - (days * 24 * 3600)

    for file in output_dir.glob("*.jsonl"):
        try:
            if file.stat().st_mtime < cutoff_time:
                file.unlink()
                logger.debug(f"Removed old test output: {file.name}")
        except Exception:
            pass  # Best effort cleanup


def cleanup_stale_test_artifacts(output_dir: Path) -> None:
    """Clean up stale test artifacts that cause incorrect report aggregation.

    Targets ONLY the test type directories (api/, d2d/, default/) which contain
    html_report_data_temp/*.jsonl files from interrupted runs. These stale JSONL
    files get picked up during report generation and cause incorrect results.

    Does NOT remove:
        - Archive files (nac_test_job_*.zip): The orchestrator's ArchiveInspector
          uses only the newest archive per type, so old archives don't cause issues.
        - pyats_results/ directory: This is unconditionally removed and recreated
          during report generation (multi_archive_generator.py), so cleaning it
          here provides no benefit.

    Args:
        output_dir: Base output directory for test results.
    """
    if not output_dir.exists():
        return

    # Clean up test type directories (api/, d2d/, default/)
    # These contain html_report_data_temp/ with potentially stale JSONL files
    # from interrupted test runs (e.g., Ctrl+C)
    # "default" is a safety net for tests run outside orchestration (see base_test.py)
    dirs_to_clean = (*VALID_TEST_TYPES, "default")
    dirs_removed = 0

    for dir_name in dirs_to_clean:
        dir_path = output_dir / dir_name
        if dir_path.exists():
            try:
                shutil.rmtree(dir_path, ignore_errors=True)
                dirs_removed += 1
                logger.debug(f"Removed stale test directory: {dir_path}")
            except Exception as e:
                logger.warning(f"Failed to clean directory {dir_path}: {e}")

    if dirs_removed > 0:
        logger.info(
            f"Cleaned up {dirs_removed} stale test artifact director{'y' if dirs_removed == 1 else 'ies'}"
        )
