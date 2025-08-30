# -*- coding: utf-8 -*-

# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

import logging
from typing import Optional

import errorhandler

import typer
from typing_extensions import Annotated

from pathlib import Path

import nac_test
from nac_test.combined_orchestrator import CombinedOrchestrator
from nac_test.utils.logging import configure_logging, VerbosityLevel
from nac_test.data_merger import DataMerger


app = typer.Typer(add_completion=False)

logger = logging.getLogger(__name__)

error_handler = errorhandler.ErrorHandler()


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
    list[str],
    typer.Option(
        "-i",
        "--include",
        help="Selects the test cases by tag (include).",
        envvar="NAC_TEST_INCLUDE",
    ),
]


Exclude = Annotated[
    list[str],
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


PyATS = Annotated[
    bool,
    typer.Option(
        "--pyats",
        help="[DEV ONLY] Run only PyATS tests (skips Robot Framework). Use for faster development cycles.",
        envvar="NAC_TEST_PYATS",
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


Version = Annotated[
    bool,
    typer.Option(
        "--version",
        callback=version_callback,
        help="Display version number.",
        is_eager=True,
    ),
]


@app.command()
def main(
    data: Data,
    templates: Templates,
    output: Output,
    filters: Filters = None,
    tests: Tests = None,
    include: Include = [],
    exclude: Exclude = [],
    render_only: RenderOnly = False,
    dry_run: DryRun = False,
    pyats: PyATS = False,
    max_parallel_devices: Optional[MaxParallelDevices] = None,
    verbosity: Verbosity = VerbosityLevel.WARNING,
    version: Version = False,
    merged_data_filename: MergedDataFilename = "merged_data_model_test_variables.yaml",
) -> None:
    """A CLI tool to render and execute Robot Framework tests using Jinja templating."""
    configure_logging(verbosity, error_handler)

    # Create output directory and shared merged data file (SOT)
    output.mkdir(parents=True, exist_ok=True)
    merged_data = DataMerger.merge_data_files(data)
    DataMerger.write_merged_data_model(merged_data, output, merged_data_filename)

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
        verbosity=verbosity,
        dev_pyats_only=pyats,
    )
    
    orchestrator.run_tests()
    exit()


def exit() -> None:
    if error_handler.fired:
        raise typer.Exit(1)
    else:
        raise typer.Exit(0)
