# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Progress reporting for PyATS test execution."""

import logging
import threading
import time
from datetime import datetime
from typing import Any

from nac_test.utils.terminal import terminal

logger = logging.getLogger(__name__)


class ProgressReporter:
    """Reports PyATS test progress in a format matching Robot Framework output."""

    def __init__(self, total_tests: int = 0, max_workers: int = 1):
        self.start_time = time.time()
        self.total_tests = total_tests
        self.max_workers = max_workers
        self.test_status: dict[str, dict[str, Any]] = {}
        self.test_counter = 0  # Global test ID counter
        self.current_test_id = 0
        self.lock = threading.Lock()

    def report_test_start(
        self, test_name: str, pid: int, worker_id: str, test_id: int
    ) -> None:
        """Report that a test has started executing"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Use terminal utilities for consistent coloring
        status_text = terminal.warning("EXECUTING")

        print(
            f"{timestamp} [PID:{pid}] [{worker_id}] [ID:{test_id}] "
            f"{status_text} {test_name}"
        )

        # Track test start in test_status
        self.test_status[test_name] = {
            "start_time": time.time(),
            "status": "EXECUTING",
            "worker_id": worker_id,
            "test_id": test_id,
        }

    def report_test_end(
        self,
        test_name: str,
        pid: int,
        worker_id: int,
        test_id: int,
        status: str,
        duration: float,
    ) -> None:
        """Format: 2025-06-27 18:26:16.834346 [PID:893270] [4] [ID:4] PASSED ... in 3.2 seconds"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Update test status with duration
        if test_name in self.test_status:
            self.test_status[test_name].update({"status": status, "duration": duration})

        # Color based on status using terminal utilities
        # PyATS statuses: 'passed', 'failed', 'skipped', 'errored', 'aborted', 'blocked'
        if status == "PASSED" or status == "passed":
            status_text = terminal.success(status.upper())
        elif status == "FAILED" or status == "failed":
            # FAILED = test assertions failed (show in red, but not as "ERROR")
            status_text = terminal.error(status.upper())
        elif status == "ERRORED" or status == "errored":
            # ERRORED = exception/setup issue (show as "ERROR" in red)
            status_text = terminal.error("ERROR")
        elif status == "SKIPPED" or status == "skipped":
            status_text = terminal.warning(status.upper())
        elif status == "ABORTED" or status == "aborted":
            status_text = terminal.error("ABORTED")
        elif status == "BLOCKED" or status == "blocked":
            status_text = terminal.warning("BLOCKED")
        else:
            # Unknown status - show as-is
            status_text = status.upper()

        print(
            f"{timestamp} [PID:{pid}] [{worker_id}] [ID:{test_id}] "
            f"{status_text} {test_name} in {duration:.1f} seconds"
        )

    def get_next_test_id(self) -> int:
        """Get next available test ID - ensures global uniqueness across workers"""
        self.test_counter += 1
        return self.test_counter
