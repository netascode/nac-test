# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

import os
import re
from pathlib import Path

import pabot.pabot

ORDERING_FILE = "ordering.txt"

ROBOT_LOGLEVEL_DICT = {
    "TRACE": "TRACE",
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "WARNING": "WARN",
    "ERROR": "ERROR",
}


def run_pabot(
    path: Path,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    dry_run: bool = False,
    verbosity: str = "INFO",
) -> None:
    """Run pabot"""
    include = include or []
    exclude = exclude or []
    args = ["--pabotlib", "--pabotlibport", "0"]

    ordering_file = path / ORDERING_FILE
    if ordering_file.exists():
        with ordering_file.open() as f:
            if re.search(r"^--test ", f.read(), re.MULTILINE):
                args.extend(["--testlevelsplit"])
        args.extend(["--ordering", str(ordering_file)])
        # remove possible leftover ".pabotsuitenames" as it can interfere with ordering
        try:
            os.remove(".pabotsuitenames")
        except FileNotFoundError:
            pass
    if verbosity in ["DEBUG", "TRACE"]:
        args.append("--verbose")
    if dry_run:
        args.append("--dryrun")
    for i in include:
        args.extend(["--include", i])
    for e in exclude:
        args.extend(["--exclude", e])
    args.extend(
        [
            "-d",
            str(path),
            "--skiponfailure",
            "non-critical",
            "-x",
            "xunit.xml",
            "--loglevel",
            ROBOT_LOGLEVEL_DICT.get(verbosity, "INFO"),
            str(path),
        ]
    )

    pabot.pabot.main(args)
