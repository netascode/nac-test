#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Stop the mock API server."""

import os
import sys
import time
from pathlib import Path

PID_FILE = Path("/tmp/nac-test-mock-server.pid")


def main() -> None:
    """Main entry point for stopping the mock server."""
    if not PID_FILE.exists():
        print("No running server found (PID file missing)")
        sys.exit(1)

    try:
        pid = int(PID_FILE.read_text().strip())
    except ValueError:
        print(f"Invalid PID file: {PID_FILE}")
        PID_FILE.unlink()
        sys.exit(1)

    # Check if process exists
    try:
        os.kill(pid, 0)
    except OSError:
        print(f"Server not running (stale PID: {pid})")
        PID_FILE.unlink()
        sys.exit(1)

    # Send SIGTERM for graceful shutdown
    print(f"Stopping server (PID: {pid})...")
    try:
        os.kill(pid, 15)  # SIGTERM

        # Wait up to 5 seconds for graceful shutdown
        for _ in range(50):
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except OSError:
                # Process terminated
                break
        else:
            # Force kill if still running
            print("Graceful shutdown failed, forcing...")
            os.kill(pid, 9)  # SIGKILL

        print("Server stopped")
        if PID_FILE.exists():
            PID_FILE.unlink()

    except OSError as e:
        print(f"Error stopping server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
