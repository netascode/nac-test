# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import logging
<<<<<<< HEAD
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
=======
from typing import Optional

import errorhandler

import typer
from typing_extensions import Annotated

from pathlib import Path
>>>>>>> 903a1a2

import nac_test
from nac_test.combined_orchestrator import CombinedOrchestrator
from nac_test.utils.logging import configure_logging, VerbosityLevel
from nac_test.data_merger import DataMerger
from datetime import datetime

# typer exceptions are BIG (albeit colorful), I feel for a program
# with this complextiy logging everything is not required, hence disabling
# them
app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)

logger = logging.getLogger(__name__)

ORDERING_FILE = "ordering.txt"


<<<<<<< HEAD
def configure_logging(level: str) -> None:
    if level == "DEBUG":
        lev = logging.DEBUG
    elif level == "INFO":
        lev = logging.INFO
    elif level == "WARNING":
        lev = logging.WARNING
    elif level == "ERROR":
        lev = logging.ERROR
    else:
        lev = logging.CRITICAL

    logging.basicConfig(
        level=lev, format="%(levelname)s - %(message)s", stream=sys.stdout, force=True
    )


class VerbosityLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


=======
>>>>>>> 903a1a2
def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"nac-test, version {nac_test.__version__}")
        raise typer.Exit()


Verbosity = Annotated[
    VerbosityLevel,
    typer.Option(
        "-v",
        "--verbosity",
        help="Verbosity level.",
        envvar="NAC_VALIDATE_VERBOSITY",
        is_eager=True,
    ),
]


Data = Annotated[
    list[Path],
    typer.Option(
        "-d",
        "--data",
        exists=True,
        dir_okay=True,
        file_okay=True,
        help="Path to data YAML files.",
        envvar="NAC_TEST_DATA",
    ),
]


Templates = Annotated[
    Path,
    typer.Option(
        "-t",
        "--templates",
        exists=True,
        dir_okay=True,
        file_okay=False,
        help="Path to test templates.",
        envvar="NAC_TEST_TEMPLATES",
    ),
]


Filters = Annotated[
    Path | None,
    typer.Option(
        "-f",
        "--filters",
        exists=True,
        dir_okay=True,
        file_okay=False,
        help="Path to Jinja filters.",
        envvar="NAC_TEST_FILTERS",
    ),
]


Tests = Annotated[
    Path | None,
    typer.Option(
        "--tests",
        exists=True,
        dir_okay=True,
        file_okay=False,
        help="Path to Jinja tests.",
        envvar="NAC_TEST_TESTS",
    ),
]


Output = Annotated[
    Path,
    typer.Option(
        "-o",
        "--output",
        exists=False,
        dir_okay=True,
        file_okay=False,
        help="Path to output directory.",
        envvar="NAC_TEST_OUTPUT",
    ),
]


Include = Annotated[
    list[str] | None,
    typer.Option(
        "-i",
        "--include",
        help="Selects the test cases by tag (include).",
        envvar="NAC_TEST_INCLUDE",
    ),
]


Exclude = Annotated[
    list[str] | None,
    typer.Option(
        "-e",
        "--exclude",
        help="Selects the test cases by tag (exclude).",
        envvar="NAC_TEST_EXCLUDE",
    ),
]


MergedDataFilename = Annotated[
    str,
    typer.Option(
        "-m",
        "--merged-data-filename",
        help="Filename for the merged data model YAML file.",
    ),
]


RenderOnly = Annotated[
    bool,
    typer.Option(
        "--render-only",
        help="Only render tests without executing them.",
        envvar="NAC_TEST_RENDER_ONLY",
    ),
]


DryRun = Annotated[
    bool,
    typer.Option(
        "--dry-run",
        help="Dry run flag. See robot dry run mode.",
        envvar="NAC_TEST_DRY_RUN",
    ),
]


<<<<<<< HEAD
Processes = Annotated[
    int | None,
    typer.Option(
        "--processes",
        help="Number of parallel processes for test execution (pabot --processes option), default is max(2, cpu count).",
        envvar="NAC_TEST_PROCESSES",
=======
PyATS = Annotated[
    bool,
    typer.Option(
        "--pyats",
        help="[DEV ONLY] Run only PyATS tests (skips Robot Framework). Use for faster development cycles.",
        envvar="NAC_TEST_PYATS",
    ),
]


Robot = Annotated[
    bool,
    typer.Option(
        "--robot",
        help="[DEV ONLY] Run only Robot Framework tests (skips PyATS). Use for faster development cycles.",
        envvar="NAC_TEST_ROBOT",
    ),
]


MaxParallelDevices = Annotated[
    int,
    typer.Option(
        "--max-parallel-devices",
        help="Maximum number of devices to test in parallel for SSH/D2D tests. If not specified, automatically calculated based on system resources. Use this to set a lower limit if needed.",
        envvar="NAC_TEST_MAX_PARALLEL_DEVICES",
        min=1,
        max=500,
    ),
]


MinimalReports = Annotated[
    bool,
    typer.Option(
        "--minimal-reports",
        help="Only include detailed command outputs for failed/errored tests in HTML reports (80-95%% artifact size reduction).",
        envvar="NAC_TEST_MINIMAL_REPORTS",
>>>>>>> 903a1a2
    ),
]


Version = Annotated[
    bool,
    typer.Option(
        "--version",
        callback=version_callback,
        help="Display version number.",
        is_eager=True,
    ),
]


@app.command(
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True}
)
def main(
    ctx: typer.Context,
    data: Data,
    templates: Templates,
    output: Output,
    filters: Filters = None,
    tests: Tests = None,
    include: Include = None,
    exclude: Exclude = None,
    render_only: RenderOnly = False,
    dry_run: DryRun = False,
<<<<<<< HEAD
    processes: Processes = None,
    verbosity: Verbosity = VerbosityLevel.WARNING,
    version: Version = False,  # noqa: ARG001
) -> None:
    """
    A CLI tool to render and execute Robot Framework tests using Jinja templating.

    Additional Robot Framework options can be passed at the end of the command to
    further control test execution (e.g., --variable, --listener, --loglevel).
    These are appended to the pabot invocation. Pabot-specific options and test
    files/directories are not supported and will result in an error.
    """
    configure_logging(verbosity)

    if "NAC_TEST_NO_TESTLEVELSPLIT" not in os.environ:
        ordering_file = output / ORDERING_FILE
=======
    pyats: PyATS = False,
    robot: Robot = False,
    max_parallel_devices: Optional[MaxParallelDevices] = None,
    minimal_reports: MinimalReports = False,
    verbosity: Verbosity = VerbosityLevel.WARNING,
    version: Version = False,
    merged_data_filename: MergedDataFilename = "merged_data_model_test_variables.yaml",
) -> None:
    """A CLI tool to render and execute Robot Framework tests using Jinja templating."""
    configure_logging(verbosity, error_handler)

    # Validate development flag combinations
    if pyats and robot:
        typer.echo(
            typer.style(
                "Error: Cannot use both --pyats and --robot flags simultaneously.",
                fg=typer.colors.RED,
            )
        )
        typer.echo(
            "Use one development flag at a time, or neither for combined execution."
        )
        raise typer.Exit(1)

    # Create output directory and shared merged data file (SOT)
    output.mkdir(parents=True, exist_ok=True)

    # Merge data files with timing
    start_time = datetime.now()
    start_timestamp = start_time.strftime("%H:%M:%S")
    typer.echo(f"\n\n[{start_timestamp}] 📄 Merging data model files...")

    merged_data = DataMerger.merge_data_files(data)
    DataMerger.write_merged_data_model(merged_data, output, merged_data_filename)

    end_time = datetime.now()
    end_timestamp = end_time.strftime("%H:%M:%S")
    duration = (end_time - start_time).total_seconds()
    duration_str = (
        f"{duration:.1f}s"
        if duration < 60
        else f"{int(duration // 60)}m {duration % 60:.0f}s"
    )
    typer.echo(f"[{end_timestamp}] ✅ Data model merging completed ({duration_str})")

    # CombinedOrchestrator - handles both dev and production modes (uses pre-created merged data)
    orchestrator = CombinedOrchestrator(
        data_paths=data,
        templates_dir=templates,
        output_dir=output,
        merged_data_filename=merged_data_filename,
        filters_path=filters,
        tests_path=tests,
        include_tags=include,
        exclude_tags=exclude,
        render_only=render_only,
        dry_run=dry_run,
        max_parallel_devices=max_parallel_devices,
        minimal_reports=minimal_reports,
        verbosity=verbosity,
        dev_pyats_only=pyats,
        dev_robot_only=robot,
    )

    # Track total runtime for benchmarking
    runtime_start = datetime.now()

    try:
        orchestrator.run_tests()
    except Exception as e:
        # Ensure runtime is shown even if orchestrator fails
        typer.echo(f"Error during execution: {e}")
        raise

    # Display total runtime before exit
    runtime_end = datetime.now()
    total_runtime = (runtime_end - runtime_start).total_seconds()

    # Format like other timing outputs
    if total_runtime < 60:
        runtime_str = f"{total_runtime:.2f} seconds"
    else:
        minutes = int(total_runtime / 60)
        secs = total_runtime % 60
        runtime_str = f"{minutes} minutes {secs:.2f} seconds"

    typer.echo(f"\nTotal runtime: {runtime_str}")
    exit()


def exit() -> None:
    if error_handler.fired:
        raise typer.Exit(1)
>>>>>>> 903a1a2
    else:
        ordering_file = None

    writer = nac_test.robot_writer.RobotWriter(data, filters, tests, include, exclude)
    writer.write(templates, output, ordering_file=ordering_file)
    if not render_only:
        rc = nac_test.pabot.run_pabot(
            output,
            include,
            exclude,
            processes,
            dry_run,
            verbosity == VerbosityLevel.DEBUG,
            ordering_file=ordering_file,
            extra_args=ctx.args,
        )
    else:
        rc = 0
    raise typer.Exit(code=rc)
