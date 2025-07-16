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
                Expected keys: device_id, host, hostname, os, username, password

        Returns:
            Testbed YAML content as a string
        """
        device_id = device.get("device_id", device.get("host", "unknown"))

        # Build connection arguments
        connection_args = {
            "protocol": "ssh",
            "ip": device["host"],
            "port": device.get("port", 22),
        }

        # Add optional SSH arguments if provided
        if device.get("ssh_options"):
            connection_args["ssh_options"] = device["ssh_options"]

        # Build the testbed structure
        testbed = {
            "testbed": {
                "name": f"testbed_{device_id}",
                "credentials": {
                    "default": {
                        "username": device["username"],
                        "password": device["password"],
                    }
                },
            },
            "devices": {
                device_id: {
                    "alias": device.get("hostname", device_id),
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
