# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""PyATS job file generation functionality."""

import json
import logging
import textwrap
from pathlib import Path
from typing import Any

from nac_test.pyats_core.constants import DEFAULT_TEST_TIMEOUT
from nac_test.utils.logging import VERBOSITY_TO_LOGLEVEL, VerbosityLevel


class JobGenerator:
    """Generates PyATS job files for test execution."""

    def __init__(
        self,
        max_workers: int,
        output_dir: Path,
        verbosity: VerbosityLevel = VerbosityLevel.WARNING,
    ):
        """Initialize job generator.

        Args:
            max_workers: Maximum number of parallel workers
            output_dir: Directory for output files
            verbosity: Verbosity level for aetest logging
        """
        self.max_workers = max_workers
        self.output_dir = Path(output_dir)
        self.verbosity = verbosity
        self.loglevel = VERBOSITY_TO_LOGLEVEL.get(verbosity, logging.WARNING)

    def generate_job_file_content(self, test_files: list[Path]) -> str:
        """Generate the content for a PyATS job file for API tests.

        This method is used for API tests (standard execution mode) where tests
        call management APIs and don't directly connect to network devices.

        The testbed parameter is passed to run() for consistency and to support
        future extensions, even though API tests typically don't require device
        connections or Genie parsers.

        Note: We set managed_handlers.screen.setLevel() directly in the generated
        job file because other approaches don't work:
        - logging.getLogger('pyats.aetest').setLevel() gets overwritten by aetest's configure_logging()
        - loglevel param to run() gets overwritten by CLI argument parsing

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
        from pyats.log import managed_handlers

        TEST_FILES = [
            {test_files_str}
        ]

        def main(runtime):
            runtime.max_workers = {self.max_workers}
            managed_handlers.screen.setLevel({self.loglevel})

            for idx, test_file in enumerate(TEST_FILES):
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

        Note: We set managed_handlers.screen.setLevel() directly in the generated
        job file because other approaches don't work:
        - logging.getLogger('pyats.aetest').setLevel() gets overwritten by aetest's configure_logging()
        - loglevel param to run() gets overwritten by CLI argument parsing

        Args:
            device: Device dictionary with connection information
            test_files: List of D2D/SSH test files to run on this device

        Returns:
            Job file content as a string
        """
        hostname = device["hostname"]
        test_files_str = ",\n        ".join(
            [f'"{str(Path(tf).resolve())}"' for tf in test_files]
        )

        job_content = textwrap.dedent(f'''
        """Auto-generated PyATS job file for device {hostname}"""

        import json
        import os
        from pathlib import Path
        from pyats.easypy import run
        from pyats.log import managed_handlers
        from nac_test.pyats_core.ssh.connection_manager import DeviceConnectionManager
        from nac_test.utils import sanitize_hostname

        HOSTNAME = "{hostname}"
        DEVICE_INFO = {json.dumps(device)}

        TEST_FILES = [
            {test_files_str}
        ]

        def main(runtime):
            os.environ['DEVICE_INFO'] = json.dumps(DEVICE_INFO)
            managed_handlers.screen.setLevel({self.loglevel})
            runtime.connection_manager = DeviceConnectionManager(max_concurrent=1)
            safe_hostname = sanitize_hostname(HOSTNAME)

            for idx, test_file in enumerate(TEST_FILES):
                test_name = Path(test_file).stem
                run(
                    testscript=test_file,
                    taskid=f"{{safe_hostname}}_{{test_name}}",
                    hostname=HOSTNAME,
                    max_runtime={DEFAULT_TEST_TIMEOUT},
                    testbed=runtime.testbed
                )
        ''')

        return job_content
