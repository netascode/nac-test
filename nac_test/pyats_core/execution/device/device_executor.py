# -*- coding: utf-8 -*-

"""Device-centric test execution functionality."""

import asyncio
import tempfile
import logging
from pathlib import Path
from typing import List, Any, Optional
import os

from .testbed_generator import TestbedGenerator
from nac_test.utils.path_setup import get_pythonpath_for_tests
from nac_test.pyats_core.execution.subprocess_runner import SubprocessRunner
from nac_test.pyats_core.execution.job_generator import JobGenerator

logger = logging.getLogger(__name__)


class DeviceExecutor:
    """Handles device-centric test execution."""

    def __init__(
        self,
        job_generator: JobGenerator,
        subprocess_runner: SubprocessRunner,
        test_status: dict[str, Any],
        test_dir: Path,
    ):
        """Initialize device executor.

        Args:
            job_generator: JobGenerator instance for creating job files
            subprocess_runner: SubprocessRunner instance for executing jobs
            test_status: Dictionary for tracking test status
            test_dir: Directory containing PyATS test files (user-specified)
        """
        self.job_generator = job_generator
        self.subprocess_runner = subprocess_runner
        self.test_status = test_status
        self.test_dir = test_dir

    async def run_device_job_with_semaphore(
        self,
        device: dict[str, Any],
        test_files: List[Path],
        semaphore: asyncio.Semaphore,
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
                # Always start with a copy of os.environ to preserve PATH and other variables
                env = os.environ.copy()
                nac_test_dir = Path(
                    __file__
                ).parent.parent.parent.parent  # nac-test root
                env.update(
                    {
                        "HOSTNAME": hostname,
                        "DEVICE_INFO": str(device),  # Will be loaded by the job file
                        # Environment variables are used because PyATS tests run as separate subprocess processes.
                        # The merged data file is created by main.py at the base output level.
                        "DATA_MODEL_PATH": str(
                            self.subprocess_runner.output_dir.parent
                            / "merged_data_model_test_variables.yaml"
                        ),
                        "PYTHONPATH": get_pythonpath_for_tests(
                            self.test_dir, [nac_test_dir]
                        ),
                    }
                )

                # Track test status for this device
                for test_file in test_files:
                    test_name = f"{hostname}::{test_file.stem}"
                    self.test_status[test_name] = {
                        "status": "pending",
                        "device": hostname,
                        "test_file": str(test_file),
                    }

                # FIXME: TEMP DEBUG: Print environment and command for D2D/SSH subprocess -- REMOVE ME AFTER TESTING
                # print("=== D2D/SSH SUBPROCESS ENV ===")
                # print("sys.executable:", sys.executable)
                # print("os.getcwd():", os.getcwd())
                # print("env['PATH']:", env.get('PATH'))
                # print("env['PYTHONPATH']:", env.get('PYTHONPATH'))
                # print("env:", env)
                # print("cmd: pyats run job ...", job_file_path, testbed_file_path)

                # # TEMP DEBUG: Print test_dir and PYTHONPATH for D2D/SSH subprocess
                # print(f"D2D/SSH DEBUG: self.test_dir = {self.test_dir}")
                # print(f"D2D/SSH DEBUG: PYTHONPATH = {env['PYTHONPATH']}")

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

                # Clean up temporary files -- UNCOMMENT ME
                # try:
                #     job_file_path.unlink()
                #     testbed_file_path.unlink()
                # except Exception:
                #     pass

                if archive_path:
                    logger.info(
                        f"Completed tests for device {hostname}: {archive_path}"
                    )
                else:
                    logger.error(f"Failed to run tests for device {hostname}")

                return Path(archive_path) if archive_path else None

            except Exception as e:
                logger.error(f"Error running tests for device {hostname}: {e}")

                # Mark all tests as errored
                for test_file in test_files:
                    test_name = f"{hostname}::{test_file.stem}"
                    if test_name in self.test_status:
                        self.test_status[test_name]["status"] = "errored"
                        self.test_status[test_name]["error"] = str(e)

                return None
