# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Environment variable utilities for nac-test framework."""

import os

from nac_test.utils.controller import CREDENTIAL_PATTERNS
from nac_test.utils.terminal import terminal


class EnvironmentValidator:
    """Environment variable validation utilities.

    Provides methods for validating and retrieving environment variables,
    including controller-specific credential validation.
    """

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
    def get_missing_controller_vars(controller_type: str) -> list[str]:
        """Return list of missing credential environment variables for a controller.

        Args:
            controller_type: Controller type (e.g., "ACI", "SDWAN", "CC")

        Returns:
            List of missing environment variable names (empty if all present)

        Raises:
            ValueError: If controller_type is unknown
        """
        if controller_type not in CREDENTIAL_PATTERNS:
            raise ValueError(f"Unknown controller type: {controller_type}")
        required = CREDENTIAL_PATTERNS[controller_type]
        return [var for var in required if not os.environ.get(var)]

    @staticmethod
    def format_missing_credentials_error(
        controller_type: str, missing_vars: list[str]
    ) -> str:
        """Format user-friendly error message for missing controller credentials.

        Args:
            controller_type: Controller type (e.g., "ACI", "SDWAN", "CC")
            missing_vars: List of missing environment variable names

        Returns:
            Formatted error message suitable for terminal display
        """
        return terminal.format_env_var_error(missing_vars, controller_type)

    @staticmethod
    def validate_controller_env(controller_type: str) -> list[str]:
        """Validate controller-specific environment variables.

        Checks that all required credential environment variables are set
        for the specified controller type.

        Args:
            controller_type: Type of controller (ACI, SDWAN, CC, etc.)

        Returns:
            List of missing environment variable names (empty if all present)

        Raises:
            ValueError: If controller_type is unknown
        """
        return EnvironmentValidator.get_missing_controller_vars(controller_type)
