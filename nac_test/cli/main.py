# -*- coding: utf-8 -*-

# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

import logging
import sys
import time  #  -- ANDREA REMOVE AFTER MVP
from datetime import datetime  #  -- ANDREA REMOVE AFTER MVP

import errorhandler

import typer
from typing_extensions import Annotated
from enum import Enum

from pathlib import Path

import nac_test.pabot
import nac_test.robot_writer
from nac_test.pyats.orchestrator import PyATSOrchestrator


app = typer.Typer(add_completion=False)

logger = logging.getLogger(__name__)

error_handler = errorhandler.ErrorHandler()


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
    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(lev)
    error_handler.reset()


class VerbosityLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def version_callback(value: bool) -> None:
    if value:
        print(f"nac-test, version {nac_test.__version__}")
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
        help="Run PyATS tests instead of Robot Framework tests (MVP feature).",
        envvar="NAC_TEST_PYATS",
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
    verbosity: Verbosity = VerbosityLevel.WARNING,
    version: Version = False,
    merged_data_filename: MergedDataFilename = "merged_data_model_test_variables.yaml",
) -> None:
    """A CLI tool to render and execute Robot Framework tests using Jinja templating."""
    configure_logging(verbosity)

    if pyats:
        # PyATS execution path
        orchestrator = PyATSOrchestrator(data, templates, output, merged_data_filename)
        orchestrator.run_tests()
    else:
        # Robot Framework execution path
        writer = nac_test.robot_writer.RobotWriter(
            data, filters, tests, include, exclude
        )

        # Start timing the rendering process -- ANDREA REMOVE AFTER MVP
        print(
            f"Starting template rendering at {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}"
        )
        render_start_time = time.time()
        #  -- ANDREA REMOVE AFTER MVP

        writer.write(templates, output)
        writer.write_merged_data_model(output, merged_data_filename)

        # End timing the rendering process -- ANDREA REMOVE AFTER MVP
        render_end_time = time.time()
        render_duration = render_end_time - render_start_time
        print(
            f"Template rendering completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}"
        )
        print(f"Total rendering time: {render_duration:.3f} seconds")
        #  -- ANDREA REMOVE AFTER MVP
        if not render_only:
            nac_test.pabot.run_pabot(
                output, include, exclude, dry_run, verbosity == VerbosityLevel.DEBUG
            )
    exit()


def exit() -> None:
    if error_handler.fired:
        raise typer.Exit(1)
    else:
        raise typer.Exit(0)
