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
            with open(base_testbed_path) as f:
                testbed = yaml.safe_load(f)

            # Ensure required structure exists
            if "testbed" not in testbed:
                testbed["testbed"] = {}
            if "devices" not in testbed:
                testbed["devices"] = {}

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
            with open(base_testbed_path) as f:
                testbed = yaml.safe_load(f)

            # Ensure required structure exists
            if "testbed" not in testbed:
                testbed["testbed"] = {
                    "name": "nac_test_consolidated_testbed",
                    "credentials": {
                        "default": {
                            "username": devices[0]["username"],
                            "password": devices[0]["password"],
                        }
                    },
                }
            if "devices" not in testbed:
                testbed["devices"] = {}

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

        connection_args.setdefault("settings", {})
        connection_args["settings"].setdefault("POST_DISCONNECT_WAIT_SEC", 0)

        if "platform" in device:
            device_config["platform"] = device["platform"]
            if "model" in device:
                device_config["model"] = device["model"]

        if "series" in device:
            device_config["series"] = device["series"]

        return device_config
