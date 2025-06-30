# -*- coding: utf-8 -*-

"""Progress reporting for PyATS tests matching Robot Framework format."""

import time
import os
from datetime import datetime
import logging
from typing import Optional
from colorama import Fore, Style, init

init()  # Initialize colorama for cross-platform color support

logger = logging.getLogger(__name__)


class ProgressReporter:
    """Reports PyATS test progress in a format matching Robot Framework output."""

    def __init__(self, total_tests: int = 0, max_workers: int = 1):
        self.start_time = time.time()
        self.total_tests = total_tests
        self.max_workers = max_workers
        self.test_status = {}
        self.test_counter = 0  # Global test ID counter

    def report_test_start(
        self, test_name: str, pid: int, worker_id: str, test_id: int
    ) -> None:
        """Report that a test has started executing"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Use colorama for cross-platform color support
        status_color = Fore.YELLOW

        print(
            f"{timestamp} [PID:{pid}] [{worker_id}] [ID:{test_id}] "
            f"{status_color}EXECUTING{Style.RESET_ALL} {test_name}"
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

        # Color based on status using colorama for cross-platform support
        # Aligning similarly to Robot Framework output
        if status == "PASSED":
            status_color = Fore.GREEN
        elif status == "FAILED":
            status_color = Fore.RED
        elif status == "SKIPPED":
            status_color = Fore.YELLOW
        else:
            status_color = Fore.WHITE

        print(
            f"{timestamp} [PID:{pid}] [{worker_id}] [ID:{test_id}] "
            f"{status_color}{status}{Style.RESET_ALL} {test_name} in {duration:.1f} seconds"
        )

    def get_next_test_id(self) -> int:
        """Get next available test ID - ensures global uniqueness across workers"""
        self.test_counter += 1
        return self.test_counter

    def _format_duration(self, seconds: float) -> str:
        """Format duration like Robot Framework does"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        else:
            minutes = int(seconds / 60)
            secs = seconds % 60
            return f"{minutes}m {secs:.0f}s"
