# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""PyATS output processing functionality."""

import json
import logging
import os
import re
import time
from typing import Any

from nac_test.pyats_core.progress import ProgressReporter
from nac_test.utils.terminal import terminal

logger = logging.getLogger(__name__)


class OutputProcessor:
    """Processes PyATS test output and handles progress events."""

    def __init__(
        self,
        progress_reporter: ProgressReporter | None = None,
        test_status: dict[str, Any] | None = None,
    ):
        """Initialize output processor.

        Args:
            progress_reporter: Progress reporter instance for test progress tracking
            test_status: Dictionary reference for tracking test status
        """
        self.progress_reporter = progress_reporter
        self.test_status = test_status or {}

    def process_line(self, line: str) -> None:
        """Process output line, looking for our progress events.

        Args:
            line: Output line to process
        """
        # Look for our structured progress events
        if line.startswith("NAC_PROGRESS:"):
            try:
                # Parse our JSON event
                event_json = line[13:]  # Remove "NAC_PROGRESS:" prefix
                event = json.loads(event_json)

                # Validate event schema version
                if event.get("version", "1.0") != "1.0":
                    logger.warning(
                        f"Unknown event schema version: {event.get('version')}"
                    )

                self._handle_progress_event(event)
            except json.JSONDecodeError:
                # If parsing fails, show the line in debug mode
                if os.environ.get("NAC_TEST_DEBUG"):
                    print(f"Failed to parse progress event: {line}")
            except Exception as e:
                logger.error(f"Error processing progress event: {e}", exc_info=True)
        else:
            # Show line if it matches our criteria
            if self._should_show_line(line):
                print(line)

    def _handle_progress_event(self, event: dict[str, Any]) -> None:
        """Handle structured progress event from plugin.

        Args:
            event: Progress event dictionary
        """
        event_type = event.get("event")

        if event_type == "task_start":
            # Assign global test ID
            test_id = 0
            if self.progress_reporter:
                test_id = self.progress_reporter.get_next_test_id()

                # Report test starting
                self.progress_reporter.report_test_start(
                    event["test_name"], event["pid"], event["worker_id"], test_id
                )

            # Track status with assigned test ID and title
            # Use taskid as key, test_name is not unique across devices for d2d tests
            self.test_status[event["taskid"]] = {
                "start_time": event["timestamp"],
                "status": "EXECUTING",
                "worker": event["worker_id"],
                "test_id": test_id,
                "taskid": event["taskid"],
                "title": event.get(
                    "test_title", event["test_name"]
                ),  # Use test_name as final fallback
                "test_file": event.get(
                    "test_file"
                ),  # Store for test type categorization
                "hostname": event.get(
                    "hostname"
                ),  # Device name for D2D tests, None for API tests
            }

        elif event_type == "task_end":
            # Retrieve the test ID we assigned at start using taskid
            test_info = self.test_status.get(event["taskid"], {})
            test_id = test_info.get("test_id", 0)

            # Report test completion
            if self.progress_reporter:
                self.progress_reporter.report_test_end(
                    event["test_name"],
                    event["pid"],
                    event["worker_id"],
                    test_id,
                    event["result"],
                    event["duration"],
                )

            # Update status using taskid
            if event["taskid"] in self.test_status:
                self.test_status[event["taskid"]].update(
                    {"status": event["result"], "duration": event["duration"]}
                )

            # After progress reporter shows the line, add title display
            title = test_info.get("title", event["test_name"])
            hostname = test_info.get("hostname")

            # Format display title - include hostname for D2D tests
            if hostname:
                display_title = f"{title} ({hostname})"
            else:
                display_title = title

            # Format status for display - distinguish between FAILED and ERRORED
            result_status = event["result"].lower()
            if result_status == "errored":
                status_text = "ERROR"
            else:
                status_text = result_status.upper()

            # Display title line like Robot Framework with colors
            separator = "-" * 78

            # Color based on status
            if result_status == "passed":
                # Green for passed
                print(terminal.success(separator))
                print(terminal.success(f"{display_title:<70} | {status_text} |"))
                print(terminal.success(separator))
            elif result_status in ["failed", "errored"]:
                # Red for failed/errored
                print(terminal.error(separator))
                print(terminal.error(f"{display_title:<70} | {status_text} |"))
                print(terminal.error(separator))
            else:
                # Default (white) for other statuses
                print(separator)
                print(f"{display_title:<70} | {status_text} |")
                print(separator)

        elif event_type == "job_end":
            # When job ends, check for orphaned tests (started but never ended)
            # This handles PyATS multi-process architecture where post_task() may not
            # be called for tests that error during setup
            self._finalize_orphaned_tests(event)

        elif event_type == "section_start" and os.environ.get("NAC_TEST_DEBUG"):
            # In debug mode, show section progress
            print(f"  -> Section {event['section']} starting")

        elif event_type == "section_end" and os.environ.get("NAC_TEST_DEBUG"):
            print(f"  -> Section {event['section']} {event['result']}")

    def _finalize_orphaned_tests(self, job_end_event: dict[str, Any]) -> None:
        """Finalize any tests that started but never received task_end.

        PyATS uses a multi-process architecture where tasks run in subprocesses.
        When a test errors during setup, PyATS may not call post_task() in the
        subprocess, resulting in no task_end event being emitted. This method
        detects such orphaned tests and generates synthetic completions.

        Important: Only finalizes tests from the SAME worker as the job_end event
        to avoid incorrectly finalizing tests from parallel jobs.

        Args:
            job_end_event: The job_end event that triggered finalization.
        """
        job_worker_id = job_end_event.get("worker_id", "")

        # Find tests still in EXECUTING status that belong to this worker
        orphaned_tests = [
            (test_name, info)
            for test_name, info in self.test_status.items()
            if info.get("status") == "EXECUTING" and info.get("worker") == job_worker_id
        ]

        if not orphaned_tests:
            return

        logger.debug(
            f"Found {len(orphaned_tests)} orphaned test(s) for worker {job_worker_id}"
        )

        for test_name, test_info in orphaned_tests:
            test_id = test_info.get("test_id", 0)
            title = test_info.get("title", test_name)
            worker_id = test_info.get("worker", job_end_event.get("worker_id", "0"))
            start_time = test_info.get("start_time", time.time())
            duration = time.time() - start_time

            logger.debug(f"Finalizing orphaned test: {test_name} (ID={test_id})")

            # Report test completion as errored
            if self.progress_reporter:
                self.progress_reporter.report_test_end(
                    test_name,
                    job_end_event.get("pid", 0),
                    worker_id,
                    test_id,
                    "errored",
                    duration,
                )

            # Update status
            self.test_status[test_name].update(
                {"status": "errored", "duration": duration}
            )

            # Display the completion line
            separator = "-" * 78
            print(terminal.error(separator))
            print(terminal.error(f"{title:<70} | ERROR |"))
            print(terminal.error(separator))

    def _should_show_line(self, line: str) -> bool:
        """Determine if line should be shown to user.

        Filter out verbose PyATS output while keeping important information.

        Args:
            line: Output line to check

        Returns:
            True if line should be shown, False otherwise
        """
        # In debug mode, show everything
        if os.environ.get("NAC_TEST_DEBUG"):
            return True

        # Always suppress these patterns for clean console output
        suppress_patterns = [
            r"%HTTPX-INFO:",
            r"%AETEST-INFO:",
            r"%AETEST-ERROR:",  # We'll show our own error summary
            r"%EASYPY-INFO:",
            r"%WARNINGS-WARNING:",
            r"%GENIE-INFO:",
            r"%UNICON-INFO:",
            r"%SCRIPT-INFO:",  # Suppress script-level info logs from tests
            r"NAC_PROGRESS_PLUGIN:",  # Suppress plugin debug output
            r"^\s*$",  # Empty lines
            r"^\+[-=]+\+$",  # PyATS table borders
            r"^\|.*\|$",  # PyATS table content
            r"^[-=]+$",  # Separator lines
            r"Starting section",  # Section start messages
            r"Starting testcase",  # Test start messages
        ]

        for pattern in suppress_patterns:
            if re.search(pattern, line):
                return False

        # Show critical information
        show_patterns = [
            r"ERROR",
            r"FAILED",
            r"CRITICAL",
            r"Traceback",
            r"Exception.*Error",
            r"RECOVERED",  # Controller recovered messages
            r"RECOVERY",  # Controller recovery messages
        ]

        for pattern in show_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                # But still suppress if it's part of PyATS formatting
                if not any(re.search(p, line) for p in [r"^\|", r"^\+"]):
                    return True

        return False
