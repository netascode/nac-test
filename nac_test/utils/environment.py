# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

# -*- coding: utf-8 -*-

"""Environment variable utilities for nac-test framework."""

import os
import sys
from collections.abc import Callable

from nac_test.utils.terminal import terminal


class EnvironmentValidator:
    """Generic environment variable validation utilities."""

    @staticmethod
    def check_required_vars(
        required_vars: list[str],
        exit_on_missing: bool = True,
        custom_formatter: Callable[[list[str]], str] | None = None,
    ) -> list[str]:
        """Check for required environment variables.

        Args:
            required_vars: List of required environment variable names
            exit_on_missing: Whether to exit if variables are missing
            custom_formatter: Optional custom error formatter function

        Returns:
            List of missing variable names (empty if all present)

        Raises:
            SystemExit: If exit_on_missing is True and variables are missing
        """
        missing = [var for var in required_vars if not os.environ.get(var)]

        if missing and exit_on_missing:
            # Use custom formatter or default
            if custom_formatter:
                error_msg = custom_formatter(missing)
            else:
                error_msg = EnvironmentValidator.format_missing_vars_error(missing)

            print(error_msg)
            sys.exit(1)

        return missing

    @staticmethod
    def format_missing_vars_error(missing_vars: list[str]) -> str:
        """Format a generic error message for missing environment variables.

        Args:
            missing_vars: List of missing environment variable names

        Returns:
            Formatted error message
        """
        lines = []
        lines.append(terminal.header("ERROR: Missing environment variable(s)"))
        lines.append("")

        for var in missing_vars:
            lines.append(f"  • {terminal.error(var)}")

        lines.append("")
        lines.append(
            terminal.info(
                "Please set the required environment variables before running."
            )
        )

        return "\n".join(lines)

    @staticmethod
    def get_with_default(var_name: str, default: str) -> str:
        """Get environment variable with a default value.

        Args:
            var_name: Environment variable name
            default: Default value if not set

        Returns:
            Environment variable value or default
        """
        return os.environ.get(var_name, default)

    @staticmethod
    def get_bool(var_name: str, default: bool = False) -> bool:
        """Get environment variable as boolean.

        Args:
            var_name: Environment variable name
            default: Default value if not set

        Returns:
            Boolean value (true/1/yes/on are True, everything else is False)
        """
        value = os.environ.get(var_name, "").lower()
        if not value:
            return default
        return value in ("true", "1", "yes", "on")

    @staticmethod
    def get_int(var_name: str, default: int = 0) -> int:
        """Get environment variable as integer.

        Args:
            var_name: Environment variable name
            default: Default value if not set or invalid

        Returns:
            Integer value or default
        """
        try:
            return int(os.environ.get(var_name, str(default)))
        except ValueError:
            return default

    @staticmethod
    def validate_controller_env(controller_type: str = "ACI") -> None:
        """Validate controller-specific environment variables.

        This is a convenience method for validating controller credentials.

        Args:
            controller_type: Type of controller (ACI, CC, etc.)

        Raises:
            SystemExit: If required variables are missing
        """
        required_vars = [
            f"{controller_type}_URL",
            f"{controller_type}_USERNAME",
            f"{controller_type}_PASSWORD",
        ]

        # Use terminal's controller-specific formatter
        def controller_formatter(missing: list[str]) -> str:
            return terminal.format_env_var_error(missing, controller_type)

        EnvironmentValidator.check_required_vars(
            required_vars, exit_on_missing=True, custom_formatter=controller_formatter
        )
