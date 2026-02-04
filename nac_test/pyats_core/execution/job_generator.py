# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""PyATS job file generation functionality."""

import json
import textwrap
from pathlib import Path
from typing import Any

from nac_test.pyats_core.constants import DEFAULT_TEST_TIMEOUT


class JobGenerator:
    """Generates PyATS job files for test execution."""

    def __init__(self, max_workers: int, output_dir: Path):
        """Initialize job generator.

        Args:
            max_workers: Maximum number of parallel workers
            output_dir: Directory for output files
        """
        self.max_workers = max_workers
        self.output_dir = Path(output_dir)

    def generate_job_file_content(self, test_files: list[Path]) -> str:
        """Generate the content for a PyATS job file for API tests.

        This method is used for API tests (standard execution mode) where tests
        call management APIs and don't directly connect to network devices.

        The testbed parameter is passed to run() for consistency and to support
        future extensions, even though API tests typically don't require device
        connections or Genie parsers.

        Args:
            test_files: List of API test files to include in the job

        Returns:
            Job file content as a string
        """
        # Convert all paths to absolute to be cwd-agnostic in the job process
        test_files_str = ",\n        ".join(
            [f'"{str(Path(tf).resolve())}"' for tf in test_files]
        )

        job_content = textwrap.dedent(f'''
        """Auto-generated PyATS job file by nac-test"""

        import os
        from pathlib import Path
        from pyats.easypy import run

        # Test files to execute
        TEST_FILES = [
            {test_files_str}
        ]

        def main(runtime):
            """Main job file entry point"""
            # Set max workers
            runtime.max_workers = {self.max_workers}

            # Note: runtime.directory is read-only and set by --archive-dir
            # The output directory is: {str(self.output_dir)}

            # Run all test files
            for idx, test_file in enumerate(TEST_FILES):
                # Create meaningful task ID from test file name
                # e.g., "epg_attributes.py" -> "epg_attributes"
                test_name = Path(test_file).stem
                run(
                    testscript=test_file,
                    taskid=test_name,
                    max_runtime={DEFAULT_TEST_TIMEOUT},
                    testbed=runtime.testbed
                )
        ''')

        return job_content

    def generate_device_centric_job(
        self, device: dict[str, Any], test_files: list[Path]
    ) -> str:
        """Generate PyATS job file content for device-centric D2D/SSH tests.

        This method is used for D2D (device-to-device) tests where tests directly
        connect to network devices via SSH. These tests are executed in device-centric
        mode with connection broker support for connection pooling and command caching.

        The testbed parameter is passed to run() to provide access to device metadata
        and enable Genie parsers for command output parsing. The connection broker
        (when active) takes priority for actual device connections, but the testbed
        remains available for parser support.

        This job file sets up the environment for SSH tests to run against a single device.
        It ensures the SSHTestBase has access to device info and the data model.

        Args:
            device: Device dictionary with connection information
            test_files: List of D2D/SSH test files to run on this device

        Returns:
            Job file content as a string
        """
        hostname = device["hostname"]  # Required field per nac-test contract
        # Use absolute paths so device-centric jobs are independent of cwd
        test_files_str = ",\n        ".join(
            [f'"{str(Path(tf).resolve())}"' for tf in test_files]
        )

        job_content = textwrap.dedent(f'''
        """Auto-generated PyATS job file for device {hostname}"""

        import json
        import logging
        import os
        import re
        from pathlib import Path
        from pyats.easypy import run
        from nac_test.pyats_core.ssh.connection_manager import DeviceConnectionManager

        # Device being tested (using hostname)
        HOSTNAME = "{hostname}"
        DEVICE_INFO = {json.dumps(device)}

        # Test files to execute
        TEST_FILES = [
            {test_files_str}
        ]

        def main(runtime):
            """Main job file entry point for device-centric execution"""
            # Set up environment variables that SSHTestBase expects
            os.environ['DEVICE_INFO'] = json.dumps(DEVICE_INFO)

            # Create and attach connection manager to runtime
            # This will be shared across all tests for this device
            runtime.connection_manager = DeviceConnectionManager(max_concurrent=1)

            # Sanitize hostname for taskid (replace non-alphanumeric with underscore and lowercase)
            safe_hostname = re.sub(r'[^a-zA-Z0-9_]', '_', HOSTNAME).lower()

            # Run all test files for this device
            for idx, test_file in enumerate(TEST_FILES):
                # Create meaningful task ID from test file name and hostname
                test_name = Path(test_file).stem
                run(
                    testscript=test_file,
                    taskid=f"{{safe_hostname}}_{{test_name}}",
                    hostname=HOSTNAME,  # Pass original hostname for progress reporting
                    max_runtime={DEFAULT_TEST_TIMEOUT},
                    testbed=runtime.testbed
                )
        ''')

        return job_content
