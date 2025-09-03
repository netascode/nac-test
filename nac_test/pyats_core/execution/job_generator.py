# -*- coding: utf-8 -*-

"""PyATS job file generation functionality."""

from pathlib import Path
from typing import List, Dict, Any
import textwrap
import json

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

    def generate_job_file_content(self, test_files: List[Path]) -> str:
        """Generate the content for a PyATS job file.

        Args:
            test_files: List of test files to include in the job

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
                runtime.tasks.run(
                    testscript=test_file,
                    taskid=test_name,
                    max_runtime={DEFAULT_TEST_TIMEOUT}
                )
        ''')

        return job_content

    def generate_device_centric_job(
        self, device: Dict[str, Any], test_files: List[Path]
    ) -> str:
        """Generate PyATS job file content for a specific device.

        This job file sets up the environment for SSH tests to run against a single device.
        It ensures the SSHTestBase has access to device info and the data model.

        Args:
            device: Device dictionary with connection information
            test_files: List of test files to run on this device

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
        
        import os
        import json
        from pathlib import Path
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
            
            # Run all test files for this device
            for idx, test_file in enumerate(TEST_FILES):
                # Create meaningful task ID from test file name and hostname
                # e.g., "router1_epg_attributes"
                test_name = Path(test_file).stem
                runtime.tasks.run(
                    testscript=test_file,
                    taskid=f"{{HOSTNAME}}_{{test_name}}",
                    max_runtime={DEFAULT_TEST_TIMEOUT}
                )
        ''')

        return job_content
