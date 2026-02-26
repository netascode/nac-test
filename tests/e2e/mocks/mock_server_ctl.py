#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Mock API server control script with start/stop/status subcommands."""

import argparse
import json
import os
import signal
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Ensure we can import mock_server from the same directory
sys.path.insert(0, str(Path(__file__).parent))

from mock_server import (
    SERVER_POLL_INTERVAL_SECONDS,
    SERVER_STARTUP_TIMEOUT_SECONDS,
    MockAPIServer,
)

DEFAULT_PORT = 5555
STATE_FILE = Path("/tmp/nac-test-mock-server.json")
LOG_FILE = Path("/tmp/nac-test-mock-server.log")


def read_state() -> dict[str, int | str] | None:
    """Read server state from JSON file. Returns None if not found or invalid."""
    if not STATE_FILE.exists():
        return None
    try:
        data: dict[str, int | str] = json.loads(STATE_FILE.read_text())
        return data
    except (json.JSONDecodeError, OSError):
        return None


def write_state(pid: int, port: int) -> None:
    """Write server state to JSON file."""
    state = {
        "pid": pid,
        "port": port,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    STATE_FILE.write_text(json.dumps(state, indent=2))


def remove_state() -> None:
    """Remove state file if it exists."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()


def is_process_running(pid: int) -> bool:
    """Check if a process with given PID is running."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def daemonize() -> bool:
    """Fork process to run in background. Returns True if child (daemon), False if parent."""
    try:
        pid = os.fork()
        if pid > 0:
            return False  # Parent process
    except OSError as e:
        print(f"Fork failed: {e}", file=sys.stderr)
        sys.exit(1)

    os.setsid()
    os.chdir("/")

    log_fd = open(LOG_FILE, "a")
    os.dup2(log_fd.fileno(), sys.stdout.fileno())
    os.dup2(log_fd.fileno(), sys.stderr.fileno())
    log_fd.close()  # Release original handle after duplication

    return True  # Child process (daemon)


def cmd_start(args: argparse.Namespace) -> None:
    """Start the mock server."""
    state = read_state()
    if state:
        pid = int(state["pid"])
        if is_process_running(pid):
            print(f"Server already running (PID: {pid}, port: {state['port']})")
            print("Stop it first with: python mock_server_ctl.py stop")
            sys.exit(1)
        remove_state()  # Clean up stale state

    if not args.foreground:
        if not daemonize():
            # Parent process
            print(f"Starting mock server on port {args.port}...")
            print(f"Logs: {LOG_FILE}")
            print(f"State: {STATE_FILE}")
            print("Stop with: python mock_server_ctl.py stop")
            return

    server = MockAPIServer(host="127.0.0.1", port=args.port)

    config_path = Path(args.config)
    if config_path.exists():
        server.load_from_yaml(config_path)
        print(
            f"Loaded {len(server.endpoint_configs)} endpoints from {config_path.name}"
        )
    else:
        print(f"Warning: Config file not found: {config_path}")

    server.start()

    # Write state after server starts (to capture actual port)
    write_state(os.getpid(), server.port)

    print(f"Mock server running at {server.url}")
    print(f"PID: {os.getpid()}")

    def shutdown_handler(signum: int, frame: object) -> None:
        print(f"\nReceived signal {signum}, shutting down...")
        server.stop()
        remove_state()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    try:
        signal.pause()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.stop()
        remove_state()


def cmd_stop(args: argparse.Namespace) -> None:
    """Stop the mock server."""
    state = read_state()
    if not state:
        print("No running server found (state file missing)")
        sys.exit(1)

    pid = int(state["pid"])
    if not is_process_running(pid):
        print(f"Server not running (stale PID: {pid})")
        remove_state()
        sys.exit(1)

    print(f"Stopping server (PID: {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)

        max_attempts = int(
            SERVER_STARTUP_TIMEOUT_SECONDS / SERVER_POLL_INTERVAL_SECONDS
        )
        for _ in range(max_attempts):
            if not is_process_running(pid):
                break
            time.sleep(SERVER_POLL_INTERVAL_SECONDS)
        else:
            print("Graceful shutdown failed, forcing...")
            os.kill(pid, signal.SIGKILL)

        print("Server stopped")
        remove_state()

    except OSError as e:
        print(f"Error stopping server: {e}")
        sys.exit(1)


def cmd_status(args: argparse.Namespace) -> None:
    """Check mock server status."""
    state = read_state()
    if not state:
        print("Server: NOT RUNNING (no state file)")
        sys.exit(1)

    pid = int(state["pid"])
    port = int(state["port"])

    if not is_process_running(pid):
        print(f"Server: DEAD (stale PID: {pid})")
        remove_state()
        sys.exit(1)

    # Health check using the actual port from state
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/", method="GET")
        with urllib.request.urlopen(req, timeout=1):
            status = "RESPONDING"
    except urllib.error.HTTPError:
        status = "RESPONDING"  # 404 is fine - server is responding
    except Exception as e:
        status = f"NOT RESPONDING ({e})"

    print(f"Server: {status}")
    print(f"PID: {pid}")
    print(f"URL: http://127.0.0.1:{port}")
    print(f"Logs: {LOG_FILE}")
    if "started_at" in state:
        print(f"Started: {state['started_at']}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Mock API server control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # start subcommand
    start_parser = subparsers.add_parser("start", help="Start the mock server")
    start_parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to bind (default: {DEFAULT_PORT})",
    )
    start_parser.add_argument(
        "--config",
        type=str,
        default=str(Path(__file__).parent / "mock_api_config.yaml"),
        help="Path to config YAML (default: mock_api_config.yaml in same dir)",
    )
    start_parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run in foreground (don't daemonize)",
    )
    start_parser.set_defaults(func=cmd_start)

    # stop subcommand
    stop_parser = subparsers.add_parser("stop", help="Stop the mock server")
    stop_parser.set_defaults(func=cmd_stop)

    # status subcommand
    status_parser = subparsers.add_parser("status", help="Check server status")
    status_parser.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
