# -*- coding: utf-8 -*-

"""Main PyATS orchestration logic for nac-test."""

from pathlib import Path
import os
import sys
import tempfile
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import asyncio

from nac_test.pyats.constants import (
    DEFAULT_CPU_MULTIPLIER,
    MEMORY_PER_WORKER_GB,
    MAX_WORKERS_HARD_LIMIT,
)
from nac_test.pyats.discovery import TestDiscovery, DeviceInventoryDiscovery
from nac_test.pyats.execution import JobGenerator, SubprocessRunner, OutputProcessor
from nac_test.pyats.execution.device import DeviceExecutor
from nac_test.data_merger import DataMerger
from nac_test.pyats.progress import ProgressReporter
from nac_test.pyats.reporting.multi_archive_generator import MultiArchiveReportGenerator
from nac_test.pyats.reporting.summary_printer import SummaryPrinter
from nac_test.pyats.reporting.utils.archive_inspector import ArchiveInspector
from nac_test.pyats.reporting.utils.archive_aggregator import ArchiveAggregator
from nac_test.utils.system_resources import SystemResourceCalculator
from nac_test.utils.terminal import terminal
from nac_test.utils.environment import EnvironmentValidator


logger = logging.getLogger(__name__)


class PyATSOrchestrator:
    """Orchestrates PyATS test execution with dynamic resource management."""

    def __init__(
        self,
        data_paths: List[Path],
        test_dir: Path,
        output_dir: Path,
        merged_data_filename: str,
    ):
        """Initialize the PyATS orchestrator.

        Args:
            data_paths: List of paths to data model YAML files
            test_dir: Directory containing PyATS test files
            output_dir: Directory for test output
            merged_data_filename: Name of the merged data model file
        """
        self.data_paths = data_paths
        self.test_dir = Path(test_dir)
        self.output_dir = Path(output_dir)
        self.merged_data_filename = merged_data_filename

        # Track test status by type for combined summary
        self.api_test_status: Dict[str, Dict[str, Any]] = {}
        self.d2d_test_status: Dict[str, Dict[str, Any]] = {}
        self.overall_start_time: Optional[datetime] = None

        # Calculate max workers based on system resources
        self.max_workers = self._calculate_workers()

        # Device parallelism for SSH/D2D tests (can be overridden via CLI)
        self.max_parallel_devices: Optional[int] = None

        # Note: ProgressReporter will be initialized later with total test count

        # Initialize discovery components
        self.test_discovery = TestDiscovery(self.test_dir)
        self.device_inventory_discovery = DeviceInventoryDiscovery(
            self.output_dir, self.merged_data_filename
        )

        # Initialize execution components
        self.job_generator = JobGenerator(self.max_workers, self.output_dir)
        self.output_processor = (
            None  # Will be initialized when progress reporter is ready
        )
        self.subprocess_runner = (
            None  # Will be initialized when output processor is ready
        )
        self.device_executor = None  # Will be initialized when needed

        # Initialize reporting components
        self.summary_printer = SummaryPrinter()

    def _calculate_workers(self) -> int:
        """Calculate optimal worker count based on CPU, memory, and test type"""
        cpu_workers = SystemResourceCalculator.calculate_worker_capacity(
            memory_per_worker_gb=MEMORY_PER_WORKER_GB,
            cpu_multiplier=DEFAULT_CPU_MULTIPLIER,
            max_workers=MAX_WORKERS_HARD_LIMIT,
            env_var="PYATS_MAX_WORKERS",
        )

        return cpu_workers

    async def _execute_api_tests_standard(
        self, test_files: List[Path]
    ) -> Optional[Path]:
        """
        Execute API tests using the standard PyATS job file approach.

        Args:
            test_files: List of API test files to execute

        Returns:
            Path to the generated archive file, or None if execution fails
        """
        logger.info(
            f"Executing {len(test_files)} API tests using standard PyATS job execution"
        )

        if not test_files:
            logger.warning("No test files provided for API tests")
            return None

        job_content = self.job_generator.generate_job_file_content(test_files)
        job_file_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix="_api_job.py", delete=False
            ) as f:
                f.write(job_content)
                job_file_path = Path(f.name)

            # Set up environment for the API test job
            env = os.environ.copy()
            env["PYTHONWARNINGS"] = "ignore::UserWarning"
            env["PYATS_LOG_LEVEL"] = "ERROR"
            env["HTTPX_LOG_LEVEL"] = "ERROR"
            env["DATA_FILE"] = str(self.output_dir / self.merged_data_filename)
            test_parent_dir = str(self.test_dir)
            nac_test_dir = str(Path(__file__).parent.parent.parent)
            if "PYTHONPATH" in env:
                env["PYTHONPATH"] = (
                    f"{test_parent_dir}{os.pathsep}{nac_test_dir}{os.pathsep}{env['PYTHONPATH']}"
                )
            else:
                env["PYTHONPATH"] = f"{test_parent_dir}{os.pathsep}{nac_test_dir}"

            # Execute and return the archive path
            assert self.subprocess_runner is not None  # Should be initialized by now
            archive_path = await self.subprocess_runner.execute_job(job_file_path, env)

            # If successful, rename archive to include _api_ identifier
            if archive_path and archive_path.exists():
                api_archive_path = archive_path.parent / archive_path.name.replace(
                    "nac_test_job_", "nac_test_job_api_"
                )
                archive_path.rename(api_archive_path)
                logger.info(f"API test archive created: {api_archive_path}")
                return api_archive_path

            return archive_path

        finally:
            # Clean up the temporary job file
            if job_file_path and os.path.exists(job_file_path):
                os.unlink(job_file_path)

    async def _execute_ssh_tests_device_centric(
        self, test_files: List[Path], devices: List[Dict[str, Any]]
    ) -> Optional[Path]:
        """
        Run tests in device-centric mode for SSH.

        This method iterates through each device from the inventory and launches a
        dedicated PyATS job subprocess for it, managed by a semaphore to
        control concurrency.

        Args:
            test_files: List of SSH test files to execute
            devices: List of device dictionaries from inventory

        Returns:
            Path to the aggregated D2D archive file, or None if no tests were executed
        """
        logger.info(
            f"Executing {len(test_files)} SSH tests using device-centric execution"
        )

        # Devices are passed from the orchestration level
        if not devices:
            # This shouldn't happen since we check before calling, but keep as safety
            logger.error("No devices provided for D2D test execution")
            return None

        # Initialize device executor if not already done
        if self.device_executor is None:
            assert self.subprocess_runner is not None  # Should be initialized
            self.device_executor = DeviceExecutor(
                self.job_generator, self.subprocess_runner, self.test_status
            )

        # Note: Progress reporter is already initialized at orchestration level
        # with the correct total_operations count

        # Track individual device archives for aggregation
        device_archives = []

        # Determine batch size: use max_workers by default, cap with max_parallel_devices if specified
        batch_size = self.max_workers
        if self.max_parallel_devices is not None:
            batch_size = min(self.max_workers, self.max_parallel_devices)
            logger.info(
                f"Using user-specified device parallelism cap: {self.max_parallel_devices} (system capacity: {self.max_workers})"
            )
        else:
            logger.info(f"Using system-calculated device parallelism: {batch_size}")

        # Batch devices based on calculated batch size
        device_batches = [
            devices[i : i + batch_size] for i in range(0, len(devices), batch_size)
        ]

        logger.info(
            f"Processing {len(devices)} devices in {len(device_batches)} batches (batch size: {batch_size})"
        )

        # Process each batch sequentially, but devices within batch in parallel
        for batch_idx, device_batch in enumerate(device_batches):
            logger.info(
                f"Processing batch {batch_idx + 1}/{len(device_batches)} with {len(device_batch)} devices"
            )

            # Create tasks for all devices in this batch
            # Use min of max_workers and batch size for semaphore
            semaphore_size = min(self.max_workers, len(device_batch))
            semaphore = asyncio.Semaphore(semaphore_size)
            tasks = [
                self.device_executor.run_device_job_with_semaphore(
                    device, test_files, semaphore
                )
                for device in device_batch
            ]

            # Wait for all devices in this batch to complete and collect archives
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect successful archives
            for result in batch_results:
                if isinstance(result, Path) and result.exists():
                    device_archives.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Device execution failed with error: {result}")

            logger.info(f"Completed batch {batch_idx + 1}/{len(device_batches)}")

        # Copy test status to d2d_test_status for combined reporting
        if hasattr(self, "d2d_test_status"):
            self.d2d_test_status.update(self.test_status)

        # Print summary for D2D tests
        start_time = (
            self.overall_start_time
            if hasattr(self, "overall_start_time") and self.overall_start_time
            else getattr(self, "start_time", datetime.now())
        )
        self.summary_printer.print_summary(
            self.test_status,
            start_time,
            output_dir=self.output_dir,
            archive_path=None,  # Archive will be created after this
            api_test_status=getattr(self, "api_test_status", None),
            d2d_test_status=getattr(self, "d2d_test_status", None),
            overall_start_time=self.overall_start_time,
        )

        # Aggregate all device archives into a single D2D archive
        if device_archives:
            aggregated_archive = await ArchiveAggregator.aggregate_device_archives(
                device_archives, self.output_dir
            )
            return aggregated_archive
        else:
            logger.warning("No device archives were generated")
            return None

    def validate_environment(self) -> None:
        """Pre-flight check: Validate required environment variables before running tests.

        This ensures we fail fast with clear error messages rather than starting
        PyATS only to have all tests fail due to missing configuration.

        Raises:
            SystemExit: If required environment variables are missing
        """
        # Get controller type (defaults to ACI in the MVP)
        controller_type = os.environ.get("CONTROLLER_TYPE", "ACI")

        EnvironmentValidator.validate_controller_env(controller_type)

    def run_tests(self) -> None:
        """Main entry point - triggers the async execution flow."""
        # This is the synchronous entry point that kicks off the async orchestration
        try:
            asyncio.run(self._run_tests_async())
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during test orchestration: {e}",
                exc_info=True,
            )

    async def _run_tests_async(self):
        """Main async orchestration logic."""
        # Track overall start time for combined summary
        self.overall_start_time = datetime.now()

        # Pre-flight check and setup
        self.validate_environment()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        merged_data = DataMerger.merge_data_files(self.data_paths)
        DataMerger.write_merged_data_model(
            merged_data, self.output_dir, self.merged_data_filename
        )

        # Test Discovery
        test_files, skipped_files = self.test_discovery.discover_pyats_tests()

        if not test_files:
            print("No PyATS test files (*.py) found in test directory")
            return

        print(f"Discovered {len(test_files)} PyATS test files")
        print(f"Running with {self.max_workers} parallel workers")

        # Categorize tests by type (api/ vs d2d/)
        try:
            api_tests, d2d_tests = self.test_discovery.categorize_tests_by_type(
                test_files
            )
        except ValueError as e:
            print(terminal.error(str(e)))
            sys.exit(1)

        # Initialize progress reporter for output formatting
        self.progress_reporter = ProgressReporter(
            total_tests=len(test_files), max_workers=self.max_workers
        )
        self.test_status = {}
        self.start_time = datetime.now()

        # Set the test_status reference in progress reporter
        self.progress_reporter.test_status = self.test_status

        # Initialize execution components now that progress reporter is ready
        self.output_processor = OutputProcessor(
            self.progress_reporter, self.test_status
        )
        self.subprocess_runner = SubprocessRunner(
            self.output_dir, output_handler=self.output_processor.process_line
        )

        # Execute tests based on their type
        tasks = []

        if api_tests:
            print(f"Found {len(api_tests)} API test(s) - using standard execution")
            tasks.append(self._execute_api_tests_standard(api_tests))

        if d2d_tests:
            # Get device inventory for D2D tests
            devices = self.device_inventory_discovery.get_device_inventory(d2d_tests)

            if devices:
                print(
                    f"Found {len(d2d_tests)} D2D test(s) - using device-centric execution"
                )
                tasks.append(self._execute_ssh_tests_device_centric(d2d_tests, devices))
            else:
                print(
                    terminal.warning(
                        "No devices found in inventory. D2D tests will be skipped."
                    )
                )

        # Run all test types in parallel
        if tasks:
            await asyncio.gather(*tasks)
        else:
            print("No tests to execute after categorization")

        # Print summary after all tests complete
        if hasattr(self, "test_status") and self.test_status:
            # Combine all test statuses for summary
            combined_status = {}
            if hasattr(self, "api_test_status"):
                combined_status.update(self.api_test_status)
            if hasattr(self, "d2d_test_status"):
                combined_status.update(self.d2d_test_status)
            if not combined_status:
                combined_status = self.test_status

            # Print the summary
            self.summary_printer.print_summary(
                combined_status,
                self.start_time,
                output_dir=self.output_dir,
                archive_path=None,
                api_test_status=getattr(self, "api_test_status", None),
                d2d_test_status=getattr(self, "d2d_test_status", None),
                overall_start_time=self.overall_start_time,
            )

        # Generate HTML reports after all test types have completed
        await self._generate_html_reports_async()

    async def _generate_html_reports_async(self) -> None:
        """Generate HTML reports asynchronously from collected archives.

        This method handles multiple archives (API and D2D) using the
        MultiArchiveReportGenerator for proper report organization and
        combined summary generation.
        """

        # Use ArchiveInspector to find all archives
        archives = ArchiveInspector.find_archives(self.output_dir)

        # Collect the latest archive of each type
        archive_paths = []
        archive_info = []  # Store archive info for display later

        if archives["api"]:
            archive_paths.append(archives["api"][0])
            archive_info.append(f"Found API archive: {archives['api'][0].name}")

        if archives["d2d"]:
            archive_paths.append(archives["d2d"][0])
            archive_info.append(f"Found D2D archive: {archives['d2d'][0].name}")

        if not archive_paths and archives["legacy"]:
            # Fallback to legacy archives for backward compatibility
            archive_paths.append(archives["legacy"][0])
            archive_info.append(f"Found legacy archive: {archives['legacy'][0].name}")

        if not archive_paths:
            print("No PyATS job archives found to generate reports from.")
            return

        print(f"\nGenerating reports from {len(archive_paths)} archive(s)...")

        # Use MultiArchiveReportGenerator for all cases (handles single archive too)
        generator = MultiArchiveReportGenerator(self.output_dir)
        result = await generator.generate_reports_from_archives(archive_paths)

        if result["status"] in ["success", "partial"]:
            print(f"Total report generation time: {result['duration']:.2f} seconds")

            # Print archive info at the bottom
            for info in archive_info:
                print(info)

            # Display results based on what was generated
            print(f"\n{terminal.info('HTML Reports Generated:')}")
            print("=" * 80)

            if result.get("combined_summary"):
                # Multiple archives - show combined summary
                print(f"{'Combined Summary:'} {result['combined_summary']}")

                # Show individual report directories
                for archive_type, archive_result in result["results"].items():
                    if archive_result.get("status") == "success":
                        report_dir = archive_result.get("report_dir", "")
                        print(f"{f'{archive_type.upper()} Reports:'}   {report_dir}")
            else:
                # Single archive - show its report location
                for archive_type, archive_result in result["results"].items():
                    if archive_result.get("status") == "success":
                        report_dir = Path(archive_result.get("report_dir", ""))
                        summary_report = report_dir / "summary_report.html"

                        print(f"{'Summary Report:'} {summary_report}")
                        print(f"{'All Reports:'}    {report_dir}")
                        break

            # Report any failures
            failed_archives = [
                k for k, v in result["results"].items() if v.get("status") != "success"
            ]
            if failed_archives:
                print(
                    f"\n{terminal.warning('Warning:')} Failed to process archives: {', '.join(failed_archives)}"
                )
        else:
            print(f"\n{terminal.error('Failed to generate reports')}")
            if result.get("error"):
                print(f"Error: {result['error']}")
