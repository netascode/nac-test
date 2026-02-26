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
import sys
from pathlib import Path

import typer

from nac_test.core.constants import EXIT_INVALID_ARGS


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


def _extract_output_dir(args: list[str]) -> str | None:
    """Extract the output directory value from command-line arguments.

    Parses the argument list to find the -o/--output option value.
    Handles all common argument syntaxes:
    - -o value
    - --output value
    - --output=value
    - -o=value

    Args:
        args: List of command-line arguments to parse.

    Returns:
        The output directory path as a string if found, None otherwise.
        If multiple -o/--output options are present, returns the first one.
    """
    i = 0
    while i < len(args):
        arg = args[i]

        # Handle --output=value or -o=value syntax
        if arg.startswith("--output="):
            return arg[len("--output=") :]
        if arg.startswith("-o="):
            return arg[len("-o=") :]

        # Handle --output value or -o value syntax
        if arg in ("-o", "--output"):
            if i + 1 < len(args):
                return args[i + 1]
            return None

        i += 1

    return None


def _reconstruct_command(argv: list[str]) -> str:
    """Reconstruct the original command without the --diagnostic flag.

    Takes sys.argv and removes the --diagnostic flag to create a clean
    command string that can be passed to the diagnostic script.

    Args:
        argv: The original sys.argv list from command invocation.

    Returns:
        A shell-safe command string with --diagnostic removed,
        suitable for passing to the diagnostic script.
    """
    # Filter out --diagnostic flag
    filtered_args = [arg for arg in argv if arg != "--diagnostic"]
    return shlex.join(filtered_args)


def diagnostic_callback(value: bool) -> None:
    """Typer callback to handle the --diagnostic flag.

    When --diagnostic is specified, this callback intercepts execution,
    runs the diagnostic collection script with the original command,
    and exits with the script's return code.

    Args:
        value: Boolean indicating whether --diagnostic was specified.
            If False, returns immediately without action.
            If True, runs diagnostic collection and exits.

    Raises:
        typer.Exit: Always raised when value is True, with the
            return code from the diagnostic script subprocess.
    """
    if not value:
        return

    # Find the diagnostic script
    script_path = _find_diagnostic_script()

    # Reconstruct the original command without --diagnostic
    command = _reconstruct_command(sys.argv)

    # Extract output directory from arguments
    output_dir = _extract_output_dir(sys.argv)

    if output_dir is None:
        typer.echo(
            typer.style(
                "Error: --diagnostic requires -o/--output to be specified.",
                fg=typer.colors.RED,
            )
        )
        raise typer.Exit(code=EXIT_INVALID_ARGS)

    typer.echo("Running diagnostic collection...")

    # Run the diagnostic script
    # The script path and output_dir are controlled by us (bundled asset and CLI arg).
    # The command is reconstructed from sys.argv which is user input but is passed
    # as a single string argument to the script, not executed directly.
    result = subprocess.run(  # nosec B603 B607
        ["bash", str(script_path), "-o", output_dir, command],
        check=False,
    )

    raise typer.Exit(code=result.returncode)
