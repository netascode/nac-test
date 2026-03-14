# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Cleanup utilities for nac-test framework."""

import logging
import shutil
import time
from pathlib import Path

from nac_test.core.constants import (
    COMBINED_SUMMARY_FILENAME,
    LOG_HTML,
    OUTPUT_XML,
    PYATS_RESULTS_DIRNAME,
    REPORT_HTML,
    ROBOT_RESULTS_DIRNAME,
    XUNIT_XML,
)
from nac_test.pyats_core.discovery.test_type_resolver import VALID_TEST_TYPES

logger = logging.getLogger(__name__)

# Framework result directories removed upfront before each run so stale artifacts
# from previous runs don't persist. pyats_results/ is also removed by
# MultiArchiveReportGenerator during report generation; removing it here makes the
# timing explicit and avoids mid-run dependencies.
_RESULT_DIRS = (ROBOT_RESULTS_DIRNAME, PYATS_RESULTS_DIRNAME)

# Root-level files written (or linked) by a combined run.
# log.html/output.xml/report.html may be symlinks or hard links depending on the
# platform; Path.unlink() handles both correctly.
_ROOT_ARTIFACTS = (
    LOG_HTML,
    OUTPUT_XML,
    REPORT_HTML,
    XUNIT_XML,
    COMBINED_SUMMARY_FILENAME,
)


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


def cleanup_output_dir(output_dir: Path) -> None:
    """Clean up stale artifacts in the output directory before a test run.

    Removes three categories of stale content so that artifacts present after
    execution reliably reflect the current run:

    1. PyATS JSONL temp directories (api/, d2d/, default/) — stale *.jsonl files
       from interrupted runs cause incorrect report aggregation.
    2. Framework result directories (robot_results/, pyats_results/) — ensures no
       output files from a prior run are mixed with the current run's results.
    3. Root-level combined artifacts (log.html, xunit.xml, combined_summary.html,
       etc.) — prevents stale files surfacing in the terminal summary or HTML
       dashboard when a framework produces no results (e.g. filters match nothing).

    Archive files (nac_test_job_*.zip) are intentionally preserved — the
    ArchiveInspector always uses the newest archive per type.

    Args:
        output_dir: Base output directory for test results.
    """
    if not output_dir.exists():
        return

    # Remove all stale directories: PyATS JSONL temp dirs (api/, d2d/, default/) and
    # framework result dirs (robot_results/, pyats_results/).
    # "default" is a safety net for tests run outside orchestration (see base_test.py).
    dirs_to_remove = (*VALID_TEST_TYPES, "default", *_RESULT_DIRS)
    for dir_name in dirs_to_remove:
        dir_path = output_dir / dir_name
        if dir_path.exists():
            shutil.rmtree(dir_path, ignore_errors=True)
            if not dir_path.exists():
                if dir_name in _RESULT_DIRS:
                    logger.info(f"Removed stale directory: {dir_path.name}/")
                else:
                    logger.debug(f"Removed stale directory: {dir_path.name}/")
            else:
                logger.warning(f"Failed to remove stale directory: {dir_path.name}/")

    # Remove root-level artifacts (files and symlinks/hard links).
    # is_symlink() is checked first to catch broken symlinks that exist() misses.
    # Path.unlink() works for both regular files and symlinks/hard links.
    for filename in _ROOT_ARTIFACTS:
        path = output_dir / filename
        if path.is_symlink() or path.exists():
            try:
                path.unlink()
            except OSError as e:
                logger.warning(f"Failed to remove {path.name}: {e}")
            else:
                logger.debug(f"Removed stale artifact: {filename}")
