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

from nac_test.pyats_core.reporting.types import ResultStatus

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
            output_dir: Directory where the JSONL results file will be saved.
        """
        self.test_id = test_id
        self.output_dir = output_dir
        self.start_time = datetime.now()
        
        # Open JSONL file for streaming writes
        self.jsonl_path = output_dir / f"{test_id}.jsonl"
        self.jsonl_file = open(self.jsonl_path, 'w', buffering=1)  # Line buffered
        
        # Write metadata header as first line
        metadata_record = {
            "type": "metadata",
            "test_id": test_id,
            "start_time": self.start_time.isoformat()
        }
        self.jsonl_file.write(json.dumps(metadata_record) + "\n")
        
        # Keep only counters and status tracking in memory (Option 2 approach)
        self.result_counts = {"passed": 0, "failed": 0, "skipped": 0, "errored": 0, "info": 0}
        self.command_count = 0
        self._overall_status_determined = False
        self._current_overall_status = "passed"  # Start optimistic, update as we stream
        self.metadata: Dict[str, str] = {}  # Will be set by base test class

    def add_result(self, status: ResultStatus, message: str) -> None:
        """Add a test result - writes immediately to disk.

        Args:
            status: Result status from ResultStatus enum (e.g., ResultStatus.PASSED).
            message: Detailed result message.
        """
        logger.debug("[RESULT][%s] %s", status, message)
        
        # Write to disk immediately
        record = {
            "type": "result",
            "status": status.value,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        self.jsonl_file.write(json.dumps(record) + "\n")
        
        # Update in-memory counter and overall status tracking
        self.result_counts[status.value] = self.result_counts.get(status.value, 0) + 1
        
        # Update overall status in real-time (preserves existing business logic)
        if not self._overall_status_determined:
            if status.value in ["failed", "errored"]:
                self._current_overall_status = "failed"
                self._overall_status_determined = True  # Once failed, stays failed
            elif status.value not in ["skipped"]:
                # We have at least one non-skipped result, so not "all skipped"
                if self._current_overall_status == "skipped":
                    self._current_overall_status = "passed"

    # TODO: Consider alternative display options for command execution context (this is `test_context`):
    # Option 1: Group by test step with collapsible sections - better for tests with many API calls per step
    # Option 2: Inline commands with their corresponding results - more intuitive but requires restructuring
    # Option 3: (Current) Add context banners - simple to implement, maintains current structure
    # Trade-offs: Option 1 adds UI complexity, Option 2 requires significant template changes and might
    # make the results section too verbose, Option 3 keeps things simple but requires scrolling to correlate
    # keeping it simple for MVP
    def add_command_api_execution(
        self,
        device_name: str,
        command: str,
        output: str,
        data: Optional[Dict] = None,
        test_context: Optional[str] = None,
    ) -> None:
        """Add a command/API execution record - writes immediately to disk.

        Pre-truncates output to 50KB to avoid memory issues with large responses.
        Handles all execution types: API calls, SSH commands, D2D tests.

        Args:
            device_name: Device name (router, switch, APIC, vManage, etc.).
            command: Command or API endpoint.
            output: Raw output/response (will be truncated to 50KB).
            data: Parsed data (if applicable).
            test_context: Optional context describing which test step/verification this belongs to.
                         Example: "BGP peer 10.100.2.73 on node 202"

        #TODO: Alternative display options could be considered (need to discuss w/ the team):
            - Group executions by test step with collapsible sections
            - Inline commands directly with their corresponding test results
            - Current approach: Display context as banners above each execution
        The current approach was chosen for simplicity and backwards compatibility.
        """
        logger.debug("Recording command execution on %s: %s", device_name, command)

        # Pre-truncate to 50KB to prevent memory issues
        truncated_output = output[:50000] if len(output) > 50000 else output
        
        # Write to disk immediately
        record = {
            "type": "command_execution",
            "device_name": device_name,
            "command": command,
            "output": truncated_output,
            "data": data or {},
            "timestamp": datetime.now().isoformat(),
            "test_context": test_context
        }
        self.jsonl_file.write(json.dumps(record) + "\n")
        
        # Update counter only
        self.command_count += 1

    def save_to_file(self) -> Path:
        """Finalize JSONL file with summary record and close properly.
        
        Refactored from original JSON approach to streaming JSONL approach.
        Maintains same interface for backward compatibility.
        
        Returns:
            Path to the saved JSONL file (changed from JSON to JSONL).
        """
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        # Write final summary record (replaces old JSON structure)
        summary_record = {
            "type": "summary",
            "test_id": self.test_id,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration": duration,
            "overall_status": self._determine_overall_status(),
            "result_counts": self.result_counts,
            "command_count": self.command_count,
            "metadata": self.metadata if hasattr(self, "metadata") else {}
        }
        self.jsonl_file.write(json.dumps(summary_record) + "\n")
        
        # Close JSONL file handle properly
        self.jsonl_file.close()
        
        logger.debug("Finalized JSONL results to %s", self.jsonl_path)
        
        # Return JSONL path instead of JSON path
        return self.jsonl_path

    def _determine_overall_status(self) -> str:
        """Determine overall status using counter-based logic
        
       
        Uses straightforward rules instead of complex fallback logic:
        - If no results, status is SKIPPED
        - If any result is FAILED or ERRORED, overall is FAILED
        - If all results are SKIPPED, overall is SKIPPED
        - Otherwise, all passed

        Returns:
            Overall status as a string value.
        """
        # Handle edge case: no results recorded
        if sum(self.result_counts.values()) == 0:
            return ResultStatus.SKIPPED.value
        
        # Use real-time tracking for failed/errored (performance optimization)
        if self._overall_status_determined and self._current_overall_status == "failed":
            return ResultStatus.FAILED.value
        
        # Check for "all skipped" case using counters (preserves existing logic)
        # All results are skipped if: skipped > 0 AND all other counters are 0
        skipped_count = self.result_counts.get(ResultStatus.SKIPPED.value, 0)
        non_skipped_count = sum(
            self.result_counts.get(status.value, 0) 
            for status in ResultStatus 
            if status != ResultStatus.SKIPPED
        )
        
        if skipped_count > 0 and non_skipped_count == 0:
            return ResultStatus.SKIPPED.value
            
        # Mixed results (some passed, some skipped) or all passed
        return ResultStatus.PASSED.value

    def __del__(self):
        """Ensure file handle is closed even if cleanup isn't called."""
        if hasattr(self, 'jsonl_file') and not self.jsonl_file.closed:
            try:
                # Write emergency closure record
                self.jsonl_file.write(json.dumps({
                    "type": "emergency_close",
                    "timestamp": datetime.now().isoformat()
                }) + "\n")
                self.jsonl_file.close()
            except:
                pass  # Best effort
