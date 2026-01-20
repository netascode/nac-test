# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# -*- coding: utf-8 -*-

"""Robot Framework orchestration logic for nac-test.

This module provides the RobotOrchestrator class that manages the complete
Robot Framework test execution lifecycle, following the same architectural
pattern as PyATSOrchestrator.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import typer

from nac_test.robot.pabot import run_pabot
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

    def run_tests(self) -> None:
        """Execute the complete Robot Framework test lifecycle.

        This method:
        1. Creates the output directory (uses root for backward compatibility)
        2. Renders Robot test templates using RobotWriter
        3. Creates merged data model file in output directory
        4. Executes tests using pabot (unless render_only mode)

        Follows the same pattern as PyATSOrchestrator.run_tests().
        """
        # Create Robot Framework output directory (orchestrator owns its structure)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Robot Framework orchestrator initialized")
        logger.info(f"Base output directory: {self.base_output_dir}")
        logger.info(f"Robot working directory: {self.output_dir}")
        logger.info(f"Templates directory: {self.templates_dir}")

        # Phase 1: Template rendering (delegate to existing RobotWriter)
        start_time = datetime.now()
        start_timestamp = start_time.strftime("%H:%M:%S")
        typer.echo(f"[{start_timestamp}] 📝 Rendering Robot Framework templates...")

        self.robot_writer.write(
            self.templates_dir, self.output_dir, ordering_file=self.ordering_file
        )

        end_time = datetime.now()
        end_timestamp = end_time.strftime("%H:%M:%S")
        duration = (end_time - start_time).total_seconds()
        duration_str = (
            f"{duration:.1f}s"
            if duration < 60
            else f"{int(duration // 60)}m {duration % 60:.0f}s"
        )
        typer.echo(
            f"[{end_timestamp}] ✅ Template rendering completed ({duration_str})"
        )

        # Phase 2: Create merged data model in Robot working directory
        # Note: Robot tests expect the merged data file in their working directory
        typer.echo("📄 Creating merged data model for Robot tests...")
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
                verbose=(self.verbosity == VerbosityLevel.DEBUG),
                ordering_file=self.ordering_file,
                extra_args=self.extra_args,
            )
            # Handle exit code 252 (invalid extra arguments)
            if exit_code == 252:
                typer.echo(
                    typer.style(
                        "Error: Invalid Robot Framework arguments provided",
                        fg=typer.colors.RED,
                    )
                )
                raise typer.Exit(252)
            typer.echo("✅ Robot Framework tests completed")
        else:
            typer.echo("✅ Robot Framework templates rendered (render-only mode)")

    def get_output_summary(self) -> dict[str, Any]:
        """Get summary information about Robot Framework outputs.

        Returns:
            Dictionary containing output directory and key files information
        """
        return {
            "type": "robot",
            "base_output_dir": str(self.base_output_dir),
            "working_dir": str(self.output_dir),
            "templates_dir": str(self.templates_dir),
            "merged_data_file": str(self.output_dir / self.merged_data_filename),
            "render_only": self.render_only,
        }
