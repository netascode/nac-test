# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt


"""Auto-generated PyATS job file for device EDGE01"""

import json
import logging
import os
import re
from pathlib import Path
from pyats.easypy import run
from nac_test.pyats_core.ssh.connection_manager import DeviceConnectionManager

# Device being tested (using hostname)
HOSTNAME = "EDGE01"
DEVICE_INFO = {
    "hostname": "EDGE01",
    "host": "198.18.130.1",
    "os": "iosxe",
    "device_id": "EDGE01",
    "username": "%ENV{IOSXE_USERNAME}",
    "password": "%ENV{IOSXE_PASSWORD}",
}

# Test files to execute
TEST_FILES = [
    "/Users/oboehmer/Documents/DD/nac-test/workspace/catc/templates-mini/tests/pyats/verify_iosxe_vtp_mode_status.py"
]


def main(runtime):
    """Main job file entry point for device-centric execution"""
    # Set up environment variables that SSHTestBase expects
    os.environ["DEVICE_INFO"] = json.dumps(DEVICE_INFO)

    # Create and attach connection manager to runtime
    # This will be shared across all tests for this device
    runtime.connection_manager = DeviceConnectionManager(max_concurrent=1)

    # Sanitize hostname for taskid (replace non-alphanumeric with underscore and lowercase)
    safe_hostname = re.sub(r"[^a-zA-Z0-9_]", "_", HOSTNAME).lower()

    # Run all test files for this device
    for idx, test_file in enumerate(TEST_FILES):
        # Create meaningful task ID from test file name and hostname
        test_name = Path(test_file).stem
        run(
            testscript=test_file,
            taskid=f"{safe_hostname}_{test_name}",
            hostname=HOSTNAME,  # Pass original hostname for progress reporting
            max_runtime=21600,
            testbed=runtime.testbed,
        )
