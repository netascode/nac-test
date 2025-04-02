# -*- coding: utf-8 -*-

# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

import logging
import sys

import click
import errorhandler

import nac_test.pabot
import nac_test.robot_writer

from . import options

logger = logging.getLogger(__name__)

error_handler = errorhandler.ErrorHandler()


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
    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(lev)
    error_handler.reset()


@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.version_option(nac_test.__version__)
@click.option(
    "-v",
    "--verbosity",
    metavar="LVL",
    is_eager=True,
    type=click.Choice(["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]),
    help="Either CRITICAL, ERROR, WARNING, INFO or DEBUG",
    default="WARNING",
)
@options.data
@options.templates
@options.filters
@options.tests
@options.output
@options.include
@options.exclude
@options.render_only
@options.dry_run
def main(
    verbosity: str,
    data: list[str],
    templates: str,
    filters: str,
    tests: str,
    output: str,
    include: list[str],
    exclude: list[str],
    render_only: bool,
    dry_run: bool,
) -> None:
    """A CLI tool to render and execute Robot Framework tests using Jinja templating."""
    configure_logging(verbosity)

    writer = nac_test.robot_writer.RobotWriter(data, filters, tests, include, exclude)
    writer.write(templates, output)
    if not render_only:
        nac_test.pabot.run_pabot(output, include, exclude, dry_run)
    exit()


def exit() -> None:
    if error_handler.fired:
        sys.exit(1)
    else:
        sys.exit(0)
