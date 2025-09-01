# -*- coding: utf-8 -*-

"""Robot Framework orchestration logic for nac-test.

This module provides the RobotOrchestrator class that manages the complete
Robot Framework test execution lifecycle, following the same architectural
pattern as PyATSOrchestrator.
"""

import logging
from pathlib import Path
from typing import List, Optional

import typer

from nac_test.robot.robot_writer import RobotWriter
from nac_test.robot.pabot import run_pabot
from nac_test.utils.logging import VerbosityLevel

logger = logging.getLogger(__name__)


class RobotOrchestrator:
    """Orchestrates Robot Framework test execution with clean directory management.
    
    This class follows the same architectural pattern as PyATSOrchestrator:
    - Receives base output directory from caller
    - Creates its own robot_results subdirectory  
    - Manages complete Robot Framework lifecycle
    - Reuses existing RobotWriter and pabot components (DRY principle)
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
            verbosity: Logging verbosity level
        """
        self.data_paths = data_paths
        self.templates_dir = Path(templates_dir)
        self.base_output_dir = Path(output_dir)  # Store base directory for merged data file access
        self.output_dir = self.base_output_dir / "robot_results"  # Robot works in its own subdirectory
        self.merged_data_filename = merged_data_filename
        
        # Robot-specific parameters
        self.filters_path = filters_path
        self.tests_path = tests_path
        self.include_tags = include_tags or []
        self.exclude_tags = exclude_tags or []
        self.render_only = render_only
        self.dry_run = dry_run
        self.verbosity = verbosity

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
        1. Creates the robot_results output directory
        2. Renders Robot test templates using RobotWriter
        3. Creates merged data model file in robot_results directory
        4. Executes tests using pabot (unless render_only mode)
        
        Follows the same pattern as PyATSOrchestrator.run_tests().
        """
        # Create Robot Framework output directory (orchestrator owns its structure)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Robot Framework orchestrator initialized")
        logger.info(f"Base output directory: {self.base_output_dir}")
        logger.info(f"Robot working directory: {self.output_dir}")
        logger.info(f"Templates directory: {self.templates_dir}")
        
        # Phase 1: Template rendering (delegate to existing RobotWriter)
        typer.echo("📝 Rendering Robot Framework templates...")
        self.robot_writer.write(self.templates_dir, self.output_dir)
        
        # Phase 2: Create merged data model in Robot working directory
        # Note: Robot tests expect the merged data file in their working directory
        typer.echo("📄 Creating merged data model for Robot tests...")
        self.robot_writer.write_merged_data_model(self.output_dir, self.merged_data_filename)
        
        # Phase 3: Test execution (unless render-only mode)
        if not self.render_only:
            typer.echo("🤖 Executing Robot Framework tests...")
            run_pabot(
                path=self.output_dir,
                include=self.include_tags,
                exclude=self.exclude_tags,
                dry_run=self.dry_run,
                verbose=(self.verbosity == VerbosityLevel.DEBUG),
            )
            typer.echo("✅ Robot Framework tests completed")
        else:
            typer.echo("✅ Robot Framework templates rendered (render-only mode)")

    def get_output_summary(self) -> dict:
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
