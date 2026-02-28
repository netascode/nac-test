# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Robot Framework orchestration logic for nac-test.

This module provides the RobotOrchestrator class that manages the complete
Robot Framework test execution lifecycle, following the same architectural
pattern as PyATSOrchestrator.
"""

import logging
import os
from pathlib import Path

import typer

from nac_test.core.constants import (
    EXIT_DATA_ERROR,
    EXIT_ERROR,
    EXIT_INTERRUPTED,
    LOG_HTML,
    OUTPUT_XML,
    REPORT_HTML,
    ROBOT_RESULTS_DIRNAME,
)
from nac_test.core.types import ErrorType, TestResults
from nac_test.robot.pabot import run_pabot
from nac_test.robot.reporting.robot_generator import RobotReportGenerator
from nac_test.robot.robot_writer import RobotWriter
from nac_test.utils.logging import VerbosityLevel

logger = logging.getLogger(__name__)


class RobotOrchestrator:
    """Orchestrates Robot Framework test execution with clean directory management.

    This class follows a similar architectural pattern as PyATSOrchestrator:
    - Receives base output directory from caller
    - Uses root output directory for backward compatibility (unlike PyATS which uses subdirectory)
    - Manages complete Robot Framework lifecycle
    - Reuses existing RobotWriter and pabot components (DRY principle)
    """

    def __init__(
        self,
        data_paths: list[Path],
        templates_dir: Path,
        output_dir: Path,
        merged_data_filename: str,
        filters_path: Path | None = None,
        tests_path: Path | None = None,
        include_tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        render_only: bool = False,
        dry_run: bool = False,
        processes: int | None = None,
        extra_args: list[str] | None = None,
        verbosity: VerbosityLevel = VerbosityLevel.WARNING,
        debug: bool = False,
    ):
        """Initialize the Robot Framework orchestrator.

        Args:
            data_paths: List of paths to data model YAML files
            templates_dir: Directory containing Robot template files
            output_dir: Base output directory (orchestrator creates robot_results subdirectory)
            merged_data_filename: Name of the merged data model file
            filters_path: Optional path to filter files
            tests_path: Optional path to test files
            include_tags: Optional list of tags to include
            exclude_tags: Optional list of tags to exclude
            render_only: If True, only render templates without executing tests
            dry_run: If True, run tests in dry-run mode
            processes: Number of parallel processes for test execution
            extra_args: Additional Robot Framework arguments to pass to pabot
            verbosity: Logging verbosity level
            debug: Enable debug mode - enables verbose output for pabot
        """
        self.data_paths = data_paths
        self.templates_dir = Path(templates_dir)
        self.base_output_dir = Path(
            output_dir
        )  # Store base directory for merged data file access
        self.output_dir = (
            self.base_output_dir
        )  # Keep at root for backward compatibility
        self.merged_data_filename = merged_data_filename

        # Robot-specific parameters
        self.filters_path = filters_path
        self.tests_path = tests_path
        self.include_tags = include_tags or []
        self.exclude_tags = exclude_tags or []
        self.render_only = render_only
        self.dry_run = dry_run
        self.processes = processes
        self.extra_args = extra_args or []
        self.verbosity = verbosity
        self.debug = debug

        # Determine if ordering file should be used for test-level parallelization
        if "NAC_TEST_NO_TESTLEVELSPLIT" not in os.environ:
            self.ordering_file: Path | None = self.output_dir / "ordering.txt"
        else:
            self.ordering_file = None

        # Initialize Robot Framework components (reuse existing implementations)
        self.robot_writer = RobotWriter(
            data_paths=self.data_paths,
            filters_path=self.filters_path,
            tests_path=self.tests_path,
            include_tags=self.include_tags,
            exclude_tags=self.exclude_tags,
        )

    def run_tests(self) -> TestResults:
        """Execute the complete Robot Framework test lifecycle.

        This method:
        1. Creates the output directory (uses root for backward compatibility)
        2. Renders Robot test templates using RobotWriter
        3. Creates merged data model file in output directory
        4. Executes tests using pabot (unless render_only mode)
        5. Creates backward compatibility symlinks
        6. Extracts and returns test statistics

        Follows the same pattern as PyATSOrchestrator.run_tests().

        Returns:
            TestResults with test execution results.

        Raises:
            RuntimeError: If pabot returns exit code 252 (invalid arguments).
        """
        # Create Robot Framework output directory (orchestrator owns its structure)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Robot Framework orchestrator initialized")
        logger.info(f"Base output directory: {self.base_output_dir}")
        logger.info(f"Robot working directory: {self.output_dir}")
        logger.info(f"Templates directory: {self.templates_dir}")

        # Phase 1: Template rendering (delegate to existing RobotWriter)
        typer.echo("📝 Rendering Robot Framework templates...")
        self.robot_writer.write(
            self.templates_dir, self.output_dir, ordering_file=self.ordering_file
        )

        # Phase 2: Create merged data model in Robot working directory
        # Note: Robot tests expect the merged data file in their working directory
        logger.info("Creating merged data model for Robot tests")
        self.robot_writer.write_merged_data_model(
            self.output_dir, self.merged_data_filename
        )

        # Phase 3: Test execution (unless render-only mode)
        if not self.render_only:
            typer.echo("🤖 Executing Robot Framework tests...\n\n")
            exit_code = run_pabot(
                path=self.output_dir,
                include=self.include_tags,
                exclude=self.exclude_tags,
                processes=self.processes,
                dry_run=self.dry_run,
                verbose=(self.debug or self.verbosity == VerbosityLevel.DEBUG),
                ordering_file=self.ordering_file,
                extra_args=self.extra_args,
            )
            # Handle special exit codes - just log and return appropriate TestResults
            # User-facing error messages are handled centrally in main.py
            if exit_code == EXIT_DATA_ERROR:
                error_msg = "Invalid Robot Framework arguments passed to nac-test"
                logger.error(error_msg)
                return TestResults.from_error(error_msg, ErrorType.INVALID_ROBOT_ARGS)
            elif exit_code == EXIT_INTERRUPTED:
                error_msg = "Robot Framework execution was interrupted"
                logger.error(error_msg)
                return TestResults.from_error(error_msg, ErrorType.INTERRUPTED)
            elif exit_code == EXIT_ERROR:
                error_msg = "Robot Framework execution failed (fatal error, see logs)"
                logger.error(error_msg)
                return TestResults.from_error(error_msg)

            # Phase 4: Create backward compatibility symlinks
            # (output files written directly to robot_results/ via --output/--log/--report flags)
            self._create_backward_compat_symlinks()

            # Phase 5: Generate Robot summary report and get stats
            logger.info("Generating Robot summary report...")
            generator = RobotReportGenerator(self.base_output_dir)
            summary_path, stats = generator.generate_summary_report()
            if summary_path:
                logger.info(f"Robot summary report: {summary_path}")
            else:
                logger.warning(
                    "Robot summary report generation skipped (no tests or error)"
                )
            logger.info(f"Robot results: {stats}")

            return stats
        else:
            typer.echo("✅ Robot Framework templates rendered (render-only mode)")
            return TestResults.not_run("render-only mode")

    def _create_backward_compat_symlinks(self) -> None:
        """Create backward compatibility symlinks at root pointing to robot_results/.

        Creates symlinks for:
        - output.xml -> robot_results/output.xml
        - log.html -> robot_results/log.html
        - report.html -> robot_results/report.html

        Note: xunit.xml is NOT symlinked here. The combined xunit.xml at root
        is created by the xunit merger (merging Robot + PyATS results).

        This ensures existing tools/scripts that expect these files at root continue to work.
        """
        robot_results_dir = self.base_output_dir / ROBOT_RESULTS_DIRNAME
        files_to_link = [LOG_HTML, OUTPUT_XML, REPORT_HTML]

        for filename in files_to_link:
            source = robot_results_dir / filename
            target = self.base_output_dir / filename

            # Skip if source doesn't exist (shouldn't happen, but be defensive)
            if not source.exists():
                logger.warning(f"Source file not found for symlink: {source}")
                continue

            # Remove existing symlink or file if it exists
            if target.is_symlink():
                target.unlink()
            elif target.is_dir():
                logger.warning(f"Skipping symlink creation: {target} is a directory")
                continue
            elif target.exists():
                target.unlink()

            # Create relative symlink
            target.symlink_to(source.relative_to(self.base_output_dir))
            logger.debug(f"Created symlink: {target} -> {source}")
