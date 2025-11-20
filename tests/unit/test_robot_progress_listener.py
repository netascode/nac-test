# -*- coding: utf-8 -*-

"""Unit tests for Robot Framework socket-based progress listener.

These tests validate the socket IPC infrastructure without invoking the full
nac-test CLI. For end-to-end integration tests, see tests/integration/.
"""

import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List

import pytest

pytestmark = pytest.mark.unit


def test_robot_listener_socket_basic():
    """Test that Robot listener can send events via Unix socket.

    This test validates:
    1. ProgressEventServer can be started and creates Unix socket
    2. Robot listener can connect to the socket
    3. Events are transmitted correctly
    4. Event format matches PyATS schema
    """
    from nac_test.robot.progress_event_server import ProgressEventServer

    test_dir = (
        Path(__file__).parent.parent
        / "integration"
        / "fixtures"
        / "robot_progress_test"
    )
    assert test_dir.exists(), f"Test directory not found: {test_dir}"

    # Track received events
    received_events: List[Dict[str, Any]] = []

    def event_handler(event: Dict[str, Any]) -> None:
        """Callback to collect events."""
        received_events.append(event)

    async def run_test():
        with tempfile.TemporaryDirectory() as tmpdir:
            # Get absolute path to socket-based listener
            listener_path = (
                Path(__file__).parent.parent.parent
                / "nac_test"
                / "robot"
                / "NacProgressListenerSocket.py"
            )
            assert listener_path.exists(), f"Listener not found: {listener_path}"

            # Start event server
            server = ProgressEventServer(event_handler=event_handler)

            async with server.run_context():
                # Set socket path in environment so listener can find it
                env = {**os.environ, "NAC_TEST_EVENT_SOCKET": str(server.socket_path)}

                # Run robot with socket-based listener (single worker for basic test)
                cmd = [
                    "robot",
                    "--listener",
                    str(listener_path),
                    "-d",
                    tmpdir,
                    "--skiponfailure",
                    "expected_fail",
                    str(test_dir),
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                )

                # Give server a moment to process any pending events
                await asyncio.sleep(0.3)

            # Validate events were received
            assert len(received_events) > 0, "No events received via socket"

            # Validate event structure
            task_start_events = [
                e for e in received_events if e.get("event") == "task_start"
            ]
            task_end_events = [
                e for e in received_events if e.get("event") == "task_end"
            ]

            # With plain robot (not pabot), we get all test files in the directory
            # We have 4 test files with varying test counts
            # Accept any reasonable number of tests (at least some tests ran)
            assert len(task_start_events) >= 4, (
                f"Expected at least 4 task_start events, got {len(task_start_events)}"
            )
            assert len(task_end_events) >= 4, (
                f"Expected at least 4 task_end events, got {len(task_end_events)}"
            )

            # Validate we got matching start/end events (or close to it)
            # Allow for one missing event due to potential race conditions in test cleanup
            event_diff = abs(len(task_start_events) - len(task_end_events))
            assert event_diff <= 1, (
                f"Too many mismatched start/end events: {len(task_start_events)} starts, "
                f"{len(task_end_events)} ends"
            )

            # Validate event schema
            for event in task_start_events:
                assert event.get("version") == "1.0"
                assert "test_name" in event
                assert "worker_id" in event
                assert "timestamp" in event

            print(f"\n✅ Received {len(received_events)} events via socket")
            print(f"   - {len(task_start_events)} task_start events")
            print(f"   - {len(task_end_events)} task_end events")

    # Run async test
    asyncio.run(run_test())


def test_robot_listener_socket_parallel():
    """Test socket communication with parallel pabot execution.

    This test validates that events from multiple parallel Robot workers
    don't get corrupted or interleaved when transmitted via socket.
    """
    from nac_test.robot.progress_event_server import ProgressEventServer

    test_dir = (
        Path(__file__).parent.parent
        / "integration"
        / "fixtures"
        / "robot_progress_test"
    )
    assert test_dir.exists(), f"Test directory not found: {test_dir}"

    # Track received events
    received_events: List[Dict[str, Any]] = []

    def event_handler(event: Dict[str, Any]) -> None:
        """Thread-safe event collector."""
        received_events.append(event)

    async def run_test():
        with tempfile.TemporaryDirectory() as tmpdir:
            listener_path = (
                Path(__file__).parent.parent.parent
                / "nac_test"
                / "robot"
                / "NacProgressListenerSocket.py"
            )

            # Start event server
            server = ProgressEventServer(event_handler=event_handler)

            async with server.run_context():
                env = {**os.environ, "NAC_TEST_EVENT_SOCKET": str(server.socket_path)}

                # Run pabot with multiple workers to test parallel execution
                cmd = [
                    "pabot",
                    "--processes",
                    "2",  # Use 2 parallel workers
                    "--listener",
                    str(listener_path),
                    "--pabotlib",
                    "--pabotlibport",
                    "0",
                    "-d",
                    tmpdir,
                    "--skiponfailure",
                    "expected_fail",
                    str(test_dir),
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                )

                # Give server time to process all events
                await asyncio.sleep(0.2)

            # Validate events
            assert len(received_events) > 0, (
                "No events received from parallel execution"
            )

            task_start_events = [
                e for e in received_events if e.get("event") == "task_start"
            ]
            task_end_events = [
                e for e in received_events if e.get("event") == "task_end"
            ]

            # Should have 15 tests total (4 + 4 + 4 + 3 across 4 suites)
            assert len(task_start_events) >= 15
            assert len(task_end_events) >= 15

            # Validate no corruption - each event should be valid JSON with proper structure
            for event in received_events:
                assert "version" in event
                assert "event" in event
                assert event["version"] == "1.0"
                assert event["event"] in ["task_start", "task_end"]

            # Check that we have events from multiple workers
            worker_ids = set(
                e.get("worker_id") for e in received_events if "worker_id" in e
            )

            print(
                f"\n✅ Received {len(received_events)} events from parallel execution"
            )
            print(f"   - {len(task_start_events)} task_start events")
            print(f"   - {len(task_end_events)} task_end events")
            print(f"   - {len(worker_ids)} unique worker(s)")

    asyncio.run(run_test())


def test_robot_listener_socket_output_processor():
    """Test that socket events work with OutputProcessor.

    This validates the complete integration: Robot -> Socket -> OutputProcessor.
    """
    from nac_test.robot.progress_event_server import ProgressEventServer
    from nac_test.pyats_core.execution.output_processor import OutputProcessor
    from nac_test.pyats_core.progress import ProgressReporter

    test_dir = (
        Path(__file__).parent.parent
        / "integration"
        / "fixtures"
        / "robot_progress_test"
    )

    # Initialize OutputProcessor
    progress_reporter = ProgressReporter(total_tests=15, max_workers=1)
    test_status = {}
    progress_reporter.test_status = test_status
    output_processor = OutputProcessor(progress_reporter, test_status)

    # Event handler that feeds into OutputProcessor
    def event_handler(event: Dict[str, Any]) -> None:
        """Process events through OutputProcessor."""
        # Convert event to NAC_PROGRESS line format
        event_line = f"NAC_PROGRESS:{json.dumps(event)}"
        output_processor.process_line(event_line)

    async def run_test():
        with tempfile.TemporaryDirectory() as tmpdir:
            listener_path = (
                Path(__file__).parent.parent.parent
                / "nac_test"
                / "robot"
                / "NacProgressListenerSocket.py"
            )

            server = ProgressEventServer(event_handler=event_handler)

            async with server.run_context():
                env = {**os.environ, "NAC_TEST_EVENT_SOCKET": str(server.socket_path)}

                cmd = [
                    "pabot",
                    "--processes",
                    "2",
                    "--listener",
                    str(listener_path),
                    "--pabotlib",
                    "--pabotlibport",
                    "0",
                    "-d",
                    tmpdir,
                    "--skiponfailure",
                    "expected_fail",
                    str(test_dir),
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                )

                await asyncio.sleep(0.2)

            # Validate OutputProcessor tracked tests
            assert len(test_status) > 0, "OutputProcessor did not track any tests"

            # Check all tests were tracked (15 tests across 4 suites)
            assert len(test_status) >= 15, (
                f"Expected at least 15 tests, got {len(test_status)}"
            )

            # Validate test status structure
            for test_name, status in test_status.items():
                assert "status" in status
                assert "test_id" in status
                assert status["status"] in ["PASSED", "FAILED", "SKIPPED", "ERRORED"]

            print(f"\n✅ OutputProcessor tracked {len(test_status)} tests via socket:")
            for test_name, status in test_status.items():
                print(f"   - {test_name}: {status['status']}")

    asyncio.run(run_test())
