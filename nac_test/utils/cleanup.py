# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Cleanup utilities for nac-test framework."""

import atexit
import logging
import shutil
import signal
import threading
import time
from pathlib import Path
from types import FrameType
from typing import Any

from nac_test.core.constants import DEBUG_MODE, IS_WINDOWS
from nac_test.pyats_core.discovery.test_type_resolver import VALID_TEST_TYPES

logger = logging.getLogger(__name__)


class CleanupManager:
    """Thread-safe manager for registering files to be cleaned up on exit.

    Ensures registered files are removed on:
    - Normal program exit (atexit)
    - SIGTERM signal (e.g., docker stop, kill)
    - SIGINT signal (Ctrl+C / KeyboardInterrupt)

    Note: SIGKILL cannot be caught - files may remain if process is killed with -9.

    Usage:
        cleanup_manager = CleanupManager()
        cleanup_manager.register(Path("/tmp/sensitive_file.yaml"))
        # File will be automatically removed on exit

        # Skip deletion when NAC_TEST_DEBUG is set (useful for debugging):
        cleanup_manager.register(Path("/tmp/temp_job.py"), keep_if_debug=True)

    Thread Safety:
        All operations are thread-safe via internal locking.

    Fork Safety:
        Not safe to use in forked child processes. If a process is forked
        while the singleton is initialised, the child inherits the lock in
        an undefined state. Subprocesses spawned via subprocess.Popen are
        unaffected (they get a fresh interpreter).
    """

    _instance: "CleanupManager | None" = None
    _instance_lock = threading.Lock()
    _initialized: bool = False

    def __new__(cls) -> "CleanupManager":
        """Singleton pattern - only one cleanup manager per process."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        """Initialize the cleanup manager (only runs once due to singleton)."""
        if self._initialized:
            return

        self._files: dict[Path, bool] = {}  # path → keep_if_debug
        self._lock = threading.RLock()
        self._original_sigterm: Any = None
        self._original_sigint: Any = None
        self._cleanup_done = False

        # Register atexit handler
        atexit.register(self.run_cleanup)

        # Install signal handlers (Unix only - Windows doesn't support SIGTERM properly)
        if not IS_WINDOWS:
            self._install_signal_handlers()

        self._initialized = True
        logger.debug("CleanupManager initialized")

    def _install_signal_handlers(self) -> None:
        """Install signal handlers for SIGTERM and SIGINT."""
        try:
            self._original_sigterm = signal.signal(signal.SIGTERM, self._signal_handler)
            self._original_sigint = signal.signal(signal.SIGINT, self._signal_handler)
            logger.debug("Signal handlers installed for SIGTERM and SIGINT")
        except (ValueError, OSError) as e:
            # Can fail if not in main thread or signal not supported
            logger.debug(f"Could not install signal handlers: {e}")

    def _signal_handler(self, signum: int, frame: FrameType | None) -> None:
        """Handle SIGTERM/SIGINT by cleaning up and re-raising."""
        sig_name = signal.Signals(signum).name
        logger.debug(f"Received {sig_name}, performing cleanup")

        # Perform cleanup
        self.run_cleanup()

        # Re-raise the signal with original handler or default behavior
        if signum == signal.SIGTERM:
            original = self._original_sigterm
        else:
            original = self._original_sigint

        # Restore original handler and re-raise
        signal.signal(signum, original if original is not None else signal.SIG_DFL)

        # For SIGINT, raise KeyboardInterrupt to allow normal exception handling
        if signum == signal.SIGINT:
            raise KeyboardInterrupt

        # For SIGTERM, re-send the signal
        signal.raise_signal(signum)

    def register(self, path: Path, keep_if_debug: bool = False) -> None:
        """Register a file path for cleanup on exit.

        If cleanup has already run (e.g. during shutdown), the file is
        deleted immediately instead of being queued — this prevents late
        registrations from being silently lost.

        Args:
            path: Path to file that should be removed on exit.
                  Directories are not supported (use shutil.rmtree directly).
            keep_if_debug: If True, the file will not be deleted when
                  NAC_TEST_DEBUG is set — useful for intermediate files
                  (job scripts, testbed YAMLs) that aid debugging.
        """
        with self._lock:
            # resolve() canonicalises symlinks (e.g. macOS /tmp → /private/tmp)
            # so registration and cleanup always refer to the same inode.
            resolved = path.resolve()

            if self._cleanup_done:
                # Cleanup already ran — delete immediately instead of
                # silently dropping the file.
                self._delete_file(resolved, keep_if_debug)
                return

            self._files[resolved] = keep_if_debug
            logger.debug(
                f"Registered for cleanup: {resolved} (keep_if_debug={keep_if_debug})"
            )

    def unregister(self, path: Path) -> None:
        """Unregister a file path from cleanup.

        Args:
            path: Path to file that should no longer be cleaned up.
        """
        with self._lock:
            resolved = path.resolve()
            self._files.pop(resolved, None)
            logger.debug(f"Unregistered from cleanup: {resolved}")

    def _delete_file(self, path: Path, keep_if_debug: bool) -> bool:
        """Delete a single file, respecting the keep_if_debug flag.

        Returns True if the file was kept for debugging, False otherwise.
        """
        if keep_if_debug and DEBUG_MODE:
            return True
        try:
            if path.exists():
                path.unlink()
                logger.debug(f"Cleaned up: {path}")
        except Exception as e:
            logger.warning(f"Failed to clean up {path}: {e}")
        return False

    def run_cleanup(self) -> None:
        """Delete all registered files. Safe to call multiple times.

        Called automatically on normal exit (atexit), SIGTERM, and SIGINT.
        Can also be called manually before an explicit exit.
        After the first call, registered files are cleared and subsequent
        calls are no-ops.  Files registered after cleanup has run are
        deleted immediately by ``register()`` instead.
        """
        with self._lock:
            if self._cleanup_done:
                return
            self._cleanup_done = True

            debug_kept: list[Path] = []
            for path, keep_if_debug in self._files.items():
                if self._delete_file(path, keep_if_debug):
                    debug_kept.append(path)

            if debug_kept:
                logger.info(
                    "Keeping %d file(s) for debugging (NAC_TEST_DEBUG is set): %s",
                    len(debug_kept),
                    ", ".join(str(p) for p in debug_kept),
                )

            self._files.clear()


def get_cleanup_manager() -> CleanupManager:
    """Get the singleton CleanupManager instance.

    Returns:
        The global CleanupManager instance.
    """
    return CleanupManager()


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
            shutil.rmtree(dir_path, ignore_errors=True)
            if not dir_path.exists():
                dirs_removed += 1
                logger.debug(f"Removed stale test directory: {dir_path}")
            else:
                logger.warning(f"Failed to remove stale directory: {dir_path}")

    if dirs_removed > 0:
        logger.info(
            f"Cleaned up {dirs_removed} stale test artifact director{'y' if dirs_removed == 1 else 'ies'}"
        )
