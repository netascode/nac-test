# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# -*- coding: utf-8 -*-

"""Cleanup utilities for nac-test framework."""

import logging
import shutil
import time
from pathlib import Path

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
