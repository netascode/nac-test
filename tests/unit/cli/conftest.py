# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
from tempfile import TemporaryDirectory

from click.testing import Result
from typer.testing import CliRunner

from nac_test.cli.main import app

runner = CliRunner()


def run_cli_with_temp_dirs(additional_args: list[str] | None = None) -> Result:
    """Run CLI with temporary directories for data, templates, and output."""
    args = additional_args or []
    with (
        TemporaryDirectory() as temp_data,
        TemporaryDirectory() as temp_templates,
        TemporaryDirectory() as temp_output,
    ):
        return runner.invoke(
            app, ["-d", temp_data, "-t", temp_templates, "-o", temp_output] + args
        )
