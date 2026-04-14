# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Diagnostic collection module for nac-test CLI.

This module provides functionality to run the nac-test diagnostic shell script,
which collects comprehensive diagnostic information when test execution fails
or encounters issues.
"""

import importlib.resources
import shlex
import subprocess
from pathlib import Path
from typing import NoReturn

import typer

from nac_test.core.constants import EXIT_INVALID_ARGS, IS_WINDOWS


def _find_diagnostic_script() -> Path:
    """Locate the nac-test diagnostic shell script within the package.

    Uses importlib.resources to find the bundled diagnostic script
    in the nac_test.support package.

    Returns:
        Path to the nac-test-diagnostic.sh script.

    Raises:
        FileNotFoundError: If the diagnostic script cannot be found
            in the package resources.
    """
    script_path = importlib.resources.files("nac_test.support").joinpath(
        "nac-test-diagnostic.sh"
    )
    # Convert to Path for consistent interface
    path = Path(str(script_path))
    if not path.exists():
        raise FileNotFoundError(
            f"Diagnostic script not found at {path}. "
            "Please ensure nac-test is properly installed."
        )
    return path


def _reconstruct_command(argv: list[str]) -> str:
    """Reconstruct the original command without the --diagnostic flag."""
    filtered_args = [arg for arg in argv if arg != "--diagnostic"]
    return shlex.join(filtered_args)


def run_diagnostic(output_dir: Path, argv: list[str]) -> NoReturn:
    """Run the diagnostic collection shell script.

    Wraps nac-test execution with pre/post environment and log collection.
    This is invoked from the main CLI entrypoint *after* Typer/Click has
    validated required args, so --diagnostic cannot bypass missing required
    options.

    Args:
        output_dir: Parsed -o/--output value.
        argv: The original sys.argv list.

    Raises:
        typer.Exit: Always raised, with the return code from the diagnostic
            script subprocess.
    """

    if IS_WINDOWS:
        typer.echo(
            typer.style(
                "Error: --diagnostic is supported only on Linux and macOS (requires bash).",
                fg=typer.colors.RED,
            ),
            err=True,
        )
        raise typer.Exit(code=EXIT_INVALID_ARGS)

    script_path = _find_diagnostic_script()
    command = _reconstruct_command(argv)

    typer.echo("Running diagnostic collection...")

    result = subprocess.run(  # nosec B603 B607
        ["bash", str(script_path), "-o", str(output_dir), command],
        check=False,
    )

    raise typer.Exit(code=result.returncode)
