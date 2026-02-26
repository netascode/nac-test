# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Controller type detection utilities for NAC test framework.

This module provides utilities for detecting which network controller type (architecture)
is being targeted based on environment variables. Controller credentials are required for
ALL test types (both API and D2D tests) as they determine the architecture context.

The detection logic ensures exactly one controller type is configured at a time to prevent
ambiguous test execution contexts.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Define supported controller types and their required environment variables
CREDENTIAL_PATTERNS: dict[str, list[str]] = {
    "ACI": ["ACI_URL", "ACI_USERNAME", "ACI_PASSWORD"],
    "SDWAN": ["SDWAN_URL", "SDWAN_USERNAME", "SDWAN_PASSWORD"],
    "CC": ["CC_URL", "CC_USERNAME", "CC_PASSWORD"],
    "MERAKI": ["MERAKI_URL", "MERAKI_USERNAME", "MERAKI_PASSWORD"],
    "FMC": ["FMC_URL", "FMC_USERNAME", "FMC_PASSWORD"],
    "ISE": ["ISE_URL", "ISE_USERNAME", "ISE_PASSWORD"],
    "IOSXE": ["IOSXE_URL"],  # Direct device access, no controller credentials needed
}


def detect_controller_type() -> str:
    """Detect the controller type based on environment variables.

    This function examines environment variables to determine which network controller
    architecture is being targeted. It ensures exactly one controller type has credentials
    configured to prevent ambiguous test contexts.

    Controller credentials are required for ALL test types:
    - API tests: Use credentials directly for controller authentication
    - D2D tests: Use controller type to determine device resolution logic

    Returns:
        The detected controller type (e.g., "ACI", "SDWAN", "CC", "MERAKI", "FMC", "ISE").

    Raises:
        ValueError: If no controller credentials are found, multiple controllers are
            configured, or credentials are incomplete.

    Example:
        >>> os.environ.update({"ACI_URL": "https://apic.local",
        ...                    "ACI_USERNAME": "admin",
        ...                    "ACI_PASSWORD": "pass"})
        >>> controller = detect_controller_type()
        >>> print(controller)
        "ACI"
    """
    logger.debug("Starting controller type detection")
    logger.debug(f"Checking for credentials: {list(CREDENTIAL_PATTERNS.keys())}")

    complete_sets, partial_sets = _find_credential_sets()

    logger.debug(f"Complete credential sets found: {complete_sets}")
    logger.debug(f"Partial credential sets found: {list(partial_sets.keys())}")

    # Check for multiple complete credential sets
    if len(complete_sets) > 1:
        error_message = _format_multiple_credentials_error(complete_sets)
        logger.error(f"Multiple controller credentials detected: {complete_sets}")
        raise ValueError(error_message)

    # Check for no credentials at all
    if not complete_sets and not partial_sets:
        error_message = _format_no_credentials_error(partial_sets)
        logger.error("No controller credentials found in environment")
        raise ValueError(error_message)

    # Check for incomplete credentials
    if not complete_sets and partial_sets:
        incomplete_info = [
            f"{controller}: missing {', '.join(info['missing'])}"
            for controller, info in partial_sets.items()
        ]
        error_message = (
            f"Incomplete controller credentials detected:\n"
            f"{chr(10).join(f'  - {info}' for info in incomplete_info)}\n\n"
            f"Please provide ALL required environment variables for your controller type."
        )
        logger.error(f"Incomplete credentials: {partial_sets}")
        raise ValueError(error_message)

    # Exactly one complete set found - success
    controller_type = complete_sets[0]
    logger.info(f"Detected controller type: {controller_type}")
    return controller_type


def _find_credential_sets() -> tuple[list[str], dict[str, dict[str, list[str]]]]:
    """Find complete and partial credential sets in environment.

    Examines environment variables to identify which controller types have
    complete credentials configured and which have partial/incomplete credentials.

    Returns:
        A tuple containing:
            - List of controller types with complete credentials
            - Dictionary mapping controller types to dict with "present" and "missing" lists

    Example:
        >>> os.environ.update({"ACI_URL": "https://apic.local", "ACI_USERNAME": "admin"})
        >>> complete, partial = _find_credential_sets()
        >>> print(complete)
        []
        >>> print(partial)
        {"ACI": {"present": ["ACI_URL", "ACI_USERNAME"], "missing": ["ACI_PASSWORD"]}}
    """
    complete_sets: list[str] = []
    partial_sets: dict[str, dict[str, list[str]]] = {}

    for controller_type, required_vars in CREDENTIAL_PATTERNS.items():
        present_vars = []
        missing_vars = []

        for var in required_vars:
            # Check if variable exists AND is not empty
            value = os.environ.get(var)
            if value and value.strip():  # Non-empty value
                present_vars.append(var)
                logger.debug(f"  {controller_type}: Found {var}")
            else:
                missing_vars.append(var)
                if var in os.environ:
                    logger.debug(f"  {controller_type}: Empty {var}")
                else:
                    logger.debug(f"  {controller_type}: Missing {var}")

        if present_vars and not missing_vars:
            # All required variables present and non-empty
            complete_sets.append(controller_type)
        elif present_vars:
            # Some but not all variables present
            partial_sets[controller_type] = {
                "present": present_vars,
                "missing": missing_vars,
            }

    return complete_sets, partial_sets


def _format_multiple_credentials_error(controllers: list[str]) -> str:
    """Format error message for multiple controller credentials.

    Creates a detailed error message with remediation options when multiple
    controller types have complete credentials configured.

    Args:
        controllers: List of controller types with complete credentials.

    Returns:
        Formatted error message with remediation steps.

    Example:
        >>> error = _format_multiple_credentials_error(["ACI", "SDWAN"])
        >>> print(error)
        Multiple controller credentials detected: ACI, SDWAN
        ...
    """
    controller_list = ", ".join(controllers)

    # Build list of all environment variables that should be unset
    vars_to_unset: list[str] = []
    for controller in controllers:
        vars_to_unset.extend(CREDENTIAL_PATTERNS[controller])

    message = (
        f"Multiple controller credentials detected: {controller_list}\n\n"
        f"The test framework requires exactly one controller type to be configured.\n\n"
        f"Remediation options:\n"
        f"1. Keep only one controller's credentials and unset the others:\n"
    )

    # Add specific unset commands for each controller
    for controller in controllers:
        other_controllers = [c for c in controllers if c != controller]
        vars_to_remove = []
        for other in other_controllers:
            vars_to_remove.extend(CREDENTIAL_PATTERNS[other])

        unset_command = f"   unset {' '.join(vars_to_remove)}"
        message += f"\n   To use {controller} only:\n{unset_command}\n"

    message += (
        "\n2. Use a separate shell session for each controller type\n"
        "\n3. Use environment variable management tools (direnv, dotenv) to switch contexts"
    )

    return message


def _format_no_credentials_error(
    partial_credentials: dict[str, dict[str, list[str]]],
) -> str:
    """Format error message when no controller credentials are found.

    Creates a detailed error message with setup instructions when no controller
    credentials are detected in the environment.

    Args:
        partial_credentials: Dictionary of partial credential sets (not used here,
            but included for consistency with the calling pattern).

    Returns:
        Formatted error message with setup guidance.

    Example:
        >>> error = _format_no_credentials_error({})
        >>> print(error)
        No controller credentials found in environment.
        ...
    """
    message = (
        "No controller credentials found in environment.\n\n"
        "Controller credentials are required for ALL test types (API and D2D).\n"
        "The framework uses these to determine the architecture context.\n\n"
        "Please set environment variables for ONE of the following controller types:\n\n"
    )

    for controller_type, required_vars in CREDENTIAL_PATTERNS.items():
        message += f"{controller_type}:\n"
        for var in required_vars:
            message += f"  export {var}=<value>\n"
        message += "\n"

    message += (
        "Example for ACI:\n"
        "  export ACI_URL=https://apic.example.com\n"
        "  export ACI_USERNAME=admin\n"
        "  export ACI_PASSWORD=yourpassword\n\n"
        "Note: Set credentials for only ONE controller type at a time."
    )

    return message
