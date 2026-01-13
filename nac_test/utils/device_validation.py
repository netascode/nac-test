
"""Device validation utilities for SSH/D2D test architectures.

This module provides validation functions to ensure device inventory
objects contain all required fields for SSH connectivity.
"""

from typing import Any

# Required fields that every device dictionary must contain
REQUIRED_DEVICE_FIELDS: frozenset[str] = frozenset(
    {"hostname", "host", "os", "username", "password"}
)


def validate_device_inventory(
    devices: list[dict[str, Any]], raise_on_first_error: bool = True
) -> list[str]:
    """Validate that device inventory contains all required fields.

    This function ensures that each device dictionary in the inventory
    contains all fields required for SSH connectivity. It provides
    comprehensive error messages to help diagnose configuration issues
    without exposing sensitive field values.

    Args:
        devices: List of device dictionaries to validate. Each dictionary
            should represent a network device with connection parameters.
        raise_on_first_error: If True, raise ValueError on the first invalid
            device. If False, collect all errors and return them as a list.
            Defaults to True for fail-fast behavior.

    Returns:
        List of error messages if raise_on_first_error is False.
        Empty list if all devices are valid.

    Raises:
        ValueError: If raise_on_first_error is True and any device is missing
            required fields. The error message includes the device identifier,
            missing fields, present fields, and guidance for fixing the issue.

    Example:
        >>> devices = [
        ...     {"hostname": "router1", "host": "10.0.0.1", "os": "iosxe"},
        ...     {"hostname": "switch1", "host": "10.0.0.2", "os": "nxos",
        ...      "username": "admin", "password": "secret"}
        ... ]
        >>> validate_device_inventory(devices)
        ValueError: Device validation failed: 'router1'
        Missing required fields: ['password', 'username']
        Present fields: ['host', 'hostname', 'os']
        Required fields: ['host', 'hostname', 'os', 'password', 'username']

        This indicates a bug in the device resolver implementation.
        Device resolvers MUST return dicts with fields: hostname, host, os, username, password
        Check the get_ssh_device_inventory() implementation in your test architecture.

    Note:
        This function intentionally does not log or display field VALUES to
        prevent leaking sensitive information like passwords. Only field
        names are included in error messages.
    """
    errors: list[str] = []

    for device in devices:
        # Get the fields present in this device dictionary
        present_fields = set(device.keys())

        # Check if all required fields are present
        missing_fields = REQUIRED_DEVICE_FIELDS - present_fields

        if missing_fields:
            # Determine device identifier for error message
            # Prefer hostname, fallback to host, then UNKNOWN
            device_id = device.get("hostname") or device.get("host") or "UNKNOWN"

            # Build comprehensive error message
            error_lines = [
                f"Device validation failed: '{device_id}'",
                f"Missing required fields: {sorted(missing_fields)}",
                f"Present fields: {sorted(present_fields)}",
                f"Required fields: {sorted(REQUIRED_DEVICE_FIELDS)}",
                "",
                "This indicates a bug in the device resolver implementation.",
                "Device resolvers MUST return dicts with fields: hostname, host, os, username, password",
                "Check the get_ssh_device_inventory() implementation in your test architecture.",
            ]

            error_message = "\n".join(error_lines)

            if raise_on_first_error:
                raise ValueError(error_message)
            else:
                errors.append(error_message)

    return errors
