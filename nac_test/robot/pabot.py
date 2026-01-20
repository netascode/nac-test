# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# -*- coding: utf-8 -*-

# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

from pathlib import Path

import pabot.pabot


def run_pabot(
    path: Path,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Run pabot"""
    if include is None:
        include = []
    if exclude is None:
        exclude = []
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
    try:
        pabot.pabot.main(args)
    except SystemExit as e:
        # Pabot calls sys.exit() when done - this is normal behavior
        # Don't re-raise to allow nac-test runtime tracking to complete
        if e.code != 0:
            # Non-zero exit code indicates failure - re-raise to maintain error handling
            raise
