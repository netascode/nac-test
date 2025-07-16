# -*- coding: utf-8 -*-

"""Device-centric test execution functionality."""

import asyncio
import tempfile
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from .testbed_generator import TestbedGenerator

logger = logging.getLogger(__name__)


class DeviceExecutor:
    """Handles device-centric test execution."""

    def __init__(self, job_generator, subprocess_runner, test_status: Dict[str, Any]):
        """Initialize device executor.

        Args:
            job_generator: JobGenerator instance for creating job files
            subprocess_runner: SubprocessRunner instance for executing jobs
            test_status: Dictionary for tracking test status
        """
        self.job_generator = job_generator
        self.subprocess_runner = subprocess_runner
        self.test_status = test_status

    async def run_device_job_with_semaphore(
        self, device: Dict, test_files: List[Path], semaphore: asyncio.Semaphore
    ) -> Optional[Path]:
        """Run PyATS tests for a specific device with semaphore control.

        This method:
        1. Acquires a semaphore slot to limit concurrent device testing
        2. Generates a device-specific job file
        3. Generates a testbed YAML for the device
        4. Executes the tests via subprocess
        5. Returns the path to the device's test archive

        Args:
            device: Device dictionary with connection info
            test_files: List of test files to run
            semaphore: Asyncio semaphore for concurrency control

        Returns:
            Path to the device's test archive if successful, None otherwise
        """
        hostname = device["hostname"]  # Required field per nac-test contract

        async with semaphore:
            logger.info(f"Starting tests for device {hostname}")

            try:
                # Create temporary files for job and testbed
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".py", delete=False
                ) as job_file:
                    job_content = self.job_generator.generate_device_centric_job(
                        device, test_files
                    )
                    job_file.write(job_content)
                    job_file_path = Path(job_file.name)

                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".yaml", delete=False
                ) as testbed_file:
                    testbed_content = TestbedGenerator.generate_testbed_yaml(device)
                    testbed_file.write(testbed_content)
                    testbed_file_path = Path(testbed_file.name)

                # Set up environment for this device
                env = {
                    "HOSTNAME": hostname,
                    "DEVICE_INFO": str(device),  # Will be loaded by the job file
                    "DATA_MODEL_PATH": str(
                        self.subprocess_runner.output_dir / "merged_data.yaml"
                    ),
                }

                # Track test status for this device
                for test_file in test_files:
                    test_name = f"{hostname}::{test_file.stem}"
                    self.test_status[test_name] = {
                        "status": "pending",
                        "device": hostname,
                        "test_file": str(test_file),
                    }

                # Execute the job with testbed
                archive_path = await self.subprocess_runner.execute_job_with_testbed(
                    job_file_path, testbed_file_path, env
                )

                # Update test status based on result
                status = "passed" if archive_path else "failed"
                for test_file in test_files:
                    test_name = f"{hostname}::{test_file.stem}"
                    if test_name in self.test_status:
                        self.test_status[test_name]["status"] = status

                # Clean up temporary files
                try:
                    job_file_path.unlink()
                    testbed_file_path.unlink()
                except Exception:
                    pass

                if archive_path:
                    logger.info(
                        f"Completed tests for device {hostname}: {archive_path}"
                    )
                else:
                    logger.error(f"Failed to run tests for device {hostname}")

                return archive_path

            except Exception as e:
                logger.error(f"Error running tests for device {hostname}: {e}")

                # Mark all tests as errored
                for test_file in test_files:
                    test_name = f"{hostname}::{test_file.stem}"
                    if test_name in self.test_status:
                        self.test_status[test_name]["status"] = "errored"
                        self.test_status[test_name]["error"] = str(e)

                return None
