# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt


"""Auto-generated PyATS job file for device BR10"""

import os
import json
import logging
from pathlib import Path
from pyats.easypy import run
from nac_test.pyats_core.ssh.connection_manager import DeviceConnectionManager

# Device being tested (using hostname)
HOSTNAME = "BR10"
DEVICE_INFO = {
    "hostname": "BR10",
    "host": "198.18.130.10",
    "os": "iosxe",
    "device_id": "BR10",
    "username": "%ENV{IOSXE_USERNAME}",
    "password": "%ENV{IOSXE_PASSWORD}",
}

# Test files to execute
TEST_FILES = [
    "/Users/oboehmer/Documents/DD/nac-test/workspace/catc/templates/tests/pyats/verify_iosxe_fabric_node_licensing_status.py",
    "/Users/oboehmer/Documents/DD/nac-test/workspace/catc/templates/tests/pyats/verify_iosxe_lisp_sessions_status.py",
    "/Users/oboehmer/Documents/DD/nac-test/workspace/catc/templates/tests/pyats/verify_iosxe_no_critical_errors_in_system_logs.py",
    "/Users/oboehmer/Documents/DD/nac-test/workspace/catc/templates/tests/pyats/verify_iosxe_vtp_mode_status.py",
]


def main(runtime):
    """Main job file entry point for device-centric execution"""
    # Set up environment variables that SSHTestBase expects
    os.environ["DEVICE_INFO"] = json.dumps(DEVICE_INFO)

    # Create and attach connection manager to runtime
    # This will be shared across all tests for this device
    runtime.connection_manager = DeviceConnectionManager(max_concurrent=1)

    # Run all test files for this device
    for idx, test_file in enumerate(TEST_FILES):
        # Create meaningful task ID from test file name and hostname
        # e.g., "router1_epg_attributes"
        test_name = Path(test_file).stem
        run(
            testscript=test_file,
            taskid=f"{HOSTNAME}_{test_name}",
            max_runtime=21600,
            testbed=runtime.testbed,
        )
