# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Combined orchestrator for sequential PyATS and Robot Framework test execution."""

import logging
import os
from pathlib import Path

import typer

from nac_test.core.constants import (
    COMBINED_SUMMARY_FILENAME,
    HTML_REPORTS_DIRNAME,
    PYATS_RESULTS_DIRNAME,
    ROBOT_RESULTS_DIRNAME,
    SUMMARY_REPORT_FILENAME,
)
from nac_test.core.reporting.combined_generator import CombinedReportGenerator
from nac_test.core.types import CombinedResults, TestResults
from nac_test.pyats_core.discovery import TestDiscovery
from nac_test.pyats_core.orchestrator import PyATSOrchestrator
from nac_test.robot.orchestrator import RobotOrchestrator
from nac_test.utils.controller import detect_controller_type
from nac_test.utils.logging import VerbosityLevel
from nac_test.utils.platform import check_and_exit_if_unsupported_macos_python

logger = logging.getLogger(__name__)


class CombinedOrchestrator:
    """Lightweight coordinator for sequential PyATS and Robot Framework test execution.

    This class discovers test types and delegates execution to existing orchestrators,
    following DRY and SRP principles by reusing proven orchestration logic.

    Output structure:
        output_dir/
        ├── combined_summary.html     # Unified dashboard (all frameworks)
        ├── robot_results/            # Robot Framework artifacts
        │   ├── output.xml, log.html, report.html, xunit.xml
        │   └── summary_report.html
        ├── output.xml, log.html...   # Symlinks to robot_results/ (backward compat)
        └── pyats_results/            # PyATS artifacts
            ├── api/html_reports/summary_report.html
            └── d2d/html_reports/summary_report.html
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
            dry_run: Dry run mode (skips actual test execution)
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

        # Detect controller type early (unless we are in render-only mode, which doesn't require controller access)
        self.controller_type: str | None = None
        if not self.render_only:
            try:
                self.controller_type = detect_controller_type()
                logger.info(f"Controller type detected: {self.controller_type}")
            except ValueError as e:
                # Exit gracefully if controller detection fails
                typer.secho(
                    f"\n❌ Controller detection failed:\n{e}",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(1) from None

    def run_tests(self) -> CombinedResults:
        """Main entry point for combined test execution.

        Handles development modes (PyATS only, Robot only) and production mode (combined).
        Dev mode flags act as filters - they restrict which test types run but use the
        same execution flow, dashboard generation, and summary output.

        Returns:
            CombinedResults with per-framework test results
        """
        # Note: Output directory and merged data file created by main.py

        # Print dev mode warnings if applicable (skip in render-only mode)
        if self.dev_pyats_only and not self.render_only:
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
            return CombinedResults()

        # Build combined results from individual orchestrators
        combined_results = CombinedResults()

        if has_pyats and not self.render_only:
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
                dry_run=self.dry_run,
            )
            if self.max_parallel_devices is not None:
                pyats_orchestrator.max_parallel_devices = self.max_parallel_devices

            # PyATS returns PyATSResults with .api and .d2d attributes
            pyats_results = pyats_orchestrator.run_tests()
            combined_results.api = pyats_results.api
            combined_results.d2d = pyats_results.d2d

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
                robot_results = robot_orchestrator.run_tests()
                combined_results.robot = robot_results
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
                # Record error in robot results
                combined_results.robot = TestResults.from_error(str(e))

        if not self.render_only:
            typer.echo("\n📊 Generating combined dashboard...")
            logger.debug(
                f"Calling CombinedReportGenerator with results: {combined_results}"
            )

            combined_generator = CombinedReportGenerator(self.output_dir)
            combined_path = combined_generator.generate_combined_summary(
                combined_results
            )
            if combined_path:
                typer.echo(f"   ✅ Combined dashboard: {combined_path}")

            self._print_execution_summary(has_pyats, has_robot, combined_results)

        return combined_results

    @staticmethod
    def _check_python_version() -> None:
        """Defense-in-depth for programmatic usage that bypasses the CLI."""
        check_and_exit_if_unsupported_macos_python()

    def _discover_test_types(self) -> tuple[bool, bool]:
        """Discover which test types are present in the templates directory.

        Returns:
            Tuple of (has_pyats, has_robot)
        """
        # Build list of directories to exclude from PyATS discovery
        exclude_paths: list[Path] = []
        if self.filters_path:
            exclude_paths.append(self.filters_path)
        if self.tests_path:
            exclude_paths.append(self.tests_path)

        # PyATS discovery - use has_pyats_tests() for efficient early exit
        has_pyats = False
        try:
            test_discovery = TestDiscovery(
                self.templates_dir, exclude_paths=exclude_paths
            )
            has_pyats = test_discovery.has_pyats_tests()
            if has_pyats:
                logger.debug("Found PyATS test files")
        except Exception as e:
            logger.debug(f"\nPyATS discovery failed (no PyATS tests found): {e}\n")

        # Robot discovery - simple existence check (RobotWriter handles the rest)
        # Local helper with early exit for efficiency - stops directory traversal on first match
        def has_robot_files() -> bool:
            robot_extensions = {".robot", ".resource", ".j2"}
            for _, _, filenames in os.walk(self.templates_dir):
                for f in filenames:
                    if os.path.splitext(f)[1] in robot_extensions:
                        return True
            return False

        has_robot = has_robot_files()
        if has_robot:
            logger.debug("Found Robot template files")

        return has_pyats, has_robot

    def _print_execution_summary(
        self, has_pyats: bool, has_robot: bool, results: CombinedResults | None = None
    ) -> None:
        """Print execution summary with statistics."""
        typer.echo("\n" + "=" * 70)
        typer.echo("📋 Combined Test Execution Summary")
        typer.echo("=" * 70)

        # Show overall stats if available
        if results:
            typer.echo("\n📊 Overall Results:")
            typer.echo(f"   Total: {results.total} tests")
            typer.echo(f"   ✅ Passed: {results.passed}")
            typer.echo(f"   ❌ Failed: {results.failed}")
            typer.echo(f"   ⊘ Skipped: {results.skipped}")

            # Combined dashboard is the main entry point
            if not self.render_only:
                typer.echo("\n🎯 Combined Dashboard:")
                combined_dashboard = self.output_dir / COMBINED_SUMMARY_FILENAME
                if combined_dashboard.exists():
                    typer.echo(f"   📊 {combined_dashboard}")
                    typer.echo("   (Aggregated results from all test frameworks)")

        if has_robot:
            typer.echo("\n✅ Robot Framework tests: Completed")
            typer.echo(f"   📁 Results: {self.output_dir}/{ROBOT_RESULTS_DIRNAME}/")
            if results and results.robot is not None:
                robot_stats = results.robot
                typer.echo(
                    f"   📊 {robot_stats.total} tests: "
                    f"{robot_stats.passed} passed, {robot_stats.failed} failed"
                )
            if not self.render_only:
                typer.echo(
                    f"   📊 Summary: {self.output_dir}/{ROBOT_RESULTS_DIRNAME}/{SUMMARY_REPORT_FILENAME}"
                )
                typer.echo(
                    f"   📊 Detailed: {self.output_dir}/{ROBOT_RESULTS_DIRNAME}/log.html"
                )

        if has_pyats:
            typer.echo("\n✅ PyATS tests: Completed")
            typer.echo(f"   📁 Results: {self.output_dir}/{PYATS_RESULTS_DIRNAME}/")
            api_summary = (
                self.output_dir
                / PYATS_RESULTS_DIRNAME
                / "api"
                / HTML_REPORTS_DIRNAME
                / SUMMARY_REPORT_FILENAME
            )
            d2d_summary = (
                self.output_dir
                / PYATS_RESULTS_DIRNAME
                / "d2d"
                / HTML_REPORTS_DIRNAME
                / SUMMARY_REPORT_FILENAME
            )
            if api_summary.exists():
                typer.echo(f"   📊 API Summary: {api_summary}")
            if d2d_summary.exists():
                typer.echo(f"   📊 D2D Summary: {d2d_summary}")

        typer.echo(
            f"\n📄 Merged data model: {self.output_dir}/{self.merged_data_filename}"
        )
        typer.echo("=" * 70)
