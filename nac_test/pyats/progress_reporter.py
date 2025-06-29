# -*- coding: utf-8 -*-

"""Progress reporting for PyATS tests matching Robot Framework format."""

import time
import os
from datetime import datetime
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ProgressReporter:
    """Reports PyATS test progress in a format matching Robot Framework output."""
    
    def __init__(self):
        self.start_time = time.time()
        
    def report_test_start(self, test_name: str, pid: int, worker_id: int, test_id: int) -> None:
        """Format: 2025-06-27 18:26:13.620910 [PID:893267] [0] [ID:6] EXECUTING ..."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        print(f"{timestamp} [PID:{pid}] [{worker_id}] [ID:{test_id}] EXECUTING {test_name}")
    
    def report_test_end(self, test_name: str, pid: int, worker_id: int, test_id: int, 
                       status: str, duration: float) -> None:
        """Format: 2025-06-27 18:26:16.834346 [PID:893270] [4] [ID:4] PASSED ... in 3.2 seconds"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        # Simple color coding for terminals that support it
        color = {'PASSED': '\033[92m', 'FAILED': '\033[91m', 'SKIPPED': '\033[93m'}.get(status, '')
        reset = '\033[0m' if color else ''
        print(f"{timestamp} [PID:{pid}] [{worker_id}] [ID:{test_id}] "
              f"{color}{status}{reset} {test_name} in {duration:.1f} seconds") 