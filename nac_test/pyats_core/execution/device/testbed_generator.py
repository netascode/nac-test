# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""PyATS testbed generation functionality."""

from typing import Any

import yaml


class TestbedGenerator:
    """Generates PyATS testbed YAML files for device connections."""

    @staticmethod
    def generate_testbed_yaml(device: dict[str, Any]) -> str:
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

        Returns:
            Testbed YAML content as a string
        """
        hostname = device["hostname"]  # Required field per nac-test contract

        # Build the testbed structure
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
            "devices": {hostname: TestbedGenerator._build_device_config(device)},
        }

        # Convert to YAML
        return yaml.dump(testbed, default_flow_style=False, sort_keys=False)  # type: ignore[no-any-return]

    @staticmethod
    def generate_consolidated_testbed_yaml(devices: list[dict[str, Any]]) -> str:
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

        Returns:
            Consolidated testbed YAML content as a string
        """
        if not devices:
            raise ValueError("At least one device is required")

        # Build consolidated testbed structure
        testbed = {
            "testbed": {
                "name": "nac_test_consolidated_testbed",
                "credentials": {
                    "default": {
                        # Use credentials from first device as default
                        # Individual devices can override in their own credentials section
                        "username": devices[0]["username"],
                        "password": devices[0]["password"],
                    }
                },
            },
            "devices": {},
        }

        # Add each device to the testbed
        for device in devices:
            hostname = device["hostname"]
            testbed["devices"][hostname] = TestbedGenerator._build_device_config(device)

        # Convert to YAML
        return yaml.dump(testbed, default_flow_style=False, sort_keys=False)  # type: ignore[no-any-return]

    @staticmethod
    def _build_device_config(device: dict[str, Any]) -> dict[str, Any]:
        """Build device configuration dict from device dictionary.

        Extracted to avoid duplication between single and consolidated methods.
        This method follows the same pattern as the feat/user_testbed branch for easier merging.

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
