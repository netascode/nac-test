# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt


"""Auto-generated PyATS job file by nac-test"""

import os
from pathlib import Path
from pyats.easypy import run

# Test files to execute
TEST_FILES = [
    "/Users/oboehmer/Documents/DD/nac-test/workspace/scale/templates/tests/verify_sdwan_sync.py",
    "/Users/oboehmer/Documents/DD/nac-test/workspace/scale/templates/tests/verify_sdwan_sync_01.py",
    "/Users/oboehmer/Documents/DD/nac-test/workspace/scale/templates/tests/verify_sdwan_sync_02.py",
    "/Users/oboehmer/Documents/DD/nac-test/workspace/scale/templates/tests/verify_sdwan_sync_03.py",
    "/Users/oboehmer/Documents/DD/nac-test/workspace/scale/templates/tests/verify_sdwan_sync_04.py",
    "/Users/oboehmer/Documents/DD/nac-test/workspace/scale/templates/tests/verify_sdwan_sync_05.py",
    "/Users/oboehmer/Documents/DD/nac-test/workspace/scale/templates/tests/verify_sdwan_sync_06.py",
    "/Users/oboehmer/Documents/DD/nac-test/workspace/scale/templates/tests/verify_sdwan_sync_07.py",
    "/Users/oboehmer/Documents/DD/nac-test/workspace/scale/templates/tests/verify_sdwan_sync_08.py",
    "/Users/oboehmer/Documents/DD/nac-test/workspace/scale/templates/tests/verify_sdwan_sync_09.py",
    "/Users/oboehmer/Documents/DD/nac-test/workspace/scale/templates/tests/verify_sdwan_sync_10.py",
]


def main(runtime):
    """Main job file entry point"""
    # Set max workers
    runtime.max_workers = 1

    # Note: runtime.directory is read-only and set by --archive-dir
    # The output directory is: /Users/oboehmer/Documents/DD/nac-test/workspace/scale/results_original/pyats_results

    # Run all test files
    for idx, test_file in enumerate(TEST_FILES):
        # Create meaningful task ID from test file name
        # e.g., "epg_attributes.py" -> "epg_attributes"
        test_name = Path(test_file).stem
        run(
            testscript=test_file,
            taskid=test_name,
            max_runtime=21600,
            testbed=runtime.testbed,
        )
