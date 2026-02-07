#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Check mock API server status."""

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

PID_FILE = Path("/tmp/nac-test-mock-server.pid")


def main() -> None:
    """Main entry point for checking server status."""
    if not PID_FILE.exists():
        print("Server: NOT RUNNING (no PID file)")
        sys.exit(1)

    try:
        pid = int(PID_FILE.read_text().strip())
    except ValueError:
        print("Server: ERROR (invalid PID file)")
        sys.exit(1)

    # Check if process exists
    try:
        os.kill(pid, 0)
    except OSError:
        print(f"Server: DEAD (stale PID: {pid})")
        PID_FILE.unlink()
        sys.exit(1)

    # Try to connect
    try:
        # Assume default port 5555 if not specified
        req = urllib.request.Request("http://127.0.0.1:5555/", method="GET")
        with urllib.request.urlopen(req, timeout=1):
            status = "RESPONDING"
    except urllib.error.HTTPError:
        # 404 is fine - server is responding
        status = "RESPONDING"
    except Exception as e:
        status = f"NOT RESPONDING ({e})"

    print(f"Server: {status}")
    print(f"PID: {pid}")
    print("URL: http://127.0.0.1:5555")
    print("Logs: /tmp/nac-test-mock-server.log")


if __name__ == "__main__":
    main()
