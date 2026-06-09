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
from typing import cast

from nac_test.core.types import ControllerTypeKey

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CredentialSet:
    """A single credential combination that can authenticate to a controller.

    Each set is self-contained: if ALL env_vars are present and non-empty,
    the controller is considered fully configured. When a controller has
    multiple CredentialSets, the first satisfied set wins (order matters).

    Attributes:
        env_vars: Environment variable names required for this credential method.
        label: Human-readable label for error messages (e.g., "API Token (20.18+)").
        auth_method: Identifier consumed by auth adapters in nac-test-pyats-common
            to select the authentication mechanism (e.g., "token", "session").
    """

    env_vars: tuple[str, ...]
    label: str
    auth_method: str = "session"


@dataclass(frozen=True)
class ControllerConfig:
    """Configuration metadata for a supported controller type.

    Attributes:
        display_name: User-facing name (e.g., "APIC", "Catalyst Center").
        url_env_var: Environment variable name for the controller URL.
        env_var_prefix: Prefix for credential env vars (e.g., "ACI" → ACI_USERNAME).
        credential_sets: Ordered list of credential combinations. The first set
            whose env_vars are all present and non-empty wins. Every controller
            must have at least one CredentialSet.
        defaults_prefix: JMESPath prefix for the defaults block in NAC data models
            (e.g., "defaults.apic", "defaults.sdwan").
        cache_key: The controller_type string passed to AuthCache by the auth adapter.
            None for controllers that don't have an auth adapter in nac-test-pyats-common.
    """

    display_name: str
    url_env_var: str
    env_var_prefix: str
    credential_sets: tuple[CredentialSet, ...]
    defaults_prefix: str
    cache_key: str | None = None


# Single source of truth for all controller configurations
# Replaces the registry from controller_auth.py
CONTROLLER_REGISTRY: dict[str, ControllerConfig] = {
    "ACI": ControllerConfig(
        display_name="APIC",
        url_env_var="ACI_URL",
        env_var_prefix="ACI",
        credential_sets=(
            CredentialSet(
                env_vars=("ACI_URL", "ACI_USERNAME", "ACI_PASSWORD"),
                label="Username/Password",
            ),
        ),
        defaults_prefix="defaults.apic",
        cache_key="ACI",
    ),
    "SDWAN": ControllerConfig(
        display_name="SDWAN Manager",
        url_env_var="SDWAN_URL",
        env_var_prefix="SDWAN",
        credential_sets=(
            CredentialSet(
                env_vars=("SDWAN_URL", "SDWAN_API_TOKEN"),
                label="API Token (20.18+)",
                auth_method="token",
            ),
            CredentialSet(
                env_vars=("SDWAN_URL", "SDWAN_USERNAME", "SDWAN_PASSWORD"),
                label="Username/Password",
            ),
        ),
        defaults_prefix="defaults.sdwan",
        cache_key="SDWAN_MANAGER",
    ),
    "CC": ControllerConfig(
        display_name="Catalyst Center",
        url_env_var="CC_URL",
        env_var_prefix="CC",
        credential_sets=(
            CredentialSet(
                env_vars=("CC_URL", "CC_USERNAME", "CC_PASSWORD"),
                label="Username/Password",
            ),
        ),
        defaults_prefix="defaults.catc",
        cache_key="CC",
    ),
    "MERAKI": ControllerConfig(
        display_name="Meraki",
        url_env_var="MERAKI_URL",
        env_var_prefix="MERAKI",
        credential_sets=(
            CredentialSet(
                env_vars=("MERAKI_URL", "MERAKI_USERNAME", "MERAKI_PASSWORD"),
                label="Username/Password",
            ),
        ),
        defaults_prefix="defaults.meraki",
    ),
    "FMC": ControllerConfig(
        display_name="Firepower Management Center",
        url_env_var="FMC_URL",
        env_var_prefix="FMC",
        credential_sets=(
            CredentialSet(
                env_vars=("FMC_URL", "FMC_USERNAME", "FMC_PASSWORD"),
                label="Username/Password",
            ),
        ),
        defaults_prefix="defaults.fmc",
    ),
    "ISE": ControllerConfig(
        display_name="ISE",
        url_env_var="ISE_URL",
        env_var_prefix="ISE",
        credential_sets=(
            CredentialSet(
                env_vars=("ISE_URL", "ISE_USERNAME", "ISE_PASSWORD"),
                label="Username/Password",
            ),
        ),
        defaults_prefix="defaults.ise",
    ),
    "IOSXE": ControllerConfig(
        display_name="IOS XE",
        url_env_var="IOSXE_URL",
        env_var_prefix="IOSXE",
        # Direct device access, no controller credentials required
        credential_sets=(
            CredentialSet(
                env_vars=("IOSXE_URL",),
                label="Device URL",
            ),
            CredentialSet(
                env_vars=("IOSXE_HOST",),
                label="Device Host",
            ),
        ),
        defaults_prefix="defaults.iosxe",
    ),
}

# Module-level cache for the credential set that was matched during detection.
# Populated by detect_controller_type(), consumed by get_matched_credential_set().
_matched_credential_sets: dict[str, CredentialSet] = {}


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
    logger.debug(f"Checking for credentials: {list(CONTROLLER_REGISTRY.keys())}")

    complete, partial = _find_credential_sets()

    logger.debug(f"Complete credential sets found: {list(complete.keys())}")
    logger.debug(f"Partial credential sets found: {partial}")

    # Check for multiple complete credential sets
    if len(complete) > 1:
        error_message = _format_multiple_credentials_error(list(complete.keys()))
        logger.error(f"Multiple controller credentials detected: {list(complete.keys())}")
        raise ValueError(error_message)

    # Check for no credentials at all
    if not complete and not partial:
        error_message = _format_no_credentials_error()
        logger.error("No controller credentials found in environment")
        raise ValueError(error_message)

    # Check for incomplete credentials
    if not complete and partial:
        error_message = _format_incomplete_credentials_error(partial)
        logger.error(f"Incomplete credentials: {partial}")
        raise ValueError(error_message)

    # Exactly one complete set found - success
    controller_type = next(iter(complete))
    _matched_credential_sets[controller_type] = complete[controller_type]
    logger.info(
        f"Detected controller type: {controller_type} "
        f"(auth_method={complete[controller_type].auth_method})"
    )
    return controller_type


def _find_credential_sets() -> tuple[
    dict[ControllerTypeKey, CredentialSet],
    list[ControllerTypeKey],
]:
    """Find complete and partial credential sets in environment.

    For each controller, iterates through its credential_sets in order. The first
    set whose env_vars are all present and non-empty marks the controller as
    complete. If no set is fully satisfied but at least one variable from any set
    is present, the controller is reported as partial.

    Returns:
        A tuple containing:
            - Dictionary mapping complete controller types to the winning CredentialSet
            - List of controller types with partial credentials
    """
    complete: dict[ControllerTypeKey, CredentialSet] = {}
    partial: list[ControllerTypeKey] = []

    for controller_type, config in CONTROLLER_REGISTRY.items():
        found_complete = False
        has_any_var = False
        ct_key = cast(ControllerTypeKey, controller_type)

        for cred_set in config.credential_sets:
            all_present = True

            for var in cred_set.env_vars:
                value = os.environ.get(var)
                if value and value.strip():
                    has_any_var = True
                    logger.debug(f"  {controller_type}: Found {var}")
                else:
                    all_present = False

            if all_present:
                complete[ct_key] = cred_set
                logger.debug(f"  {controller_type}: Complete via {cred_set.label}")
                found_complete = True
                break

        if not found_complete and has_any_var:
            partial.append(ct_key)

    return complete, partial


def _format_incomplete_credentials_error(partial_controllers: list[str]) -> str:
    """Format error message for incomplete controller credentials.

    Creates a detailed error message listing each partially configured
    controller and its accepted credential sets, so the user knows
    exactly which variables are needed.

    Args:
        partial_controllers: List of controller types with partial credentials.

    Returns:
        Formatted error message with accepted credential sets.

    Example:
        >>> error = _format_incomplete_credentials_error(["SDWAN"])
        >>> print(error)
        Incomplete controller credentials detected:
        ...
    """
    lines_parts: list[str] = []
    for controller in partial_controllers:
        config = CONTROLLER_REGISTRY[controller]
        set_descriptions = [
            f"{cs.label}: {' + '.join(cs.env_vars)}"
            for cs in config.credential_sets
        ]
        line = f"{controller}: incomplete credentials"
        line += "\n    Accepted credential sets:\n"
        line += "\n".join(f"      - {desc}" for desc in set_descriptions)
        lines_parts.append(line)
    lines = "\n".join(f"  - {info}" for info in lines_parts)
    return (
        f"Incomplete controller credentials detected:\n"
        f"{lines}\n\n"
        f"Please provide all required variables for one of the "
        f"accepted credential sets listed above."
    )


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

    message = (
        f"Multiple controller credentials detected: {controller_list}\n\n"
        f"The test framework requires exactly one controller type to be configured.\n\n"
        f"Remediation options:\n"
        f"1. Keep only one controller's credentials and unset the others:\n"
    )

    # Collect all env vars per controller (union of all credential sets)
    def _all_env_vars(controller: str) -> list[str]:
        config = CONTROLLER_REGISTRY[controller]
        seen: set[str] = set()
        result: list[str] = []
        for cs in config.credential_sets:
            for v in cs.env_vars:
                if v not in seen:
                    seen.add(v)
                    result.append(v)
        return result

    # Add specific unset commands for each controller
    for controller in controllers:
        other_controllers = [c for c in controllers if c != controller]
        vars_to_remove = []
        for other in other_controllers:
            vars_to_remove.extend(_all_env_vars(other))

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

    for controller_type, config in CONTROLLER_REGISTRY.items():
        message += f"{controller_type}:\n"
        for i, cred_set in enumerate(config.credential_sets):
            if i > 0:
                message += "  Or\n"
            if len(config.credential_sets) > 1:
                message += f"  ({cred_set.label}):\n"
            for var in cred_set.env_vars:
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

    Iterates through credential sets in order, returning the first env var value
    found. This follows the same first-match-wins pattern as _find_credential_sets.

    Args:
        controller_type: The internal controller type key (e.g., "ACI", "SDWAN", "IOSXE").

    Returns:
        The controller URL value from the environment.

    Raises:
        KeyError: If no credential set env var has a URL value set.

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

    # Iterate credential sets — first env var with a value wins
    for cred_set in config.credential_sets:
        for var in cred_set.env_vars:
            value = os.environ.get(var)
            if value and value.strip():
                return value.strip()

    # No URL found - raise KeyError with the primary var name
    raise KeyError(config.url_env_var)


def get_matched_credential_set(controller_type: str) -> CredentialSet | None:
    """Get the credential set that was matched during controller detection.

    Returns the CredentialSet that satisfied detection for the given controller
    type. This is populated by detect_controller_type() and is intended for use
    by auth adapters in nac-test-pyats-common to determine which authentication
    mechanism to use (via the auth_method attribute).

    Args:
        controller_type: The controller type key (e.g., "SDWAN", "ACI").

    Returns:
        The matched CredentialSet, or None if detect_controller_type() has not
        been called or the controller type was not detected.

    Example:
        >>> detect_controller_type()  # populates the cache
        'SDWAN'
        >>> cred = get_matched_credential_set("SDWAN")
        >>> cred.auth_method
        'token'
        >>> cred.label
        'API Token (20.18+)'
    """
    return _matched_credential_sets.get(controller_type)
