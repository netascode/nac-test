# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Pure utility functions for defaults resolution in NAC data models.

This module provides architecture-agnostic utility functions for reading
default values from merged NAC data models. These functions use JMESPath
for data model traversal and are designed to be called from architecture-
specific wrapper methods in NACTestBase.

Note:
    These are pure utility functions with NO PyATS dependencies.
    They should be called by wrapper methods that provide the required
    parameters from the test instance context.
"""

from typing import Any

import jmespath


def ensure_defaults_block_exists(
    data_model: dict[str, Any],
    defaults_prefix: str,
    missing_error: str,
) -> None:
    """Validate that a defaults block exists in the data model.

    This function performs a simple existence check for the defaults block
    in the merged data model. It should be called before attempting to read
    any default values to provide a clear error message when the defaults
    file was not passed to nac-test.

    Args:
        data_model: The merged NAC data model containing configuration and defaults.
        defaults_prefix: JMESPath prefix for the defaults block
            (e.g., "defaults.apic", "defaults.sdwan").
        missing_error: Error message to raise if defaults block is missing.
            Should be architecture-specific with guidance on how to fix.

    Raises:
        ValueError: If the defaults block is not found at the specified prefix.

    Example:
        >>> data = {"defaults": {"apic": {"fabric": {"name": "test"}}}}
        >>> ensure_defaults_block_exists(
        ...     data,
        ...     defaults_prefix="defaults.apic",
        ...     missing_error="APIC defaults block missing. Pass defaults.yaml to nac-test."
        ... )  # No error raised

        >>> ensure_defaults_block_exists(
        ...     {},
        ...     defaults_prefix="defaults.apic",
        ...     missing_error="APIC defaults block missing."
        ... )
        Traceback (most recent call last):
            ...
        ValueError: APIC defaults block missing.
    """
    result = jmespath.search(defaults_prefix, data_model)
    if result is None:
        raise ValueError(missing_error)


def get_default_value(
    data_model: dict[str, Any],
    *default_paths: str,
    defaults_prefix: str,
    missing_error: str,
    required: bool = True,
) -> Any | None:
    """Read default value(s) from the defaults block with cascade/fallback support.

    This function supports both single-path lookups and cascade behavior across
    multiple paths. When multiple paths are provided, the first non-None value
    found is returned.

    Note on Return Type:
        The return type is `Any | None` because JMESPath can return any type
        (str, int, bool, dict, list, etc.) and None is returned when
        required=False and no value is found.

    Args:
        data_model: The merged NAC data model containing configuration and defaults.
        *default_paths: One or more JMESPaths relative to the defaults prefix.
            Single: get_default_value(data, "path.to.value", ...)
            Cascade: get_default_value(data, "path1", "path2", "path3", ...)
        defaults_prefix: JMESPath prefix for the defaults block.
        missing_error: Error message if defaults block is missing.
        required: If True (default), raises ValueError when no value found.
            If False, returns None when no value found.

    Returns:
        The first non-None default value found.
        Returns None only if required=False and no value exists.

    Raises:
        TypeError: If no paths are provided.
        ValueError: If defaults block is missing or required value not found.

    Example:
        >>> data = {
        ...     "defaults": {
        ...         "sdwan": {
        ...             "global": {"timeout": 30},
        ...             "device": {"os": "iosxe"}
        ...         }
        ...     }
        ... }

        # Single path lookup
        >>> get_default_value(
        ...     data, "global.timeout",
        ...     defaults_prefix="defaults.sdwan",
        ...     missing_error="SDWAN defaults missing"
        ... )
        30

        # Cascade lookup (first non-None wins)
        >>> get_default_value(
        ...     data, "device.custom_timeout", "global.timeout",
        ...     defaults_prefix="defaults.sdwan",
        ...     missing_error="SDWAN defaults missing"
        ... )
        30

        # Optional value not found
        >>> get_default_value(
        ...     data, "nonexistent.path",
        ...     defaults_prefix="defaults.sdwan",
        ...     missing_error="SDWAN defaults missing",
        ...     required=False
        ... )
        None
    """
    if not default_paths:
        raise TypeError(
            "get_default_value() requires at least one default_path argument"
        )

    # First ensure the defaults block exists
    ensure_defaults_block_exists(
        data_model=data_model,
        defaults_prefix=defaults_prefix,
        missing_error=missing_error,
    )

    # Try each path in order, return the first non-None value
    for path in default_paths:
        full_path = f"{defaults_prefix}.{path}"
        result = jmespath.search(full_path, data_model)
        if result is not None:
            return result

    # No value found in any path
    if required:
        if len(default_paths) == 1:
            error_msg = (
                f"Required default value not found at path: "
                f"'{defaults_prefix}.{default_paths[0]}'"
            )
        else:
            paths_tried = [f"'{defaults_prefix}.{p}'" for p in default_paths]
            error_msg = (
                f"Required default value not found. "
                f"Tried paths in order: {', '.join(paths_tried)}"
            )
        raise ValueError(error_msg)

    return None
