# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""PyATS testbed generation functionality."""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class TestbedGenerator:
    """Generates PyATS testbed YAML files for device connections."""

    @staticmethod
    def generate_testbed_yaml(
        device: dict[str, Any], base_testbed_path: Path | None = None
    ) -> str:
        """Generate a PyATS testbed YAML for a single device.

        Creates a minimal testbed with just the device information needed for connection.
        The testbed uses the Unicon connection library which handles various device types.

        Connection optimization:
        - Disables init_config_commands to prevent unwanted device configuration during connection
        - Enables operating_mode for faster connection establishment
        - Adds custom.abstraction.order for Genie parser optimization
        - Supports optional platform, model, and series fields for faster device identification

        Args:
            device: Device dictionary with connection information
                Required keys: hostname, host, os, username, password
                Optional keys: type, platform, model, series, alias, port, connection_options, ssh_options
            base_testbed_path: Optional path to user-provided base testbed YAML.
                If provided, the base testbed is loaded and the device is added
                only if not already present. User-defined device takes precedence.

        Returns:
            Testbed YAML content as a string
        """
        hostname = device["hostname"]  # Required field per nac-test contract

        # Load base testbed if provided, otherwise create minimal structure
        if base_testbed_path and base_testbed_path.exists():
            testbed = TestbedGenerator._load_user_testbed(base_testbed_path)

            # If device already exists in user testbed, preserve it (user wins)
            if hostname in testbed["devices"]:
                logger.info(
                    f"Device '{hostname}' connection overridden by user-provided testbed"
                )
                # User-provided device takes precedence - return as-is
                return yaml.dump(testbed, default_flow_style=False, sort_keys=False)
        else:
            # Create minimal testbed structure
            testbed = {
                "testbed": {
                    "name": f"testbed_{hostname}",
                    "credentials": {
                        "default": {
                            "username": device["username"],
                            "password": device["password"],
                        }
                    },
                },
                "devices": {},
            }

        # Add auto-discovered device to testbed
        testbed["devices"][hostname] = TestbedGenerator._build_device_config(device)

        # Convert to YAML
        return yaml.dump(testbed, default_flow_style=False, sort_keys=False)

    @staticmethod
    def generate_consolidated_testbed_yaml(
        devices: list[dict[str, Any]], base_testbed_path: Path | None = None
    ) -> str:
        """Generate a PyATS testbed YAML for multiple devices.

        Creates a consolidated testbed containing all devices for use by the
        connection broker service. This enables connection sharing across
        multiple test subprocesses.

        Connection optimization:
        - Disables init_config_commands to prevent unwanted device configuration during connection
        - Enables operating_mode for faster connection establishment
        - Adds custom.abstraction.order for Genie parser optimization
        - Supports optional platform, model, and series fields for faster device identification

        Args:
            devices: List of device dictionaries with connection information
                Each device must have: hostname, host, os, username, password
                Optional keys: type, platform, model, series, alias, port, connection_options, ssh_options
            base_testbed_path: Optional path to user-provided base testbed YAML.
                If provided, the base testbed is loaded and used as the foundation.
                Auto-discovered devices are added only if not already present.
                User-defined devices take precedence over auto-discovered ones.

        Returns:
            Consolidated testbed YAML content as a string
        """
        if not devices:
            raise ValueError("At least one device is required")

        # Load base testbed if provided, otherwise create minimal structure
        if base_testbed_path and base_testbed_path.exists():
            logger.info(f"Loading user-provided testbed from: {base_testbed_path}")
            testbed = TestbedGenerator._load_user_testbed(base_testbed_path)

            # If user didn't provide testbed metadata, add defaults
            if not testbed["testbed"]:
                testbed["testbed"] = {
                    "name": "nac_test_consolidated_testbed",
                    "credentials": {
                        "default": {
                            "username": devices[0]["username"],
                            "password": devices[0]["password"],
                        }
                    },
                }

            # Track which devices are from user testbed
            user_device_hostnames = set(testbed["devices"].keys())
            if user_device_hostnames:
                logger.info(
                    f"User testbed contains {len(user_device_hostnames)} device(s): "
                    f"{', '.join(sorted(user_device_hostnames))}"
                )
        else:
            # Create minimal testbed structure (existing logic)
            testbed = {
                "testbed": {
                    "name": "nac_test_consolidated_testbed",
                    "credentials": {
                        "default": {
                            "username": devices[0]["username"],
                            "password": devices[0]["password"],
                        }
                    },
                },
                "devices": {},
            }
            user_device_hostnames = set()

        # Add auto-discovered devices (only if not in user testbed)
        for device in devices:
            hostname = device["hostname"]

            if hostname in user_device_hostnames:
                # Device exists in user testbed - skip (user takes precedence)
                logger.info(
                    f"Device '{hostname}' connection overridden by user-provided testbed"
                )
                continue

            # Add auto-discovered device
            testbed["devices"][hostname] = TestbedGenerator._build_device_config(device)

        # Convert to YAML
        # Note: User-only devices (not in auto-discovery) remain in testbed
        return yaml.dump(testbed, default_flow_style=False, sort_keys=False)

    @staticmethod
    def _load_user_testbed(base_testbed_path: Path) -> dict[str, Any]:
        """Load and validate a user-provided testbed YAML file.

        Performs defensive validation to catch common user errors early with
        helpful error messages. Guarantees that the returned dictionary contains
        'testbed' and 'devices' keys as dictionaries.

        Args:
            base_testbed_path: Path to the user-provided testbed YAML file.

        Returns:
            Validated testbed dictionary with 'testbed' and 'devices' keys
            guaranteed to exist as dictionaries.

        Raises:
            ValueError: If the file contains invalid UTF-8 encoding, invalid YAML,
                is empty, or has unexpected structure.
        """
        # Typer CLI validates: exists=True, file_okay=True, dir_okay=False (readable)
        try:
            with open(base_testbed_path, encoding="utf-8") as f:
                testbed = yaml.safe_load(f)
        except UnicodeDecodeError as e:
            raise ValueError(
                f"Testbed file '{base_testbed_path}' contains invalid UTF-8 encoding. "
                f"Please ensure the file is saved as UTF-8."
            ) from e
        except yaml.YAMLError as e:
            raise ValueError(
                f"Invalid YAML syntax in testbed file '{base_testbed_path}': {e}"
            ) from e

        # Handle empty file (yaml.safe_load returns None)
        if testbed is None:
            raise ValueError(f"Testbed file '{base_testbed_path}' is empty")

        # Validate root is a dictionary
        if not isinstance(testbed, dict):
            raise ValueError(
                f"Testbed file '{base_testbed_path}' must contain a YAML mapping (dict), "
                f"got {type(testbed).__name__}"
            )

        # Validate 'devices' key structure if present
        if "devices" in testbed and not isinstance(testbed["devices"], dict):
            raise ValueError(
                f"'devices' in testbed file '{base_testbed_path}' must be a mapping (dict), "
                f"got {type(testbed['devices']).__name__}"
            )

        # Ensure required keys exist as dicts (avoid duplication in callers)
        if "testbed" not in testbed:
            testbed["testbed"] = {}
        if "devices" not in testbed:
            testbed["devices"] = {}

        return testbed

    @staticmethod
    def _build_device_config(device: dict[str, Any]) -> dict[str, Any]:
        """Build device configuration dict from device dictionary.

        Extracted to avoid duplication between single and consolidated methods.

        Args:
            device: Device dictionary with connection information

        Returns:
            Device configuration dict suitable for PyATS testbed
        """
        hostname = device["hostname"]

        # Build connection arguments
        if "command" in device:
            # Special handling for mock or radkit devices
            connection_args = {
                "command": device["command"],
                "arguments": {
                    "init_config_commands": [],
                    "operating_mode": True,
                },
            }
        else:
            connection_args = {
                "protocol": "ssh",
                "ip": device["host"],
                "port": device.get("port", 22),
                "arguments": {
                    "init_config_commands": [],
                    "operating_mode": True,
                },
            }

            # Override protocol/port if connection_options is present
            if device.get("connection_options"):
                opts = device["connection_options"]
                if "protocol" in opts:
                    connection_args["protocol"] = opts["protocol"]
                if "port" in opts:
                    connection_args["port"] = opts["port"]

            # Add optional SSH arguments if provided
            if device.get("ssh_options"):
                connection_args["ssh_options"] = device["ssh_options"]

        # Build device config
        device_config = {
            "alias": device.get("alias", hostname),
            "os": device["os"],
            "type": device.get("type", "router"),
            "credentials": {
                "default": {
                    "username": device["username"],
                    "password": device["password"],
                }
            },
            "connections": {"cli": connection_args},
            "custom": {"abstraction": {"order": ["os"]}},
        }

        if "platform" in device:
            device_config["platform"] = device["platform"]
            if "model" in device:
                device_config["model"] = device["model"]

        if "series" in device:
            device_config["series"] = device["series"]

        return device_config
