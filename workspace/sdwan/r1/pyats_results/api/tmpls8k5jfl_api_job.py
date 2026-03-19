
"""Auto-generated PyATS job file by nac-test"""

import os
from pathlib import Path
from pyats.easypy import run

# Test files to execute
TEST_FILES = [
    "/Users/oboehmer/Documents/DD/nac-test/workspace/sdwan/api-tests/tests/verify_sdwan_sync.py"
]

def main(runtime):
    """Main job file entry point"""
    # Set max workers
    runtime.max_workers = 19

    # Note: runtime.directory is read-only and set by --archive-dir
    # The output directory is: /Users/oboehmer/Documents/DD/nac-test/workspace/sdwan/r1/pyats_results

    # Run all test files
    for idx, test_file in enumerate(TEST_FILES):
        # Create meaningful task ID from test file name
        # e.g., "epg_attributes.py" -> "epg_attributes"
        test_name = Path(test_file).stem
        run(
            testscript=test_file,
            taskid=test_name,
            max_runtime=21600,
            testbed=runtime.testbed
        )
