# -*- coding: utf-8 -*-

"""Test result collector for PyATS HTML reporting.

This module provides a process-safe collector for test results and command/API
executions. Each test process gets its own collector instance that writes to
its own file, avoiding any need for cross-process synchronization.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from nac_test.pyats.reporting.types import ResultStatus

logger = logging.getLogger(__name__)


class TestResultCollector:
    """Collects results for a single test execution in a single process.

    This class provides methods to accumulate results without affecting test flow,
    similar to self.passed() and self.failed() but without controlling execution.
    Each process has its own instance, so no thread/process safety is needed.
    """

    def __init__(self, test_id: str, output_dir: Path) -> None:
        """Initialize the result collector.

        Args:
            test_id: Unique identifier for this test execution.
            output_dir: Directory where the JSON results file will be saved.
        """
        self.test_id = test_id
        self.output_dir = output_dir
        self.results: List[Dict[str, str]] = []
        self.command_executions: List[Dict[str, Any]] = []
        self.start_time = datetime.now()
        self.metadata: Dict[str, str] = {}  # Will be set by base test class

    def add_result(self, status: ResultStatus, message: str) -> None:
        """Add a test result.

        Args:
            status: Result status from ResultStatus enum (e.g., ResultStatus.PASSED).
            message: Detailed result message.
        """
        logger.debug("[RESULT][%s] %s", status, message)
        self.results.append({
            "status": status.value,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })

    def add_command_api_execution(
        self, 
        device_name: str, 
        command: str, 
        output: str, 
        data: Optional[Dict] = None
    ) -> None:
        """Add a command/API execution record.

        Pre-truncates output to 50KB to avoid memory issues with large responses.

        Args:
            device_name: Device name (router, switch, APIC, vManage, etc.).
            command: Command or API endpoint.
            output: Raw output/response (will be truncated to 50KB).
            data: Parsed data (if applicable).
        """
        logger.debug("Recording command execution on %s: %s", device_name, command)
        
        # Pre-truncate to 50KB to avoid memory issues
        truncated_output = output[:50000] if len(output) > 50000 else output
        
        self.command_executions.append({
            "device_name": device_name,
            "command": command,
            "output": truncated_output,
            "data": data or {},
            "timestamp": datetime.now().isoformat()
        })

    def save_to_file(self) -> Path:
        """Save results to JSON file - called once at test end.

        Saves everything in a single JSON file to reduce I/O operations.

        Returns:
            Path to the saved JSON file.
        """
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        data = {
            "test_id": self.test_id,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration": duration,
            "results": self.results,
            "command_executions": self.command_executions,
            "overall_status": self._determine_overall_status(),
            # Include metadata directly in the results file
            "metadata": self.metadata if hasattr(self, 'metadata') else {}
        }
        
        output_file = self.output_dir / f"{self.test_id}.json"
        logger.debug("Saving test results to %s", output_file)
        
        output_file.write_text(json.dumps(data, indent=2))
        return output_file

    def _determine_overall_status(self) -> str:
        """Simple, clear status determination.

        Uses straightforward rules instead of complex fallback logic:
        - If no results, status is SKIPPED
        - If any result is FAILED or ERRORED, overall is FAILED
        - Otherwise, all passed

        Returns:
            Overall status as a string value.
        """
        if not self.results:
            return ResultStatus.SKIPPED.value
            
        # If any result is FAILED or ERRORED, overall is FAILED
        for result in self.results:
            if result["status"] in [ResultStatus.FAILED.value, ResultStatus.ERRORED.value]:
                return ResultStatus.FAILED.value
                
        # All passed
        return ResultStatus.PASSED.value 