# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Controller type detection utilities for NAC test framework.

This module provides utilities for detecting which network controller type (architecture)
is being targeted based on environment variables. Controller credentials are required for
ALL test types (both API and D2D tests) as they determine the architecture context.

The detection logic ensures exactly one controller type is configured at a time to prevent
ambiguous test execution contexts.

The module also provides a mapping from controller types to their defaults block prefixes,
enabling automatic defaults resolution without per-architecture configuration. For example,
when ACI_URL is detected, the framework automatically knows to look for defaults.apic in
the merged NAC data model.
"""

import logging
import os
from dataclasses import dataclass
from typing import TypedDict, cast

from nac_test.core.types import ControllerTypeKey

logger = logging.getLogger(__name__)


class CredentialSetStatus(TypedDict):
    """Status of a controller credential set.

    Attributes:
        present: List of environment variable names that are set.
        missing: List of environment variable names that are not set.
    """

    present: list[str]
    missing: list[str]


@dataclass(frozen=True)
class ControllerConfig:
    """Configuration metadata for a supported controller type.

    Attributes:
        display_name: User-facing name (e.g., "APIC", "Catalyst Center").
        url_env_var: Environment variable name for the controller URL.
        env_var_prefix: Prefix for credential env vars (e.g., "ACI" → ACI_USERNAME).
        required_env_vars: List of environment variables required for this controller.
        defaults_prefix: JMESPath prefix for the defaults block in NAC data models
            (e.g., "defaults.apic", "defaults.sdwan").
        cache_key: The controller_type string passed to AuthCache by the auth adapter.
            None for controllers that don't have an auth adapter in nac-test-pyats-common.
        alt_url_env_vars: Alternative environment variable names for the URL.
            Used when a controller supports multiple URL env var names (e.g., IOSXE_HOST).
    """

    display_name: str
    url_env_var: str
    env_var_prefix: str
    required_env_vars: list[str]
    defaults_prefix: str
    cache_key: str | None = None
    alt_url_env_vars: list[str] | None = None


# Single source of truth for all controller configurations
# Replaces both CREDENTIAL_PATTERNS and the registry from controller_auth.py
CONTROLLER_REGISTRY: dict[str, ControllerConfig] = {
    "ACI": ControllerConfig(
        display_name="APIC",
        url_env_var="ACI_URL",
        env_var_prefix="ACI",
        required_env_vars=["ACI_URL", "ACI_USERNAME", "ACI_PASSWORD"],
        defaults_prefix="defaults.apic",
        cache_key="ACI",
    ),
    "SDWAN": ControllerConfig(
        display_name="SDWAN Manager",
        url_env_var="SDWAN_URL",
        env_var_prefix="SDWAN",
        required_env_vars=["SDWAN_URL", "SDWAN_USERNAME", "SDWAN_PASSWORD"],
        defaults_prefix="defaults.sdwan",
        cache_key="SDWAN_MANAGER",
    ),
    "CC": ControllerConfig(
        display_name="Catalyst Center",
        url_env_var="CC_URL",
        env_var_prefix="CC",
        required_env_vars=["CC_URL", "CC_USERNAME", "CC_PASSWORD"],
        defaults_prefix="defaults.catc",
        cache_key="CC",
    ),
    "MERAKI": ControllerConfig(
        display_name="Meraki",
        url_env_var="MERAKI_URL",
        env_var_prefix="MERAKI",
        required_env_vars=["MERAKI_URL", "MERAKI_USERNAME", "MERAKI_PASSWORD"],
        defaults_prefix="defaults.meraki",
    ),
    "FMC": ControllerConfig(
        display_name="Firepower Management Center",
        url_env_var="FMC_URL",
        env_var_prefix="FMC",
        required_env_vars=["FMC_URL", "FMC_USERNAME", "FMC_PASSWORD"],
        defaults_prefix="defaults.fmc",
    ),
    "ISE": ControllerConfig(
        display_name="ISE",
        url_env_var="ISE_URL",
        env_var_prefix="ISE",
        required_env_vars=["ISE_URL", "ISE_USERNAME", "ISE_PASSWORD"],
        defaults_prefix="defaults.ise",
    ),
    "IOSXE": ControllerConfig(
        display_name="IOS XE",
        url_env_var="IOSXE_URL",
        env_var_prefix="IOSXE",
        required_env_vars=[
            "IOSXE_URL"
        ],  # Direct device access, no controller credentials
        defaults_prefix="defaults.iosxe",
        alt_url_env_vars=["IOSXE_HOST"],  # Alternative env var for URL
    ),
}

# Backward compatibility - remove in future version
CREDENTIAL_PATTERNS: dict[str, list[str]] = {
    controller_type: config.required_env_vars
    for controller_type, config in CONTROLLER_REGISTRY.items()
}


def detect_controller_type() -> ControllerTypeKey:
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
        error_message = _format_no_credentials_error()
        logger.error("No controller credentials found in environment")
        raise ValueError(error_message)

    # Check for incomplete credentials
    if not complete_sets and partial_sets:
        incomplete_info = [
            f"{controller}: missing {', '.join(info['missing'])}"
            for controller, info in partial_sets.items()
        ]
        lines = "\n".join(f"  - {info}" for info in incomplete_info)
        error_message = (
            f"Incomplete controller credentials detected:\n"
            f"{lines}\n\n"
            f"Please provide ALL required environment variables for your controller type."
        )
        logger.error(f"Incomplete credentials: {partial_sets}")
        raise ValueError(error_message)

    # Exactly one complete set found - success
    # complete_sets come from CONTROLLER_REGISTRY keys, which are always valid
    # ControllerTypeKey values, but mypy can't infer this from dict iteration.
    controller_type = cast(ControllerTypeKey, complete_sets[0])
    logger.info(f"Detected controller type: {controller_type}")
    return controller_type


def _find_credential_sets() -> tuple[list[str], dict[str, CredentialSetStatus]]:
    """Find complete and partial credential sets in environment.

    Examines environment variables to identify which controller types have
    complete credentials configured and which have partial/incomplete credentials.

    This function also handles alternative URL environment variables (e.g., IOSXE_HOST
    as an alternative to IOSXE_URL) when configured in the ControllerConfig.

    Returns:
        A tuple containing:
            - List of controller types with complete credentials
            - Dictionary mapping controller types to CredentialSetStatus

    Example:
        >>> os.environ.update({"ACI_URL": "https://apic.local", "ACI_USERNAME": "admin"})
        >>> complete, partial = _find_credential_sets()
        >>> print(complete)
        []
        >>> print(partial)
        {"ACI": {"present": ["ACI_URL", "ACI_USERNAME"], "missing": ["ACI_PASSWORD"]}}
    """
    complete_sets: list[str] = []
    partial_sets: dict[str, CredentialSetStatus] = {}

    for controller_type, config in CONTROLLER_REGISTRY.items():
        required_vars = config.required_env_vars
        present_vars = []
        missing_vars = []

        for var in required_vars:
            # Check if variable exists AND is not empty
            value = os.environ.get(var)
            if value and value.strip():  # Non-empty value
                present_vars.append(var)
                logger.debug(f"  {controller_type}: Found {var}")
            else:
                # Check alternative URL env vars if this is the URL variable
                alt_found = False
                if var == config.url_env_var and config.alt_url_env_vars:
                    for alt_var in config.alt_url_env_vars:
                        alt_value = os.environ.get(alt_var)
                        if alt_value and alt_value.strip():
                            present_vars.append(alt_var)
                            logger.debug(
                                f"  {controller_type}: Found {alt_var} (alternative)"
                            )
                            alt_found = True
                            break

                if not alt_found:
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


def _format_no_credentials_error() -> str:
    """Format error message when no controller credentials are found.

    Creates a detailed error message with setup instructions when no controller
    credentials are detected in the environment.

    Returns:
        Formatted error message with setup guidance.

    Example:
        >>> error = _format_no_credentials_error()
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


def get_display_name(controller_type: str) -> str:
    """Get the user-facing display name for a controller type.

    Looks up the display name from CONTROLLER_REGISTRY. If the controller type
    is not registered, returns the controller_type string as-is for graceful
    degradation.

    Args:
        controller_type: The internal controller type key (e.g., "ACI", "SDWAN", "CC").

    Returns:
        The user-facing display name (e.g., "APIC", "SDWAN Manager", "Catalyst Center"),
        or the controller_type string if not found in registry.
    """
    config = CONTROLLER_REGISTRY.get(controller_type)
    return config.display_name if config else controller_type


def get_env_var_prefix(controller_type: str) -> str:
    """Get the environment variable prefix for a controller type.

    Looks up the env_var_prefix from CONTROLLER_REGISTRY. If the controller type
    is not registered, returns the controller_type string as-is for graceful
    degradation.

    Args:
        controller_type: The internal controller type key (e.g., "ACI", "SDWAN", "CC").

    Returns:
        The environment variable prefix (e.g., "ACI", "SDWAN", "CC"),
        or the controller_type string if not found in registry.
    """
    config = CONTROLLER_REGISTRY.get(controller_type)
    return config.env_var_prefix if config else controller_type


def get_defaults_prefix(controller_type: str) -> str:
    """Get the JMESPath defaults prefix for a controller type.

    Looks up the defaults_prefix from CONTROLLER_REGISTRY. If the controller type
    is not registered, constructs a default prefix of "defaults.<controller_type_lower>"
    for graceful degradation.

    Args:
        controller_type: The internal controller type key (e.g., "ACI", "SDWAN", "CC").

    Returns:
        The JMESPath defaults prefix (e.g., "defaults.apic", "defaults.sdwan"),
        or "defaults.<controller_type_lower>" if not found in registry.

    Example:
        >>> get_defaults_prefix("ACI")
        'defaults.apic'
        >>> get_defaults_prefix("SDWAN")
        'defaults.sdwan'
        >>> get_defaults_prefix("UNKNOWN")
        'defaults.unknown'
    """
    config = CONTROLLER_REGISTRY.get(controller_type)
    return config.defaults_prefix if config else f"defaults.{controller_type.lower()}"


def get_controller_url(controller_type: str) -> str:
    """Get the controller URL from environment variables.

    Looks up the primary URL environment variable from CONTROLLER_REGISTRY, and
    also checks alternative URL env vars if configured (e.g., IOSXE_HOST as an
    alternative to IOSXE_URL).

    Args:
        controller_type: The internal controller type key (e.g., "ACI", "SDWAN", "IOSXE").

    Returns:
        The controller URL value from the environment.

    Raises:
        KeyError: If neither the primary nor any alternative URL env var is set.

    Example:
        >>> os.environ["ACI_URL"] = "https://apic.example.com"
        >>> get_controller_url("ACI")
        'https://apic.example.com'

        >>> os.environ["IOSXE_HOST"] = "192.168.1.1"
        >>> get_controller_url("IOSXE")  # Returns IOSXE_HOST when IOSXE_URL not set
        '192.168.1.1'
    """
    config = CONTROLLER_REGISTRY.get(controller_type)

    if config is None:
        # Fallback for unknown controller types
        return os.environ[f"{controller_type}_URL"]

    # Try primary URL env var first
    url_value = os.environ.get(config.url_env_var)
    if url_value and url_value.strip():
        return url_value.strip()

    # Try alternative URL env vars if configured
    if config.alt_url_env_vars:
        for alt_var in config.alt_url_env_vars:
            alt_value = os.environ.get(alt_var)
            if alt_value and alt_value.strip():
                return alt_value.strip()

    # No URL found - raise KeyError with the primary var name
    raise KeyError(config.url_env_var)
