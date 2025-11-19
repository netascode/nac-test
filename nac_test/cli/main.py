# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import logging
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

import nac_test.pabot
import nac_test.robot_writer

# typer exceptions are BIG (albeit colorful), I feel for a program
# with this complextiy logging everything is not required, hence disabling
# them
app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)

logger = logging.getLogger(__name__)

ORDERING_FILE = "ordering.txt"


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


Processes = Annotated[
    int | None,
    typer.Option(
        "--processes",
        help="Number of parallel processes for test execution (pabot --processes option), default is max(2, cpu count).",
        envvar="NAC_TEST_PROCESSES",
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
        print(f"rc = {rc}")
    else:
        rc = 0
    raise typer.Exit(code=rc)
