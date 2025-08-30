# -*- coding: utf-8 -*-

"""Combined orchestrator for sequential PyATS and Robot Framework test execution."""

import logging
from pathlib import Path
from typing import List, Optional, Tuple
import typer

from nac_test.data_merger import DataMerger
from nac_test.pyats_core.orchestrator import PyATSOrchestrator
from nac_test.pyats_core.discovery import TestDiscovery
import nac_test.robot.robot_writer
import nac_test.robot.pabot
from nac_test.utils.logging import VerbosityLevel

logger = logging.getLogger(__name__)


class CombinedOrchestrator:
    """Lightweight coordinator for sequential PyATS and Robot Framework test execution.

    This class discovers test types and delegates execution to existing orchestrators,
    following DRY and SRP principles by reusing proven orchestration logic.
    """

    def __init__(
        self,
        data_paths: List[Path],
        templates_dir: Path,
        output_dir: Path,
        merged_data_filename: str,
        filters_path: Optional[Path] = None,
        tests_path: Optional[Path] = None,
        include_tags: List[str] = None,
        exclude_tags: List[str] = None,
        render_only: bool = False,
        dry_run: bool = False,
        max_parallel_devices: Optional[int] = None,
        verbosity: VerbosityLevel = VerbosityLevel.WARNING,
        dev_pyats_only: bool = False,
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
            verbosity: Logging verbosity level
            dev_pyats_only: Development mode - run only PyATS tests (skip Robot)
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
        self.verbosity = verbosity

        # Development mode
        self.dev_pyats_only = dev_pyats_only

    def run_tests(self) -> None:
        """Main entry point for combined test execution.

        Handles both development mode (PyATS only) and production mode (combined).
        """
        # Note: Output directory and merged data file created by main.py

        # Handle development mode (PyATS only)
        if self.dev_pyats_only:
            typer.secho(
                "⚠️  WARNING: --pyats flag is for development use only. Production runs should use combined execution.",
                fg=typer.colors.YELLOW,
            )
            typer.echo("🧪 Running PyATS tests only (development mode)...")

            # Direct call to PyATS orchestrator (base directory)
            orchestrator = PyATSOrchestrator(
                data_paths=self.data_paths,
                test_dir=self.templates_dir,
                output_dir=self.output_dir,
                merged_data_filename=self.merged_data_filename,
            )
            if self.max_parallel_devices is not None:
                orchestrator.max_parallel_devices = self.max_parallel_devices
            orchestrator.run_tests()
            return

        # Production mode: Combined execution
        # Discover test types (simple existence checks)
        has_pyats, has_robot = self._discover_test_types()

        # Handle empty scenarios
        if not has_pyats and not has_robot:
            typer.echo("No test files found (no *.py PyATS tests or *.robot templates)")
            return

        # Sequential execution with subdirectory management
        if has_pyats:
            typer.echo("\n🧪 Running PyATS tests...\n")

            # Create PyATS output subdirectory and run
            pyats_output_dir = self.output_dir / "pyats_results"
            pyats_output_dir.mkdir(exist_ok=True)

            orchestrator = PyATSOrchestrator(
                data_paths=self.data_paths,
                test_dir=self.templates_dir,
                output_dir=pyats_output_dir,
                merged_data_filename=self.merged_data_filename,
            )
            if self.max_parallel_devices is not None:
                orchestrator.max_parallel_devices = self.max_parallel_devices
            orchestrator.run_tests()

        if has_robot:
            typer.echo("\n🤖 Running Robot Framework tests...\n")

            # Create Robot output subdirectory and run
            robot_output_dir = self.output_dir / "robot_results"
            robot_output_dir.mkdir(exist_ok=True)

            writer = nac_test.robot.robot_writer.RobotWriter(
                data_paths=self.data_paths,
                filters_path=self.filters_path,
                tests_path=self.tests_path,
                include_tags=self.include_tags,
                exclude_tags=self.exclude_tags,
            )

            writer.write(self.templates_dir, robot_output_dir)
            writer.write_merged_data_model(robot_output_dir, self.merged_data_filename)

            if not self.render_only:
                nac_test.robot.pabot.run_pabot(
                    path=robot_output_dir,
                    include=self.include_tags,
                    exclude=self.exclude_tags,
                    dry_run=self.dry_run,
                    verbose=(self.verbosity == VerbosityLevel.DEBUG),
                )

        # Summary
        self._print_execution_summary(has_pyats, has_robot)

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
        typer.echo("\n" + "=" * 50)
        typer.echo("📋 Combined Test Execution Summary")
        typer.echo("=" * 50)

        if has_pyats:
            typer.echo("\n✅ PyATS tests: Completed")
            typer.echo(f"   📁 Results: {self.output_dir}/pyats_results/")
            typer.echo(f"   📊 Reports: {self.output_dir}/pyats_results/html_reports/")

        if has_robot:
            typer.echo("\n✅ Robot Framework tests: Completed")
            typer.echo(f"   📁 Results: {self.output_dir}/robot_results/")
            if not self.render_only:
                typer.echo(
                    f"   📊 Reports: {self.output_dir}/robot_results/report.html"
                )

        typer.echo(
            f"\n📄 Merged data model: {self.output_dir}/{self.merged_data_filename}"
        )
        typer.echo("=" * 50)
