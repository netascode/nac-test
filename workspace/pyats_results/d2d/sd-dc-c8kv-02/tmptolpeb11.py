# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt


"""Auto-generated PyATS job file for device sd-dc-c8kv-02"""

import os
import json
import logging
from pathlib import Path
from nac_test.pyats_core.ssh.connection_manager import DeviceConnectionManager
from pyats.easypy import run

# Device being tested (using hostname)
HOSTNAME = "sd-dc-c8kv-02"
DEVICE_INFO = {
    "hostname": "sd-dc-c8kv-02",
    "host": "10.100.1.2",
    "os": "iosxe",
    "device_id": "CHI24330K5Y",
    "type": "router",
    "username": "admin",
    "password": "cisco123",
}

# Test files to execute
TEST_FILES = [
    "/Users/oboehmer/Documents/DD/nac-test/tests/integration/fixtures/templates_pyats_qs/sdwan/tests/verify_iosxe_all_sd_wan_control_connections_are_up.py",
    "/Users/oboehmer/Documents/DD/nac-test/tests/integration/fixtures/templates_pyats_qs/sdwan/tests/verify_iosxe_all_sd_wan_control_connections_are_up_2.py",
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
