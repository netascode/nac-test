"""
Job file to run the step data bug reproduction test.

Run with:
    uv run pyats run job job.py --testbed-file empty_testbed.yaml
"""

import os
from pyats.easypy import run


def main(runtime):
    """Run the test script."""
    testscript = os.path.join(os.path.dirname(__file__), "test_step_data_bug.py")
    run(testscript=testscript, runtime=runtime)
