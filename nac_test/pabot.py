# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

from pathlib import Path

import pabot.pabot


def run_pabot(
    path: Path,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    processes: int | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Run pabot"""
    include = include or []
    exclude = exclude or []
    args = ["--pabotlib", "--pabotlibport", "0"]
    if processes is not None:
        args.extend(["--processes", str(processes)])
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
