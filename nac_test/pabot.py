# -*- coding: utf-8 -*-

# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

from pathlib import Path

import pabot.pabot


def run_pabot(
    path: Path,
    include: list[str] = [],
    exclude: list[str] = [],
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Run pabot"""
    args = ["--pabotlib", "--pabotlibport", "0"]
    if verbose:
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
            str(path),
        ]
    )
    pabot.pabot.main(args)
