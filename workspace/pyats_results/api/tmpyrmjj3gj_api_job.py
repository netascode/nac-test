# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt


"""Auto-generated PyATS job file by nac-test"""

import os
from pathlib import Path

from pyats.easypy import run

# Test files to execute
TEST_FILES = [
    "/Users/oboehmer/Documents/DD/nac-test/tests/integration/fixtures/templates_pyats_qs/sdwan/tests/verify_sdwanmanager_all_sd_wan_edge_configurations_are_in_sync.py",
    "/Users/oboehmer/Documents/DD/nac-test/tests/integration/fixtures/templates_pyats_qs/sdwan/tests/verify_sdwanmanager_all_sd_wan_edge_configurations_are_in_sync_2.py",
]


def main(runtime):
    """Main job file entry point"""
    # Set max workers
    runtime.max_workers = 2

    # Note: runtime.directory is read-only and set by --archive-dir
    # The output directory is: /private/tmp/pyats-sdwan/pyats_results

    # Run all test files
    for idx, test_file in enumerate(TEST_FILES):
        # Create meaningful task ID from test file name
        # e.g., "epg_attributes.py" -> "epg_attributes"
        test_name = Path(test_file).stem
        run(testscript=test_file, taskid=test_name, max_runtime=21600)
