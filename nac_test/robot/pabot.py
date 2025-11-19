# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
import logging
from pathlib import Path

import pabot.pabot

logger = logging.getLogger(__name__)


def run_pabot(
    path: Path,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    processes: int | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    ordering_file: Path | None = None,
) -> None:
    """Run pabot"""
    include = include or []
    exclude = exclude or []
    args = ["--pabotlib", "--pabotlibport", "0"]

    if ordering_file and ordering_file.exists():
        args.extend(["--testlevelsplit", "--ordering", str(ordering_file)])
        # remove possible leftover ".pabotsuitenames" as it can interfere with ordering
        Path(".pabotsuitenames").unlink(missing_ok=True)
    if processes is not None:
        args.extend(["--processes", str(processes)])
    if verbose:
        args.extend(["--verbose", "--loglevel", "DEBUG"])
    if dry_run:
        args.append("--dryrun")
    for i in include:
        args.extend(["--include", i])
    for e in exclude:
        args.extend(["--exclude", e])
    args.extend(
        [
            "--outputdir",
            str(path),
            "--skiponfailure",
            "non-critical",
            "--xunit",
            "xunit.xml",
            str(path),
        ]
    )
    logger.info("Running pabot with args: %s", " ".join(args))
    pabot.pabot.main(args)
