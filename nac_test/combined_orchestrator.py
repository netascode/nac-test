# -*- coding: utf-8 -*-

"""Combined orchestrator for sequential PyATS and Robot Framework test execution."""

import logging
import platform
import sys
from pathlib import Path
from typing import List, Optional, Tuple
import typer

from nac_test.pyats_core.orchestrator import PyATSOrchestrator
from nac_test.pyats_core.discovery import TestDiscovery
from nac_test.robot.orchestrator import RobotOrchestrator
from nac_test.utils.controller import detect_controller_type
from nac_test.utils.logging import VerbosityLevel

logger = logging.getLogger(__name__)


class CombinedOrchestrator:
    """Lightweight coordinator for sequential PyATS and Robot Framework test execution.

    This class discovers test types and delegates execution to existing orchestrators,
    following DRY and SRP principles by reusing proven orchestration logic.

    Note: Robot Framework results are placed at the root output directory for backward
    compatibility, while PyATS results use a subdirectory for organization.
    """

    def __init__(
        self,
        data_paths: List[Path],
        templates_dir: Path,
        output_dir: Path,
        merged_data_filename: str,
        filters_path: Optional[Path] = None,
        tests_path: Optional[Path] = None,
        include_tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        render_only: bool = False,
        dry_run: bool = False,
        max_parallel_devices: Optional[int] = None,
        minimal_reports: bool = False,
        verbosity: VerbosityLevel = VerbosityLevel.WARNING,
        dev_pyats_only: bool = False,
        dev_robot_only: bool = False,
    ):
        """Initialize the combined orchestrator.

        Args:
            data_paths: List of paths to data model YAML files
            templates_dir: Directory containing test templates and PyATS test files
            output_dir: Base directory for test output
            merged_data_filename: Name of the merged data model file
            filters_path: Path to Jinja filters (Robot only)
            tests_path: Path to Jinja tests (Robot only)
            include_tags: Tags to include (Robot only)
            exclude_tags: Tags to exclude (Robot only)
            render_only: Only render tests without executing (Robot only)
            dry_run: Dry run mode (Robot only)
            max_parallel_devices: Max parallel devices for PyATS D2D tests
            minimal_reports: Only include command outputs for failed/errored tests (PyATS only)
            verbosity: Logging verbosity level
            dev_pyats_only: Development mode - run only PyATS tests (skip Robot)
            dev_robot_only: Development mode - run only Robot Framework tests (skip PyATS)
        """
        self.data_paths = data_paths
        self.templates_dir = Path(templates_dir)
        self.output_dir = Path(output_dir)
        self.merged_data_filename = merged_data_filename

        # Robot-specific parameters
        self.filters_path = filters_path
        self.tests_path = tests_path
        self.include_tags = include_tags or []
        self.exclude_tags = exclude_tags or []
        self.render_only = render_only
        self.dry_run = dry_run

        # PyATS-specific parameters
        self.max_parallel_devices = max_parallel_devices
        self.minimal_reports = minimal_reports
        self.verbosity = verbosity

        # Development modes
        self.dev_pyats_only = dev_pyats_only
        self.dev_robot_only = dev_robot_only

        # Detect controller type early (required for all test types)
        try:
            self.controller_type = detect_controller_type()
            logger.info(f"Controller type detected: {self.controller_type}")
        except ValueError as e:
            # Exit gracefully if controller detection fails
            typer.secho(
                f"\n❌ Controller detection failed:\n{e}", fg=typer.colors.RED, err=True
            )
            raise typer.Exit(1)

    def run_tests(self) -> None:
        """Main entry point for combined test execution.

        Handles development modes (PyATS only, Robot only) and production mode (combined).
        """
        # Note: Output directory and merged data file created by main.py

        # Handle development mode (PyATS only)
        if self.dev_pyats_only:
            typer.secho(
                "\n\n⚠️  WARNING: --pyats flag is for development use only. Production runs should use combined execution.",
                fg=typer.colors.YELLOW,
            )
            typer.echo("🧪 Running PyATS tests only (development mode)...")
            self._check_python_version()

            # Direct call to PyATS orchestrator (base directory) - orchestrator manages its own structure
            orchestrator = PyATSOrchestrator(
                data_paths=self.data_paths,
                test_dir=self.templates_dir,
                output_dir=self.output_dir,
                merged_data_filename=self.merged_data_filename,
                minimal_reports=self.minimal_reports,
                controller_type=self.controller_type,
            )
            if self.max_parallel_devices is not None:
                orchestrator.max_parallel_devices = self.max_parallel_devices
            orchestrator.run_tests()
            return

        # Handle development mode (Robot only)
        if self.dev_robot_only:
            typer.secho(
                "\n\n⚠️  WARNING: --robot flag is for development use only. Production runs should use combined execution.",
                fg=typer.colors.YELLOW,
            )
            typer.echo("🤖 Running Robot Framework tests only (development mode)...")

            # Direct call to Robot orchestrator (base directory) - orchestrator manages its own structure
            robot_orchestrator = RobotOrchestrator(
                data_paths=self.data_paths,
                templates_dir=self.templates_dir,
                output_dir=self.output_dir,
                merged_data_filename=self.merged_data_filename,
                filters_path=self.filters_path,
                tests_path=self.tests_path,
                include_tags=self.include_tags,
                exclude_tags=self.exclude_tags,
                render_only=self.render_only,
                dry_run=self.dry_run,
                verbosity=self.verbosity,
            )
            robot_orchestrator.run_tests()
            return

        # Production mode: Combined execution
        # Discover test types (simple existence checks)
        has_pyats, has_robot = self._discover_test_types()

        # Handle empty scenarios
        if not has_pyats and not has_robot:
            typer.echo("No test files found (no *.py PyATS tests or *.robot templates)")
            return

        # Sequential execution - each orchestrator manages its own directory structure
        if has_pyats:
            typer.echo("\n🧪 Running PyATS tests...\n")
            self._check_python_version()

            # Direct call to PyATS orchestrator (base directory) - orchestrator manages its own structure
            orchestrator = PyATSOrchestrator(
                data_paths=self.data_paths,
                test_dir=self.templates_dir,
                output_dir=self.output_dir,
                merged_data_filename=self.merged_data_filename,
                minimal_reports=self.minimal_reports,
                controller_type=self.controller_type,
            )
            if self.max_parallel_devices is not None:
                orchestrator.max_parallel_devices = self.max_parallel_devices
            orchestrator.run_tests()

        if has_robot:
            typer.echo("\n🤖 Running Robot Framework tests...\n")

            # Direct call to Robot orchestrator (base directory) - orchestrator manages its own structure
            robot_orchestrator2 = RobotOrchestrator(
                data_paths=self.data_paths,
                templates_dir=self.templates_dir,
                output_dir=self.output_dir,
                merged_data_filename=self.merged_data_filename,
                filters_path=self.filters_path,
                tests_path=self.tests_path,
                include_tags=self.include_tags,
                exclude_tags=self.exclude_tags,
                render_only=self.render_only,
                dry_run=self.dry_run,
                verbosity=self.verbosity,
            )
            robot_orchestrator2.run_tests()

        # Summary
        self._print_execution_summary(has_pyats, has_robot)

    @staticmethod
    def _check_python_version() -> None:
        if platform.system() == "Darwin" and sys.version_info.minor == 11:
            typer.echo(
                typer.style(
                    "Warning: Python 3.11 on macOS has known compatibility issues with PyATS.\n"
                    "We recommend using Python 3.12 or higher on macOS for optimal reliability.",
                    fg=typer.colors.YELLOW,
                )
            )
            typer.echo()

    def _discover_test_types(self) -> Tuple[bool, bool]:
        """Discover which test types are present in the templates directory.

        Returns:
            Tuple of (has_pyats, has_robot)
        """
        # PyATS discovery - needed because we pass specific files to orchestrator
        has_pyats = False
        try:
            test_discovery = TestDiscovery(self.templates_dir)
            pyats_files, _ = test_discovery.discover_pyats_tests()
            has_pyats = bool(pyats_files)
            if has_pyats:
                logger.debug(f"Found {len(pyats_files)} PyATS test files")
        except Exception as e:
            logger.debug(f"\nPyATS discovery failed (no PyATS tests found): {e}\n")

        # Robot discovery - simple existence check (RobotWriter handles the rest)
        has_robot = any(
            f.suffix in [".robot", ".resource", ".j2"]
            for f in self.templates_dir.rglob("*")
            if f.is_file()
        )
        if has_robot:
            logger.debug("Found Robot template files")

        return has_pyats, has_robot

    def _print_execution_summary(self, has_pyats: bool, has_robot: bool) -> None:
        """Print execution summary."""
        # Skip combined summary for development modes - individual orchestrators handle their own summaries
        if self.dev_pyats_only or self.dev_robot_only:
            return

        typer.echo("\n" + "=" * 50)
        typer.echo("📋 Combined Test Execution Summary")
        typer.echo("=" * 50)

        if has_pyats:
            typer.echo("\n✅ PyATS tests: Completed")
            typer.echo(f"   📁 Results: {self.output_dir}/pyats_results/")
            typer.echo(f"   📊 Reports: {self.output_dir}/pyats_results/html_reports/")

        if has_robot:
            typer.echo("\n✅ Robot Framework tests: Completed")
            typer.echo(f"   📁 Results: {self.output_dir}/")
            if not self.render_only:
                typer.echo(f"   📊 Reports: {self.output_dir}/report.html")

        typer.echo(
            f"\n📄 Merged data model: {self.output_dir}/{self.merged_data_filename}"
        )
        typer.echo("=" * 50)
