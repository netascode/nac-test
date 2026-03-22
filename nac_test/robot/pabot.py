# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import logging
from pathlib import Path

import pabot.pabot
from pabot.arguments import parse_args
from robot.errors import DataError

from nac_test.core.constants import (
    EXIT_DATA_ERROR,
    XUNIT_XML,
)

logger = logging.getLogger(__name__)


def parse_and_validate_extra_args(extra_args: list[str]) -> list[str]:
    """
    Parse and validate extra Robot Framework arguments using pabot's parse_args.

    Args:
        extra_args: Additional Robot Framework arguments to pass to pabot

    Returns:
        Validated Robot Framework arguments (no datasources)

    Raises:
        ValueError: If extra_args contain datasources/files
        DataError: If extra_args contain invalid Robot Framework arguments
    """
    if not extra_args:
        return []

    try:
        robot_options, datasources, pabot_args, _ = parse_args(
            extra_args + ["__dummy__.robot"]
        )
    except DataError as e:
        logger.warning(
            f"Invalid Robot Framework arguments: {e}"
        )  # Changed from error to warning - this is a handled condition
        raise

    # Check if datasources were provided in extra_args (excluding our dummy)
    actual_datasources = [ds for ds in datasources if ds != "__dummy__.robot"]
    if actual_datasources:
        error_msg = f"Datasources/files are not allowed in extra arguments: {', '.join(actual_datasources)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Check if any pabot-specific arguments were provided
    # Pabot-specific options that should not be in extra_args
    pabot_specific_options = [
        "testlevelsplit",
        "pabotlib",
        "pabotlibhost",
        "pabotlibport",
        "processes",
        "verbose",
        "ordering",
        "suitesfrom",
        "resourcefile",
        "pabotprerunmodifier",
        "artifacts",
        "artifactsinsubfolders",
    ]

    pabot_options_provided = []
    for extra_arg in extra_args:
        if extra_arg.startswith("--"):
            option_name = extra_arg[2:]
            if option_name in pabot_specific_options:
                pabot_options_provided.append(extra_arg)

    if pabot_options_provided:
        error_msg = f"Pabot-specific arguments are not allowed in extra arguments: {', '.join(pabot_options_provided)}. Only Robot Framework options are accepted."
        logger.error(error_msg)
        raise ValueError(error_msg)

    return extra_args


def run_pabot(
    path: Path,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    processes: int | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    robot_loglevel: str | None = None,
    ordering_file: Path | None = None,
    extra_args: list[str] | None = None,
) -> int:
    """Run pabot against rendered Robot suites in the output directory.

    Args:
        path: Robot output directory, also containing the rendered Robot suites.
        include: Robot include tags to pass through to pabot.
        exclude: Robot exclude tags to pass through to pabot.
        processes: Number of pabot worker processes to use.
        dry_run: Whether to execute Robot in dry-run mode.
        verbose: Whether to enable pabot verbose output.
        robot_loglevel: Robot Framework log level to pass through.
        ordering_file: Optional pabot ordering file for test-level splitting.
        extra_args: Additional validated Robot Framework arguments.

    Returns:
        int: Pabot exit code.

    Notes:
        The output path is resolved to an absolute path before building pabot
        arguments. Relative paths can otherwise be resolved twice by
        Robot/Pabot, which creates nested output directories and breaks later
        artifact discovery.
    """
    include = include or []
    exclude = exclude or []
    robot_args: list[str] = []
    pabot_args = ["--pabotlib", "--pabotlibport", "0"]

    if ordering_file and ordering_file.exists():
        pabot_args.extend(["--testlevelsplit", "--ordering", str(ordering_file)])
        # remove possible leftover ".pabotsuitenames" as it can interfere with ordering
        Path(".pabotsuitenames").unlink(missing_ok=True)
    if processes is not None:
        pabot_args.extend(["--processes", str(processes)])
    if verbose:
        pabot_args.append("--verbose")
    if dry_run:
        robot_args.append("--dryrun")
    for i in include:
        robot_args.extend(["--include", i])
    for e in exclude:
        robot_args.extend(["--exclude", e])
    # Use absolute paths for pabot output arguments. Relative paths can be resolved
    # twice by Robot/Pabot, which writes results under nested output dirs and breaks
    # later result discovery.
    abs_path = path.resolve()
    robot_args.extend(
        [
            "--outputdir",
            str(abs_path),
            "--skiponfailure",
            "non-critical",
            "--xunit",
            str(abs_path / XUNIT_XML),
        ]
    )

    # Parse and validate extra arguments against valid robot arguments. Exceptions related to illegal
    # args are caught here, and a rc is returned
    if extra_args:
        try:
            validated_extra_args = parse_and_validate_extra_args(extra_args)
        except (ValueError, DataError):
            return EXIT_DATA_ERROR
        robot_args.extend(validated_extra_args)

    if robot_loglevel:
        robot_args.extend(["--loglevel", robot_loglevel])

    args = pabot_args + robot_args + [str(abs_path)]
    logger.info("Running pabot with args: %s", " ".join(args))
    exit_code: int = pabot.pabot.main_program(args)
    logger.info(f"Pabot execution completed with exit code {exit_code}")
    return exit_code
