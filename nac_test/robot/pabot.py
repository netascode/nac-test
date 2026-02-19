# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import logging
from pathlib import Path

import pabot.pabot
from pabot.arguments import parse_args
from robot.errors import DataError

from nac_test.core.constants import EXIT_INVALID_ARGS

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
    ordering_file: Path | None = None,
    extra_args: list[str] | None = None,
) -> int:
    """Run pabot"""
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
        robot_args.extend(["--loglevel", "DEBUG"])
    if dry_run:
        robot_args.append("--dryrun")
    for i in include:
        robot_args.extend(["--include", i])
    for e in exclude:
        robot_args.extend(["--exclude", e])
    robot_args.extend(
        [
            "--outputdir",
            str(path),
            "--skiponfailure",
            "non-critical",
            "--xunit",
            "xunit.xml",
        ]
    )

    # Parse and validate extra arguments against valid robot arguments. Exceptions related to illegal
    # args are caught here, and a rc is returned
    if extra_args:
        try:
            validated_extra_args = parse_and_validate_extra_args(extra_args)
        except (ValueError, DataError):
            return EXIT_INVALID_ARGS
        robot_args.extend(validated_extra_args)

    args = pabot_args + robot_args + [str(path)]
    logger.info("Running pabot with args: %s", " ".join(args))
    exit_code: int = pabot.pabot.main_program(args)
    logger.info(f"Pabot execution completed with exit code {exit_code}")
    return exit_code
