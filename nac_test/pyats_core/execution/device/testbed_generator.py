
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

        Args:
            device: Device dictionary with connection information
                Required keys: hostname, host, os, username, password
                Optional keys: type, platform

        Returns:
            Testbed YAML content as a string
        """
        hostname = device["hostname"]  # Required field per nac-test contract

        # Build connection arguments
        connection_args = {
            "protocol": "ssh",
            "ip": device["host"],
            "port": device.get("port", 22),
        }

        # Override protocol/port if connection_options is present and pased
        # This allows per-device SSH port/protocol customization from test_inventory.yaml
        if device.get("connection_options"):
            opts = device["connection_options"]
            if "protocol" in opts:
                connection_args["protocol"] = opts["protocol"]
            if "port" in opts:
                connection_args["port"] = opts["port"]

        # Add optional SSH arguments if provided
        if device.get("ssh_options"):
            connection_args["ssh_options"] = device["ssh_options"]

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
            "devices": {
                hostname: {
                    "alias": device.get("alias", hostname),
                    "os": device["os"],
                    "type": device.get("type", "router"),
                    "platform": device.get("platform", device["os"]),
                    "credentials": {
                        "default": {
                            "username": device["username"],
                            "password": device["password"],
                        }
                    },
                    "connections": {"cli": connection_args},
                }
            },
        }

        # Convert to YAML
        return yaml.dump(testbed, default_flow_style=False, sort_keys=False)

    @staticmethod
    def generate_consolidated_testbed_yaml(devices: list[dict[str, Any]]) -> str:
        """Generate a PyATS testbed YAML for multiple devices.

        Creates a consolidated testbed containing all devices for use by the
        connection broker service. This enables connection sharing across
        multiple test subprocesses.

        Args:
            devices: List of device dictionaries with connection information
                Each device must have: hostname, host, os, username, password
                Optional keys: type, platform, connection_options

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

            # Build connection arguments for this device
            connection_args = {
                "protocol": "ssh",
                "ip": device["host"],
                "port": device.get("port", 22),
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

            # Add device to testbed
            testbed["devices"][hostname] = {
                "alias": device.get("alias", hostname),
                "os": device["os"],
                "type": device.get("type", "router"),
                "platform": device.get("platform", device["os"]),
                "credentials": {
                    "default": {
                        "username": device["username"],
                        "password": device["password"],
                    }
                },
                "connections": {"cli": connection_args},
            }

        # Convert to YAML
        return yaml.dump(testbed, default_flow_style=False, sort_keys=False)
