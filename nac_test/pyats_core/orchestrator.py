# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Main PyATS orchestration logic for nac-test."""

import asyncio
import logging
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from nac_test.pyats_core.broker.connection_broker import ConnectionBroker
from nac_test.pyats_core.constants import (
    DEFAULT_CPU_MULTIPLIER,
    MAX_WORKERS_HARD_LIMIT,
    MEMORY_PER_WORKER_GB,
)
from nac_test.pyats_core.discovery import DeviceInventoryDiscovery, TestDiscovery
from nac_test.pyats_core.execution import (
    JobGenerator,
    OutputProcessor,
    SubprocessRunner,
)
from nac_test.pyats_core.execution.device import DeviceExecutor
from nac_test.pyats_core.execution.device.testbed_generator import TestbedGenerator
from nac_test.pyats_core.progress import ProgressReporter
from nac_test.pyats_core.reporting.multi_archive_generator import (
    MultiArchiveReportGenerator,
)
from nac_test.pyats_core.reporting.summary_printer import SummaryPrinter
from nac_test.pyats_core.reporting.utils.archive_aggregator import ArchiveAggregator
from nac_test.pyats_core.reporting.utils.archive_inspector import ArchiveInspector
from nac_test.utils.cleanup import cleanup_old_test_outputs, cleanup_pyats_runtime
from nac_test.utils.controller import detect_controller_type
from nac_test.utils.environment import EnvironmentValidator
from nac_test.utils.path_setup import get_pythonpath_for_tests
from nac_test.utils.system_resources import SystemResourceCalculator
from nac_test.utils.terminal import terminal

logger = logging.getLogger(__name__)


class PyATSOrchestrator:
    """Orchestrates PyATS test execution with dynamic resource management."""

    def __init__(
        self,
        data_paths: list[Path],
        test_dir: Path,
        output_dir: Path,
        merged_data_filename: str,
        minimal_reports: bool = False,
        controller_type: str | None = None,
    ):
        """Initialize the PyATS orchestrator.

        Args:
            data_paths: List of paths to data model YAML files
            test_dir: Directory containing PyATS test files
            output_dir: Base output directory (orchestrator creates pyats_results subdirectory)
            merged_data_filename: Name of the merged data model file
            minimal_reports: Only include command outputs for failed/errored tests in reports
            controller_type: The detected controller type (e.g., "ACI", "SDWAN", "CC").
                If not provided, will be detected automatically.
        """
        self.data_paths = data_paths
        self.test_dir = Path(test_dir).resolve()
        self.base_output_dir = Path(
            output_dir
        ).resolve()  # Store base directory for merged data file access (absolute)
        self.output_dir = (
            self.base_output_dir / "pyats_results"
        )  # PyATS works in its own subdirectory
        self.merged_data_filename = merged_data_filename
        self.minimal_reports = minimal_reports

        # Track test status by type for combined summary
        self.api_test_status: dict[str, dict[str, Any]] = {}
        self.d2d_test_status: dict[str, dict[str, Any]] = {}
        self.overall_start_time: datetime | None = None

        # Use provided controller type or detect it
        if controller_type:
            # Controller type provided by caller (e.g., CombinedOrchestrator)
            self.controller_type = controller_type
            logger.info(f"Using provided controller type: {self.controller_type}")
        else:
            # Fallback to auto-detection for standalone usage
            try:
                self.controller_type = detect_controller_type()
                logger.info(f"Controller type detected: {self.controller_type}")
            except ValueError as e:
                # Exit gracefully if controller detection fails
                logger.error(f"Controller detection failed: {e}")
                print(terminal.error(f"Controller detection failed:\n{e}"))
                sys.exit(1)

        # Calculate max workers based on system resources
        self.max_workers = self._calculate_workers()

        # Device parallelism for SSH/D2D tests (can be overridden via CLI)
        self.max_parallel_devices: int | None = None

        # Note: ProgressReporter will be initialized later with total test count

        # Initialize discovery components
        self.test_discovery = TestDiscovery(self.test_dir)
        self.device_inventory_discovery = DeviceInventoryDiscovery(
            self.base_output_dir / self.merged_data_filename
        )

        # Initialize execution components
        self.job_generator = JobGenerator(self.max_workers, self.output_dir)
        self.output_processor: OutputProcessor | None = (
            None  # Will be initialized when progress reporter is ready
        )
        self.subprocess_runner: SubprocessRunner | None = (
            None  # Will be initialized when output processor is ready
        )
        self.device_executor: DeviceExecutor | None = (
            None  # Will be initialized when needed
        )

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

    def _build_reporter_config(self) -> dict[str, Any]:
        """Build the configuration for PyATS reporters.

        This centralizes the reporter setup to use an asynchronous QueueHandler
        which puts all incoming reporting messages into a queue and lets a
        separate thread handle the slow disk I/O. This makes the ReportServer
        non-blocking and prevents client timeouts under heavy load.

        Returns:
            A dictionary representing the reporter configuration.
        """
        return {
            "reporter": {
                "server": {
                    "handlers": {
                        "fh": {
                            "class": "pyats.reporter.handlers.FileHandler",
                        },
                        "qh": {
                            "class": "pyats.reporter.handlers.QueueHandler",
                            "handlers": ["fh"],
                        },
                    }
                },
                "root": {
                    "handlers": ["qh"],
                },
            }
        }

    def _generate_plugin_config(self, temp_dir: Path) -> Path:
        """Generate the PyATS plugin configuration file.

        Args:
            temp_dir: The temporary directory to write the file in.

        Returns:
            The path to the generated configuration file.
        """
        reporter_config = self._build_reporter_config()
        config_path = temp_dir / "plugin_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(reporter_config, f)
        return config_path

    async def _execute_api_tests_standard(self, test_files: list[Path]) -> Path | None:
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

            # Environment variables are used because PyATS tests run as separate subprocess processes.
            # We cannot pass Python objects across process boundaries
            # so we use env vars to communicate
            # configuration (like data file paths) from the orchestrator to the test subprocess.
            # The merged data file is created by main.py at the base output level.
            # Pass absolute path so the child process (with cwd set) can locate it.
            env["MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH"] = str(
                (self.base_output_dir / self.merged_data_filename).resolve()
            )
            # Set NAC_TEST_TYPE to differentiate API vs D2D test types for separate temp directories
            # This prevents race conditions where both test types write JSONL files to the same location
            env["NAC_TEST_TYPE"] = "api"
            nac_test_dir = str(Path(__file__).parent.parent.parent)
            env["PYTHONPATH"] = get_pythonpath_for_tests(self.test_dir, [nac_test_dir])

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
        self, test_files: list[Path], devices: list[dict[str, Any]]
    ) -> Path | None:
        """
        Run tests in device-centric mode for SSH.

        This method starts a connection broker service, iterates through each device
        from the inventory and launches dedicated PyATS job subprocesses, managed by
        a semaphore to control concurrency. The broker enables connection sharing
        across all subprocesses.

        Args:
            test_files: List of SSH test files to execute
            devices: List of device dictionaries from inventory

        Returns:
            Path to the aggregated D2D archive file, or None if no tests were executed
        """
        logger.info(
            f"Executing {len(test_files)} SSH tests using device-centric execution with connection broker"
        )

        # Devices are passed from the orchestration level
        if not devices:
            # This shouldn't happen since we check before calling, but keep as safety
            logger.error("No devices provided for D2D test execution")
            return None

        # Generate consolidated testbed for broker
        logger.info(f"Creating consolidated testbed for {len(devices)} devices")
        try:
            consolidated_testbed_yaml = (
                TestbedGenerator.generate_consolidated_testbed_yaml(devices)
            )

            # Write testbed to temporary file
            testbed_file = self.output_dir / "broker_testbed.yaml"
            with open(testbed_file, "w") as f:
                f.write(consolidated_testbed_yaml)

            logger.info(f"Consolidated testbed written to: {testbed_file}")

        except Exception as e:
            logger.error(f"Failed to create consolidated testbed: {e}", exc_info=True)
            return None

        # Start connection broker with consolidated testbed
        broker = ConnectionBroker(
            testbed_path=testbed_file,
            max_connections=min(50, len(devices) * 2),  # Reasonable connection limit
            output_dir=self.output_dir,  # Pass output directory for Unicon CLI logs
        )

        try:
            async with broker.run_context():
                logger.info(f"Connection broker started at: {broker.socket_path}")

                # Set environment variable for test subprocesses to find broker
                os.environ["NAC_TEST_BROKER_SOCKET"] = str(broker.socket_path)

                # Execute device tests with broker running
                return await self._execute_device_tests_with_broker(test_files, devices)

        except Exception as e:
            logger.error(
                f"Error running tests with connection broker: {e}", exc_info=True
            )
            return None
        finally:
            # Clean up environment variable
            os.environ.pop("NAC_TEST_BROKER_SOCKET", None)

    async def _execute_device_tests_with_broker(
        self, test_files: list[Path], devices: list[dict[str, Any]]
    ) -> Path | None:
        """Execute device tests with broker running."""

        # Initialize device executor if not already done
        if self.device_executor is None:
            assert self.subprocess_runner is not None  # Should be initialized
            self.device_executor = DeviceExecutor(
                self.job_generator,
                self.subprocess_runner,
                self.d2d_test_status,  # Use d2d_test_status for device tests
                self.test_dir,
                self.base_output_dir,
            )

        # Use a local narrowed variable to satisfy mypy
        device_executor = self.device_executor
        assert device_executor is not None

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
                device_executor.run_device_job_with_semaphore(
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

        # Aggregate all device archives into a single D2D archive
        if device_archives:
            aggregated_archive = await ArchiveAggregator.aggregate_device_archives(
                device_archives, self.base_output_dir
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
        # Use the detected controller type
        EnvironmentValidator.validate_controller_env(self.controller_type)

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

    async def _run_tests_async(self) -> None:
        """Main async orchestration logic."""
        # Track overall start time for combined summary
        self.overall_start_time = datetime.now()

        # Clean up before test execution
        cleanup_pyats_runtime()

        # Clean up old test outputs (CI/CD only)
        if os.environ.get("CI"):
            cleanup_old_test_outputs(self.output_dir, days=3)

        # Pre-flight check and setup
        self.validate_environment()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Note: Merged data file created by main.py (single source of truth)

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
        self.test_status: dict[str, Any] = {}
        self.start_time = datetime.now()

        # Set the test_status reference in progress reporter
        self.progress_reporter.test_status = self.test_status

        # Initialize execution components now that progress reporter is ready
        self.output_processor = OutputProcessor(
            self.progress_reporter, self.test_status
        )
        # Archives should be stored at base level, not in pyats_results subdirectory
        self.subprocess_runner = SubprocessRunner(
            self.base_output_dir, output_handler=self.output_processor.process_line
        )
        # Generate the plugin config and pass it to the runner
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_config_path = self._generate_plugin_config(Path(temp_dir))
            if self.subprocess_runner is not None:
                self.subprocess_runner.plugin_config_path = plugin_config_path

            # Execute tests based on their type
            tasks = []

            if api_tests:
                print(f"Found {len(api_tests)} API test(s) - using standard execution")
                tasks.append(self._execute_api_tests_standard(api_tests))

            if d2d_tests:
                # Get device inventory for D2D tests
                devices = self.device_inventory_discovery.get_device_inventory(
                    d2d_tests
                )

                if devices:
                    print(
                        f"Found {len(d2d_tests)} D2D test(s) - using device-centric execution"
                    )
                    tasks.append(
                        self._execute_ssh_tests_device_centric(d2d_tests, devices)
                    )
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

        # Split test_status into api_test_status and d2d_test_status based on test type.
        # OutputProcessor correctly parses results for ALL tests into test_status.
        # We split them here based on path patterns (.api. vs .d2d.) for accurate
        # per-type summaries.
        #
        # IMPORTANT: We must clear d2d_test_status before populating it from test_status.
        # DeviceExecutor also populates d2d_test_status with its own (buggy) entries that
        # use archive-existence as pass/fail indicator. Without clearing, we'd have
        # duplicate entries with different key formats:
        #   - DeviceExecutor: "hostname::test_stem" (buggy status)
        #   - OutputProcessor: "full.module.path" (correct status)
        # This causes double-counting in summaries.
        #
        # NOTE: We do NOT remove DeviceExecutor's status tracking entirely because it
        # handles an edge case: if the PyATS subprocess fails to start (e.g., job file
        # generation error), OutputProcessor never sees the test. DeviceExecutor's error
        # handling (lines 175-179) captures these failures. By clearing here, we discard
        # DeviceExecutor's buggy success tracking while the error case is still logged.
        if hasattr(self, "test_status") and self.test_status:
            self.api_test_status.clear()
            self.d2d_test_status.clear()
            for test_name, test_info in self.test_status.items():
                if ".api." in test_name or "/api/" in test_name:
                    self.api_test_status[test_name] = test_info
                elif ".d2d." in test_name or "/d2d/" in test_name:
                    self.d2d_test_status[test_name] = test_info
                else:
                    # Fallback: if pattern not found, check test file path
                    test_file = test_info.get("test_file", "")
                    if "/api/" in test_file or "\\api\\" in test_file:
                        self.api_test_status[test_name] = test_info
                    elif "/d2d/" in test_file or "\\d2d\\" in test_file:
                        self.d2d_test_status[test_name] = test_info
                    else:
                        # Default to API if cannot determine type
                        self.api_test_status[test_name] = test_info

        # Print summary after all tests complete
        if self.api_test_status or self.d2d_test_status:
            # Combine all test statuses for summary
            combined_status = {}
            combined_status.update(self.api_test_status)
            combined_status.update(self.d2d_test_status)

            # Print the summary (archives are at base level)
            self.summary_printer.print_summary(
                combined_status,
                self.start_time,
                output_dir=self.base_output_dir,
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

        # Use ArchiveInspector to find all archives (stored at base level)
        archives = ArchiveInspector.find_archives(self.base_output_dir)

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
            # TODO: No longer need this -- remove
            # Fallback to legacy archives for backward compatibility
            archive_paths.append(archives["legacy"][0])
            archive_info.append(f"Found legacy archive: {archives['legacy'][0].name}")

        if not archive_paths:
            print("No PyATS job archives found to generate reports from.")
            return

        print(f"\nGenerating reports from {len(archive_paths)} archive(s)...")

        # Use MultiArchiveReportGenerator for all cases (handles single archive too)
        # Pass base directory to avoid double-nesting of pyats_results directories
        generator = MultiArchiveReportGenerator(
            self.base_output_dir, minimal_reports=self.minimal_reports
        )
        result = await generator.generate_reports_from_archives(archive_paths)

        if result["status"] in ["success", "partial"]:
            # Format duration (minutes and seconds)
            duration = result["duration"]
            if duration < 60:
                duration_str = f"{duration:.2f} seconds"
            else:
                minutes = int(duration / 60)
                secs = duration % 60
                duration_str = f"{minutes} minutes {secs:.2f} seconds"

            print(f"{terminal.info('Total report generation time:')} {duration_str}")

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
                for _archive_type, archive_result in result["results"].items():
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

            # Clean up archives after successful extraction and report generation
            # (unless in debug mode or user wants to keep data)
            if not (
                os.environ.get("PYATS_DEBUG") or os.environ.get("KEEP_HTML_REPORT_DATA")
            ):
                for archive_path in archive_paths:
                    try:
                        archive_path.unlink()
                        logger.debug(f"Cleaned up archive: {archive_path}")
                    except Exception as e:
                        logger.warning(
                            f"Failed to clean up archive {archive_path}: {e}"
                        )
            else:
                logger.info(
                    "Keeping archive files (debug mode or KEEP_HTML_REPORT_DATA is set)"
                )

            # Clean up empty api/ and d2d/ temp parent directories
            # These are created by base_test.py for type-specific temp directories
            # but only the html_report_data_temp subdirectories get cleaned up
            for test_type in ["api", "d2d"]:
                type_dir = self.base_output_dir / test_type
                if type_dir.exists() and type_dir.is_dir():
                    try:
                        # Only remove if empty (no files or subdirectories)
                        if not any(type_dir.iterdir()):
                            type_dir.rmdir()
                            logger.debug(f"Cleaned up empty directory: {type_dir}")
                    except Exception as e:
                        logger.debug(f"Could not remove directory {type_dir}: {e}")

        else:
            print(f"\n{terminal.error('Failed to generate reports')}")
            if result.get("error"):
                print(f"Error: {result['error']}")
