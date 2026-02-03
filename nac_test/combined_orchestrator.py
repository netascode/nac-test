# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# -*- coding: utf-8 -*-

"""Combined orchestrator for sequential PyATS and Robot Framework test execution."""

import logging
import platform
import sys
from pathlib import Path

import typer

from nac_test.core.constants import DEBUG_MODE
from nac_test.core.reporting.combined_generator import CombinedReportGenerator
from nac_test.core.types import TestResults
from nac_test.pyats_core.discovery import TestDiscovery
from nac_test.pyats_core.orchestrator import PyATSOrchestrator
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
        max_parallel_devices: int | None = None,
        minimal_reports: bool = False,
        custom_testbed_path: Path | None = None,
        verbosity: VerbosityLevel = VerbosityLevel.WARNING,
        dev_pyats_only: bool = False,
        dev_robot_only: bool = False,
        processes: int | None = None,
        extra_args: list[str] | None = None,
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
            processes: Number of parallel processes for Robot test execution (Robot only)
            extra_args: Additional Robot Framework arguments to pass to pabot (Robot only)
            max_parallel_devices: Max parallel devices for PyATS D2D tests
            minimal_reports: Only include command outputs for failed/errored tests (PyATS only)
            custom_testbed_path: Path to custom PyATS testbed YAML for device overrides (PyATS only)
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
        self.processes = processes
        self.extra_args = extra_args or []

        # PyATS-specific parameters
        self.max_parallel_devices = max_parallel_devices
        self.minimal_reports = minimal_reports
        self.custom_testbed_path = custom_testbed_path
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
            # Progressive disclosure: clean output for customers, full context for developers
            if DEBUG_MODE:
                raise typer.Exit(1) from e  # Developer: full exception context
            raise typer.Exit(1) from None  # Customer: clean output

    def run_tests(self) -> TestResults:
        """Main entry point for combined test execution.

        Handles development modes (PyATS only, Robot only) and production mode (combined).
        Dev mode flags act as filters - they restrict which test types run but use the
        same execution flow, dashboard generation, and summary output.

        Returns:
            TestResults with combined test execution results and by_framework breakdown
        """
        # Note: Output directory and merged data file created by main.py

        # Print dev mode warnings if applicable
        if self.dev_pyats_only:
            typer.secho(
                "\n\n⚠️  WARNING: --pyats flag is for development use only. "
                "Production runs should use combined execution.",
                fg=typer.colors.YELLOW,
            )
        if self.dev_robot_only:
            typer.secho(
                "\n\n⚠️  WARNING: --robot flag is for development use only. "
                "Production runs should use combined execution.",
                fg=typer.colors.YELLOW,
            )

        # Discover test types (simple existence checks)
        has_pyats, has_robot = self._discover_test_types()

        # Apply dev mode filters - these flags restrict which test types run
        if self.dev_pyats_only:
            has_robot = False
        if self.dev_robot_only:
            has_pyats = False

        # Handle empty scenarios
        if not has_pyats and not has_robot:
            typer.echo("No test files found (no *.py PyATS tests or *.robot templates)")
            return TestResults.empty()

        # Sequential execution - each orchestrator manages its own directory structure
        combined_stats = TestResults.empty()

        if has_pyats:
            typer.echo("\n🧪 Running PyATS tests...\n")
            self._check_python_version()

            pyats_orchestrator = PyATSOrchestrator(
                data_paths=self.data_paths,
                test_dir=self.templates_dir,
                output_dir=self.output_dir,
                merged_data_filename=self.merged_data_filename,
                minimal_reports=self.minimal_reports,
                custom_testbed_path=self.custom_testbed_path,
                controller_type=self.controller_type,
            )
            if self.max_parallel_devices is not None:
                pyats_orchestrator.max_parallel_devices = self.max_parallel_devices

            combined_stats += pyats_orchestrator.run_tests()

        if has_robot:
            typer.echo("\n🤖 Running Robot Framework tests...\n")

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
                processes=self.processes,
                extra_args=self.extra_args,
                verbosity=self.verbosity,
            )
            try:
                robot_stats = robot_orchestrator.run_tests()
            except Exception as e:
                # In render-only mode, propagate exceptions immediately
                if self.render_only:
                    raise

                # Robot orchestrator failed (e.g., invalid arguments, execution errors)
                logger.error(f"Robot Framework execution failed: {e}", exc_info=True)
                typer.echo(
                    typer.style(
                        f"⚠️  Robot Framework tests skipped due to error: {e}",
                        fg=typer.colors.YELLOW,
                    )
                )
                # Create error result and ensure it's in by_framework for dashboard
                robot_stats = TestResults.from_error(str(e))
                robot_stats.by_framework["ROBOT"] = TestResults.from_error(str(e))

            combined_stats += robot_stats

        # Generate combined dashboard and print summary (unless render_only mode)
        if not self.render_only:
            typer.echo("\n📊 Generating combined dashboard...")
            logger.debug(
                f"Calling CombinedReportGenerator with by_framework: {combined_stats.by_framework}"
            )

            combined_generator = CombinedReportGenerator(self.output_dir)
            combined_path = combined_generator.generate_combined_summary(
                combined_stats.by_framework
            )
            if combined_path:
                typer.echo(f"   ✅ Combined dashboard: {combined_path}")

            self._print_execution_summary(has_pyats, has_robot, combined_stats)

        return combined_stats

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

    def _discover_test_types(self) -> tuple[bool, bool]:
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

    def _print_execution_summary(
        self, has_pyats: bool, has_robot: bool, stats: TestResults | None = None
    ) -> None:
        """Print execution summary with statistics."""
        typer.echo("\n" + "=" * 70)
        typer.echo("📋 Combined Test Execution Summary")
        typer.echo("=" * 70)

        # Show overall stats if available
        if stats:
            typer.echo("\n📊 Overall Results:")
            typer.echo(f"   Total: {stats.total} tests")
            typer.echo(f"   ✅ Passed: {stats.passed}")
            typer.echo(f"   ❌ Failed: {stats.failed}")
            typer.echo(f"   ⊘ Skipped: {stats.skipped}")

            # Combined dashboard is the main entry point
            if not self.render_only:
                typer.echo("\n🎯 Combined Dashboard:")
                combined_dashboard = self.output_dir / "combined_summary.html"
                if combined_dashboard.exists():
                    typer.echo(f"   📊 {combined_dashboard}")
                    typer.echo("   (Aggregated results from all test frameworks)")

        if has_robot:
            typer.echo("\n✅ Robot Framework tests: Completed")
            typer.echo(f"   📁 Results: {self.output_dir}/robot_results/")
            if stats and "ROBOT" in stats.by_framework:
                robot_stats = stats.by_framework["ROBOT"]
                typer.echo(
                    f"   📊 {robot_stats.total} tests: "
                    f"{robot_stats.passed} passed, {robot_stats.failed} failed"
                )
            if not self.render_only:
                typer.echo(
                    f"   📊 Summary: {self.output_dir}/robot_results/summary_report.html"
                )
                typer.echo(f"   📊 Detailed: {self.output_dir}/robot_results/log.html")

        if has_pyats:
            typer.echo("\n✅ PyATS tests: Completed")
            typer.echo(f"   📁 Results: {self.output_dir}/pyats_results/")
            api_summary = (
                self.output_dir
                / "pyats_results"
                / "api"
                / "html_reports"
                / "summary_report.html"
            )
            d2d_summary = (
                self.output_dir
                / "pyats_results"
                / "d2d"
                / "html_reports"
                / "summary_report.html"
            )
            if api_summary.exists():
                typer.echo(f"   📊 API Summary: {api_summary}")
            if d2d_summary.exists():
                typer.echo(f"   📊 D2D Summary: {d2d_summary}")

        typer.echo(
            f"\n📄 Merged data model: {self.output_dir}/{self.merged_data_filename}"
        )
        typer.echo("=" * 70)
