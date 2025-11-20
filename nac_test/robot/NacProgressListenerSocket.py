# -*- coding: utf-8 -*-

"""Robot Framework listener for emitting structured progress events via Unix socket.

This listener integrates with Robot Framework's listener API v3 to provide
real-time progress updates. Unlike the stdout-based listener, this version uses
a Unix socket for communication, which prevents event interleaving when pabot
runs tests in parallel.

Events are sent as line-delimited JSON to a Unix socket server.
"""

import json
import os
import socket
import time
from typing import Any, Dict, Optional
from pathlib import Path


# Event schema version for compatibility with OutputProcessor
EVENT_SCHEMA_VERSION = "1.0"


class NacProgressListenerSocket:
    """
    Robot Framework listener that emits structured progress events via socket.

    Events are sent as line-delimited JSON to a Unix socket, matching the
    format used by PyATS's ProgressReporterPlugin. This allows the same
    OutputProcessor to handle events from both test frameworks.

    Uses Robot Framework Listener API v3.
    """

    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self):
        """Initialize the listener."""
        self.worker_id = self._get_worker_id()
        self.test_start_times: Dict[str, float] = {}
        # Track suite names for better test identification
        self.current_suite_name = ""

        # Debug tracking
        self.events_sent = 0
        self.debug = os.environ.get("NAC_TEST_DEBUG") == "1"

        # Socket connection
        self.socket_path = os.environ.get("NAC_TEST_EVENT_SOCKET")
        self.socket: Optional[socket.socket] = None
        self._connect_to_server()

        if self.debug:
            self._debug_log(
                f"Listener initialized, socket_path={self.socket_path}, socket={'connected' if self.socket else 'None'}"
            )

    def _debug_log(self, message: str) -> None:
        """Write debug message to stderr."""
        if self.debug:
            import sys

            print(
                f"[LISTENER-DEBUG PID:{os.getpid()}] {message}",
                file=sys.stderr,
                flush=True,
            )
        # Also always set self.debug attribute for first call
        if not hasattr(self, "debug"):
            self.debug = os.environ.get("NAC_TEST_DEBUG") == "1"

    def _connect_to_server(self) -> None:
        """Connect to the progress event server."""
        if not self.socket_path:
            # No socket configured - events will be silently dropped
            # This allows the listener to be loaded without a server for testing
            if self.debug:
                self._debug_log("No socket path configured")
            return

        try:
            self._debug_log(f"Connecting to socket: {self.socket_path}")
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.connect(self.socket_path)
            # Keep socket blocking to ensure reliable communication
            # Non-blocking would require more complex buffering logic
            self.socket.setblocking(True)
            # Set a timeout to avoid hanging forever
            self.socket.settimeout(1.0)
            self._debug_log("Socket connected successfully")
        except (FileNotFoundError, ConnectionRefusedError) as e:
            # Server not running - log and continue without events
            # Tests will still run, just without progress tracking
            self._debug_log(f"Failed to connect: {e}")
            self.socket = None
        except Exception as e:
            # Unexpected error - log and continue
            self._debug_log(f"Unexpected connection error: {e}")
            self.socket = None

    def _emit_event(self, event: Dict[str, Any]) -> None:
        """Emit a progress event via socket.

        Args:
            event: Event dictionary to emit
        """
        if not self.socket:
            self._debug_log("Cannot emit event - socket is None")
            return

        self.events_sent += 1
        event_type = event.get("event", "unknown")
        test_name = event.get("test_name", "unknown")

        self._debug_log(
            f"Emitting event #{self.events_sent}: {event_type} for {test_name}"
        )

        try:
            # Send line-delimited JSON
            message = json.dumps(event) + "\n"
            self.socket.sendall(message.encode("utf-8"))
            self._debug_log("Event sent successfully")

            # No need to wait for acknowledgment - fire and forget
            # The server will process events asynchronously

        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            # Server disconnected - close socket and stop sending
            self._debug_log(f"Socket error: {e}, closing socket")
            self._close_socket()
        except Exception as e:
            # Any other error - continue without events
            self._debug_log(f"Unexpected error: {e}")
            pass

    def _close_socket(self) -> None:
        """Close the socket connection."""
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

    def _get_worker_id(self) -> str:
        """Get the worker ID from environment or process ID.

        Returns:
            Worker identifier string
        """
        # Check if pabot set a worker ID environment variable
        if "ROBOT_WORKER_ID" in os.environ:
            return os.environ["ROBOT_WORKER_ID"]

        # Check pabot's PABOTEXECUTIONPOOLID
        if "PABOTEXECUTIONPOOLID" in os.environ:
            return os.environ["PABOTEXECUTIONPOOLID"]

        # Fall back to process ID
        return str(os.getpid())

    def _get_test_name(self, data: Any) -> str:
        """Extract a clean test name from Robot test data.

        Args:
            data: Robot test data object

        Returns:
            Formatted test name string
        """
        try:
            # Build hierarchical name: suite.subsuite.test
            parts = []

            # Add suite hierarchy
            if hasattr(data, "parent") and data.parent:
                suite = data.parent
                suite_parts = []
                while suite:
                    if hasattr(suite, "name") and suite.name:
                        suite_parts.insert(0, suite.name)
                    suite = getattr(suite, "parent", None)
                parts.extend(suite_parts)

            # Add test name
            if hasattr(data, "name"):
                parts.append(data.name)

            return ".".join(parts) if parts else "unknown"
        except Exception:
            return "unknown"

    def start_suite(self, data: Any, result: Any) -> None:
        """Called when a test suite starts.

        Args:
            data: Suite data object
            result: Suite result object
        """
        try:
            if hasattr(data, "name"):
                self.current_suite_name = data.name
        except Exception:
            pass

    def start_test(self, data: Any, result: Any) -> None:
        """Called when a test case starts.

        Args:
            data: Test data object
            result: Test result object
        """
        try:
            test_name = self._get_test_name(data)

            # Store start time for duration calculation
            self.test_start_times[test_name] = time.time()

            # Extract source file path
            test_file = str(data.source) if hasattr(data, "source") else "unknown"

            # Build task_start event (matching PyATS format)
            event = {
                "version": EVENT_SCHEMA_VERSION,
                "event": "task_start",
                "test_name": test_name,
                "test_file": test_file,
                "test_title": result.name if hasattr(result, "name") else test_name,
                "worker_id": self.worker_id,
                "pid": os.getpid(),
                "timestamp": time.time(),
                "taskid": f"robot_{id(result)}",  # Unique ID for this test
            }

            self._emit_event(event)

        except Exception:
            pass  # Silently fail to avoid breaking test execution

    def end_test(self, data: Any, result: Any) -> None:
        """Called when a test case ends.

        Args:
            data: Test data object
            result: Test result object
        """
        try:
            test_name = self._get_test_name(data)

            # Calculate duration
            start_time = self.test_start_times.get(test_name, time.time())
            duration = time.time() - start_time

            # Map Robot status to PyATS format
            # Robot statuses: PASS, FAIL, SKIP, NOT_RUN
            # PyATS statuses: PASSED, FAILED, ERRORED, SKIPPED
            status_map = {
                "PASS": "PASSED",
                "FAIL": "FAILED",
                "SKIP": "SKIPPED",
                "NOT_RUN": "SKIPPED",
            }

            robot_status = result.status if hasattr(result, "status") else "UNKNOWN"
            pyats_status = status_map.get(robot_status, "ERRORED")

            # Extract source file path
            test_file = str(data.source) if hasattr(data, "source") else "unknown"

            # Build task_end event (matching PyATS format)
            event = {
                "version": EVENT_SCHEMA_VERSION,
                "event": "task_end",
                "test_name": test_name,
                "test_file": test_file,
                "worker_id": self.worker_id,
                "result": pyats_status,
                "duration": duration,
                "timestamp": time.time(),
                "pid": os.getpid(),
                "taskid": f"robot_{id(result)}",
            }

            self._emit_event(event)

            # Clean up start time
            self.test_start_times.pop(test_name, None)

        except Exception:
            pass  # Silently fail to avoid breaking test execution

    def close(self) -> None:
        """Called when Robot Framework execution ends."""
        try:
            self._debug_log(f"Listener closing, sent {self.events_sent} events total")
            # Clean up any remaining state
            self.test_start_times.clear()

            # Close socket connection
            self._close_socket()
        except Exception:
            pass
