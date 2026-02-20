# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Platform-specific utilities for nac-test framework."""

import sys

import typer

from nac_test.core.constants import IS_UNSUPPORTED_MACOS_PYTHON


def check_and_exit_if_unsupported_macos_python() -> None:
    """Exit with code 1 if running on macOS with Python < 3.12.

    Raises:
        typer.Exit: With code 1 if running unsupported macOS Python.
    """
    if IS_UNSUPPORTED_MACOS_PYTHON:
        typer.secho(
            f"\nError: Python {sys.version_info.major}.{sys.version_info.minor} "
            "on macOS is not supported.",
            fg=typer.colors.RED,
            bold=True,
            err=True,
        )
        typer.echo(
            "Please use Python 3.12 or higher on macOS.\n"
            "\n"
            "Some common ways to install it:\n"
            "  • brew install python@3.12\n"
            "  • uv python install 3.12\n"
            "  • pyenv install 3.12",
            err=True,
        )
        raise typer.Exit(1)
