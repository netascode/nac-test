# -*- coding: utf-8 -*-

# Copyright: (c) 2022, Daniel Schmidt <danischm@cisco.com>

import click

data = click.option(
    "-d",
    "--data",
    type=click.Path(exists=True, dir_okay=True, file_okay=True),
    envvar="NAC_TEST_DATA",
    help="Path to data YAML files. (env: NAC_TEST_DATA)",
    required=True,
    multiple=True,
)

templates = click.option(
    "-t",
    "--templates",
    type=click.Path(exists=True, dir_okay=True, file_okay=False),
    envvar="NAC_TEST_TEMPLATES",
    help="Path to test templates. (env: NAC_TEST_TEMPLATES)",
    required=True,
)

filters = click.option(
    "-f",
    "--filters",
    type=click.Path(exists=True, dir_okay=True, file_okay=False),
    envvar="NAC_TEST_FILTERS",
    help="Path to Jinja filters. (env: NAC_TEST_FILTERS)",
    required=False,
)

tests = click.option(
    "--tests",
    type=click.Path(exists=True, dir_okay=True, file_okay=False),
    envvar="NAC_TEST_TESTS",
    help="Path to Jinja tests. (env: NAC_TEST_TESTS)",
    required=False,
)


output = click.option(
    "-o",
    "--output",
    type=click.Path(exists=False, dir_okay=True, file_okay=False),
    envvar="NAC_TEST_OUTPUT",
    help="Path to output directory. (env: NAC_TEST_OUTPUT)",
    required=True,
)

include = click.option(
    "-i",
    "--include",
    envvar="NAC_TEST_INCLUDE",
    help="Selects the test cases by tag (include). (env: NAC_TEST_INCLUDE)",
    required=False,
    multiple=True,
)

exclude = click.option(
    "-e",
    "--exclude",
    envvar="NAC_TEST_EXCLUDE",
    help="Selects the test cases by tag (exclude). (env: NAC_TEST_EXCLUDE)",
    required=False,
    multiple=True,
)

render_only = click.option(
    "--render-only",
    is_flag=True,
    envvar="NAC_TEST_RENDER_ONLY",
    help="Only render tests without executing them. (env: NAC_TEST_RENDER_ONLY)",
)

dry_run = click.option(
    "--dry-run",
    is_flag=True,
    envvar="IAC_DRY_RUN",
    help="Dry run flag. See robot dry run mode. (env: IAC_DRY_RUN)",
    required=False,
)
