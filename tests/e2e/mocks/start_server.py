#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Start the mock API server as a background daemon."""

import argparse
import os
import signal
import sys
from pathlib import Path

# Ensure we can import mock_server from the same directory
sys.path.insert(0, str(Path(__file__).parent))

from mock_server import MockAPIServer

# Default port for standalone server (different from port 0 used in tests)
DEFAULT_STANDALONE_PORT = 5555

# PID and log files in system temp directory
PID_FILE = Path("/tmp/nac-test-mock-server.pid")
LOG_FILE = Path("/tmp/nac-test-mock-server.log")


def daemonize() -> bool:
    """Fork process to run in background.

    Returns:
        True if this is the child process (daemon), False if parent.
    """
    try:
        pid = os.fork()
        if pid > 0:
            # Parent process - exit
            return False
    except OSError as e:
        print(f"Fork failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Child process continues
    os.setsid()  # Create new session
    os.chdir("/")  # Change to root to avoid blocking unmounts

    # Redirect stdout/stderr to log file
    log_fd = open(LOG_FILE, "a")
    os.dup2(log_fd.fileno(), sys.stdout.fileno())
    os.dup2(log_fd.fileno(), sys.stderr.fileno())

    return True


def main() -> None:
    """Main entry point for starting the mock server."""
    parser = argparse.ArgumentParser(description="Start mock API server")
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_STANDALONE_PORT,
        help=f"Port to bind (default: {DEFAULT_STANDALONE_PORT})",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(Path(__file__).parent / "mock_api_config.yaml"),
        help="Path to config YAML (default: mock_api_config.yaml in same dir)",
    )
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="Run in foreground (don't daemonize)",
    )
    args = parser.parse_args()

    # Check if already running
    if PID_FILE.exists():
        existing_pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(existing_pid, 0)  # Check if process exists
            print(f"Server already running (PID: {existing_pid})")
            print(f"Stop it first with: python {Path(__file__).parent}/stop_server.py")
            sys.exit(1)
        except OSError:
            # Process doesn't exist, remove stale PID file
            PID_FILE.unlink()

    # Daemonize unless --foreground
    if not args.foreground:
        if not daemonize():
            # Parent process
            print(f"Starting mock server on port {args.port}...")
            print(f"Logs: {LOG_FILE}")
            print(f"PID file: {PID_FILE}")
            print(f"Stop with: python {Path(__file__).parent}/stop_server.py")
            return

    # Write PID file
    PID_FILE.write_text(str(os.getpid()))

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum: int, frame: object) -> None:
        print(f"\nReceived signal {signum}, shutting down...")
        if PID_FILE.exists():
            PID_FILE.unlink()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Create and start server
    server = MockAPIServer(host="127.0.0.1", port=args.port)

    # Load config if exists
    config_path = Path(args.config)
    if config_path.exists():
        server.load_from_yaml(config_path)
        print(
            f"Loaded {len(server.endpoint_configs)} endpoints from {config_path.name}"
        )
    else:
        print(f"Warning: Config file not found: {config_path}")

    server.start()
    print(f"Mock server running at {server.url}")
    print(f"PID: {os.getpid()}")

    # Keep running
    try:
        signal.pause()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.stop()
        if PID_FILE.exists():
            PID_FILE.unlink()


if __name__ == "__main__":
    main()
