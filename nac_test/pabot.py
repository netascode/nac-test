# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

import sys
import tempfile
from pathlib import Path

from pabot.pabot import main_program as run_pabot_main  # use pabot API to run
from robot import rebot_cli

SPLIT_TAG = "nac:testlevelsplit"

def _run_pabot_with_args(
    path: Path,
    outdir: Path,
    include: list[str],
    exclude: list[str],
    dry_run: bool,
    verbose: bool,
    testlevelsplit: bool,
) -> None:
    """Helper function to run pabot with specified arguments

    The include/exclude logic is a bit more complex as we use the "testlevelsplit"
    tag to indicate suites which have been refactored for testlevelsplit.
    """
    args = ["--pabotlib", "--pabotlibport", "0"]

    if testlevelsplit:
        args.append("--testlevelsplit")
        # avoid this internal tag to show up in the results/reports
        args.extend(["--tagstatexclude", SPLIT_TAG])

        # --include flags passed by the user are ORed together, so we need to add "AND testlevelsplit"
        # to each of them
        include_condition = "AND" + SPLIT_TAG
    else:
        include_condition = ""

    if len(include) > 0:
        # use provided tags
        for i in include:
            if i == SPLIT_TAG:
                raise ValueError(f"Cannot use reserved tag {SPLIT_TAG} in include")
        args.extend(["--include", f"{i}{include_condition}"])
    elif testlevelsplit:
        #  no user tags, but testlevelsplit is enabled, only run tests with testlevelsplit tag
        args.extend(["--include", SPLIT_TAG])

    for e in exclude:
        # no need for complex logic here, just exclude the tags
        args.extend(["--exclude", e])
    if not testlevelsplit:
        args.extend(["--exclude", SPLIT_TAG])

    if verbose:
        args.extend(["--verbose", "--loglevel", "TRACE"])
    if dry_run:
        args.append("--dryrun")

    args.extend(
        [
            "-d",
            str(outdir),
            "--skiponfailure",
            "non-critical",
            str(path),
        ]
    )
    print("Running pabot with args:", ' '.join(args))
    return run_pabot_main(args)


def run_pabot(
    path: Path,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Run pabot twice: once with --testlevelsplit and once without"""
    include = include or []
    exclude = exclude or []

    rc = -1
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdirname = Path(tmpdirname)
        try:
            # First run: with --testlevelsplit and _testlevelsplit tag
            _run_pabot_with_args(
                path, tmpdirname / 'out1',
                include, exclude, dry_run, verbose,
                testlevelsplit=True)

            # Second run: without --testlevelsplit
            _run_pabot_with_args(
                path, tmpdirname / 'out2',
                include, exclude, dry_run, verbose,
                testlevelsplit=False)

        finally:
            # Merge results
            rebot_args = [
                "--name", "NAC Test Results",
                "--merge",
                "--outputdir", str(path),
                "--xunit", "xunit.xml",
                "--output", "output.xml",
            ]
            found_outputs = False
            for d in [tmpdirname / 'out1' , tmpdirname / 'out2']:
                if (d / "output.xml").exists():
                    rebot_args.extend([str(d / "output.xml")])
                    found_outputs = True
            if found_outputs:
                print("Running rebot with args:", ' '.join(rebot_args))

                rc = rebot_cli(rebot_args)
            else:
                raise RuntimeError("No output.xml files found to merge")

    sys.exit(rc)
