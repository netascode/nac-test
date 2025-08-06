# -*- coding: utf-8 -*-

"""PyATS testbed generation functionality."""

import yaml
from typing import Dict, Any


class TestbedGenerator:
    """Generates PyATS testbed YAML files for device connections."""

    @staticmethod
    def generate_testbed_yaml(device: Dict[str, Any]) -> str:
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
