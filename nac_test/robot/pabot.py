# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

import logging
from pathlib import Path

import pabot.pabot

from nac_test.core.constants import (
    XUNIT_XML,
)
from nac_test.core.types import ValidatedRobotArgs

logger = logging.getLogger(__name__)


def run_pabot(
    path: Path,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    processes: int | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    default_robot_loglevel: str | None = None,
    ordering_file: Path | None = None,
    extra_args: ValidatedRobotArgs | None = None,
) -> int:
    """Run pabot against rendered Robot suites in the output directory.

    Args:
        path: Robot output directory, also containing the rendered Robot suites.
        include: Robot include tags to pass through to pabot.
        exclude: Robot exclude tags to pass through to pabot.
        processes: Number of pabot worker processes to use.
        dry_run: Whether to execute Robot in dry-run mode.
        verbose: Whether to enable pabot verbose output.
        default_robot_loglevel: Default Robot Framework log level, can be overridden via extra_args.
        ordering_file: Optional pabot ordering file for test-level splitting.
        extra_args: Pre-parsed, validated Robot Framework arguments. Uses .args to
            extend pabot's command line and .robot_opts to check for a loglevel
            override without re-parsing the raw string list.

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
    pabot_args = [
        "--pabotlib",
        "--pabotlibport",
        "0",
    ]

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

    if extra_args:
        robot_args.extend(extra_args.args)

    # Respect explicit --loglevel in extra_args; default only applies if absent
    if default_robot_loglevel and not (
        extra_args and extra_args.robot_opts.get("loglevel")
    ):
        robot_args.extend(["--loglevel", default_robot_loglevel])

    args = pabot_args + robot_args + [str(abs_path)]
    logger.info("Running pabot with args: %s", " ".join(args))
    exit_code: int = pabot.pabot.main_program(args)
    logger.info(f"Pabot execution completed with exit code {exit_code}")
    return exit_code
