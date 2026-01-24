# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for TestbedGenerator with custom testbed merging."""

import tempfile
from pathlib import Path

import yaml

from nac_test.pyats_core.execution.device.testbed_generator import TestbedGenerator


class TestTestbedMerging:
    """Test testbed merging functionality."""

    def test_generate_without_base_testbed(self) -> None:
        """Test testbed generation without a base testbed (normal operation)."""
        device = {
            "hostname": "router1",
            "host": "10.1.1.1",
            "os": "iosxe",
            "username": "admin",
            "password": "cisco123",
        }

        result = TestbedGenerator.generate_consolidated_testbed_yaml([device])
        testbed = yaml.safe_load(result)

        assert "testbed" in testbed
        assert "devices" in testbed
        assert "router1" in testbed["devices"]
        assert testbed["devices"]["router1"]["os"] == "iosxe"

    def test_generate_with_base_testbed_override(self) -> None:
        """Test that user testbed devices override auto-discovered devices."""
        # Create user testbed with override
        user_testbed_yaml = """
testbed:
  name: custom_testbed
  custom:
    environment: test

devices:
  router1:
    os: iosxe
    connections:
      cli:
        command: python mock_unicon.py iosxe --hostname router1
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(user_testbed_yaml)
            user_testbed_path = Path(f.name)

        try:
            # Auto-discovered device
            device = {
                "hostname": "router1",
                "host": "10.1.1.1",
                "os": "iosxe",
                "username": "admin",
                "password": "cisco123",
            }

            result = TestbedGenerator.generate_consolidated_testbed_yaml(
                [device], base_testbed_path=user_testbed_path
            )
            testbed = yaml.safe_load(result)

            # User testbed should take precedence
            assert testbed["testbed"]["name"] == "custom_testbed"
            assert testbed["testbed"]["custom"]["environment"] == "test"
            assert "router1" in testbed["devices"]
            # Device should have user-defined connection (not auto-discovered)
            assert "command" in testbed["devices"]["router1"]["connections"]["cli"]
            assert "ip" not in testbed["devices"]["router1"]["connections"]["cli"]

        finally:
            user_testbed_path.unlink()

    def test_generate_with_base_testbed_additional_devices(self) -> None:
        """Test that auto-discovered devices are added to user testbed."""
        # User testbed with one device
        user_testbed_yaml = """
testbed:
  name: user_testbed

devices:
  jumphost:
    os: linux
    type: linux
    connections:
      cli:
        protocol: ssh
        ip: 10.0.0.1
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(user_testbed_yaml)
            user_testbed_path = Path(f.name)

        try:
            # Auto-discovered devices
            devices = [
                {
                    "hostname": "router1",
                    "host": "10.1.1.1",
                    "os": "iosxe",
                    "username": "admin",
                    "password": "cisco123",
                },
                {
                    "hostname": "router2",
                    "host": "10.1.1.2",
                    "os": "iosxe",
                    "username": "admin",
                    "password": "cisco123",
                },
            ]

            result = TestbedGenerator.generate_consolidated_testbed_yaml(
                devices, base_testbed_path=user_testbed_path
            )
            testbed = yaml.safe_load(result)

            # Should have all three devices
            assert len(testbed["devices"]) == 3
            assert "jumphost" in testbed["devices"]
            assert "router1" in testbed["devices"]
            assert "router2" in testbed["devices"]

            # Jumphost from user testbed
            assert testbed["devices"]["jumphost"]["type"] == "linux"
            # Routers from auto-discovery
            assert (
                testbed["devices"]["router1"]["connections"]["cli"]["ip"] == "10.1.1.1"
            )
            assert (
                testbed["devices"]["router2"]["connections"]["cli"]["ip"] == "10.1.1.2"
            )

        finally:
            user_testbed_path.unlink()

    def test_preserve_pyats_env_variables(self) -> None:
        """Test that PyATS environment variable syntax is preserved."""
        # User testbed with %ENV{} syntax
        user_testbed_yaml = """
testbed:
  name: env_test_testbed
  credentials:
    default:
      username: "%ENV{IOSXE_USERNAME}"
      password: "%ENV{IOSXE_PASSWORD}"

devices:
  router1:
    os: iosxe
    credentials:
      default:
        username: "%ENV{DEVICE_USERNAME}"
        password: "%ENV{DEVICE_PASSWORD}"
    connections:
      cli:
        protocol: ssh
        ip: 10.1.1.1
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(user_testbed_yaml)
            user_testbed_path = Path(f.name)

        try:
            # Auto-discovered device (should be overridden)
            device = {
                "hostname": "router1",
                "host": "10.1.1.1",
                "os": "iosxe",
                "username": "plaintext_user",
                "password": "plaintext_pass",
            }

            result = TestbedGenerator.generate_consolidated_testbed_yaml(
                [device], base_testbed_path=user_testbed_path
            )
            testbed = yaml.safe_load(result)

            # Environment variables should be preserved as strings
            assert (
                testbed["testbed"]["credentials"]["default"]["username"]
                == "%ENV{IOSXE_USERNAME}"
            )
            assert (
                testbed["testbed"]["credentials"]["default"]["password"]
                == "%ENV{IOSXE_PASSWORD}"
            )
            assert (
                testbed["devices"]["router1"]["credentials"]["default"]["username"]
                == "%ENV{DEVICE_USERNAME}"
            )
            assert (
                testbed["devices"]["router1"]["credentials"]["default"]["password"]
                == "%ENV{DEVICE_PASSWORD}"
            )

        finally:
            user_testbed_path.unlink()

    def test_preserve_pyats_custom_data(self) -> None:
        """Test that PyATS custom data sections are preserved."""
        # User testbed with custom data
        user_testbed_yaml = """
testbed:
  name: custom_data_testbed
  custom:
    shared_vars:
      ntp_server: 10.1.1.1
      dns_server: 10.1.1.2
    test_config:
      timeout: 300
      retry_count: 3

topology:
  router1:
    interfaces:
      GigabitEthernet0/0:
        link: link-1
        type: ethernet

devices: {}
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(user_testbed_yaml)
            user_testbed_path = Path(f.name)

        try:
            # Auto-discovered device
            device = {
                "hostname": "router1",
                "host": "10.1.1.1",
                "os": "iosxe",
                "username": "admin",
                "password": "cisco123",
            }

            result = TestbedGenerator.generate_consolidated_testbed_yaml(
                [device], base_testbed_path=user_testbed_path
            )
            testbed = yaml.safe_load(result)

            # Custom data should be preserved
            assert "custom" in testbed["testbed"]
            assert (
                testbed["testbed"]["custom"]["shared_vars"]["ntp_server"] == "10.1.1.1"
            )
            assert testbed["testbed"]["custom"]["test_config"]["timeout"] == 300

            # Topology should be preserved
            assert "topology" in testbed
            assert "router1" in testbed["topology"]
            assert "GigabitEthernet0/0" in testbed["topology"]["router1"]["interfaces"]

        finally:
            user_testbed_path.unlink()

    def test_preserve_device_custom_fields(self) -> None:
        """Test that device-level custom fields are preserved."""
        # User testbed with device custom fields
        user_testbed_yaml = """
testbed:
  name: device_custom_testbed

devices:
  router1:
    os: iosxe
    custom:
      rack_location: A-01
      owner: NetworkTeam
      maintenance_window: "Saturday 02:00-04:00"
    connections:
      cli:
        protocol: ssh
        ip: 10.1.1.1
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(user_testbed_yaml)
            user_testbed_path = Path(f.name)

        try:
            # Auto-discovered device (should be overridden)
            device = {
                "hostname": "router1",
                "host": "10.1.1.1",
                "os": "iosxe",
                "username": "admin",
                "password": "cisco123",
            }

            result = TestbedGenerator.generate_consolidated_testbed_yaml(
                [device], base_testbed_path=user_testbed_path
            )
            testbed = yaml.safe_load(result)

            # Device custom fields should be preserved
            assert "custom" in testbed["devices"]["router1"]
            assert testbed["devices"]["router1"]["custom"]["rack_location"] == "A-01"
            assert testbed["devices"]["router1"]["custom"]["owner"] == "NetworkTeam"

        finally:
            user_testbed_path.unlink()

    def test_single_device_testbed_with_base(self) -> None:
        """Test single device testbed generation with base testbed."""
        # User testbed
        user_testbed_yaml = """
testbed:
  name: single_device_testbed

devices:
  router1:
    os: iosxe
    connections:
      cli:
        command: python mock_unicon.py iosxe --hostname router1
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(user_testbed_yaml)
            user_testbed_path = Path(f.name)

        try:
            # Auto-discovered device
            device = {
                "hostname": "router1",
                "host": "10.1.1.1",
                "os": "iosxe",
                "username": "admin",
                "password": "cisco123",
            }

            result = TestbedGenerator.generate_testbed_yaml(
                device, base_testbed_path=user_testbed_path
            )
            testbed = yaml.safe_load(result)

            # User device should take precedence
            assert "command" in testbed["devices"]["router1"]["connections"]["cli"]
            assert "ip" not in testbed["devices"]["router1"]["connections"]["cli"]

        finally:
            user_testbed_path.unlink()

    def test_nonexistent_base_testbed(self) -> None:
        """Test that nonexistent base testbed path is handled gracefully."""
        device = {
            "hostname": "router1",
            "host": "10.1.1.1",
            "os": "iosxe",
            "username": "admin",
            "password": "cisco123",
        }

        # Should work fine with nonexistent path
        result = TestbedGenerator.generate_consolidated_testbed_yaml(
            [device], base_testbed_path=Path("/nonexistent/testbed.yaml")
        )
        testbed = yaml.safe_load(result)

        assert "router1" in testbed["devices"]
        assert testbed["devices"]["router1"]["connections"]["cli"]["ip"] == "10.1.1.1"
