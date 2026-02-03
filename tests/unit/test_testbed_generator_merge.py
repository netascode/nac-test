# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for TestbedGenerator with custom testbed merging."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from nac_test.pyats_core.execution.device.testbed_generator import TestbedGenerator


@pytest.fixture
def create_testbed_file(tmp_path: Path) -> Callable[[str], Path]:
    """Fixture that returns a function to create temporary testbed files.

    Args:
        tmp_path: pytest tmp_path fixture

    Returns:
        A function that takes YAML content and returns the path to the created file.
        Each call creates a unique file that is automatically cleaned up by pytest.
    """
    counter = 0

    def _create_file(yaml_content: str) -> Path:
        nonlocal counter
        counter += 1
        testbed_file = tmp_path / f"testbed_{counter}.yaml"
        testbed_file.write_text(yaml_content)
        return testbed_file

    return _create_file


@pytest.fixture
def sample_device() -> dict[str, Any]:
    """Fixture providing a sample device dictionary for tests."""
    return {
        "hostname": "router1",
        "host": "10.1.1.1",
        "os": "iosxe",
        "username": "admin",
        "password": "cisco123",
    }


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

    def test_generate_with_base_testbed_override(
        self, create_testbed_file: Callable[[str], Path]
    ) -> None:
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

        user_testbed_path = create_testbed_file(user_testbed_yaml)

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

    def test_generate_with_base_testbed_additional_devices(
        self, create_testbed_file: Callable[[str], Path]
    ) -> None:
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

        user_testbed_path = create_testbed_file(user_testbed_yaml)

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
        assert testbed["devices"]["router1"]["connections"]["cli"]["ip"] == "10.1.1.1"
        assert testbed["devices"]["router2"]["connections"]["cli"]["ip"] == "10.1.1.2"

    def test_preserve_pyats_env_variables(
        self, create_testbed_file: Callable[[str], Path]
    ) -> None:
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

        user_testbed_path = create_testbed_file(user_testbed_yaml)

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

    def test_preserve_pyats_custom_data(
        self, create_testbed_file: Callable[[str], Path]
    ) -> None:
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

        user_testbed_path = create_testbed_file(user_testbed_yaml)

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
        assert testbed["testbed"]["custom"]["shared_vars"]["ntp_server"] == "10.1.1.1"
        assert testbed["testbed"]["custom"]["test_config"]["timeout"] == 300

        # Topology should be preserved
        assert "topology" in testbed
        assert "router1" in testbed["topology"]
        assert "GigabitEthernet0/0" in testbed["topology"]["router1"]["interfaces"]

    def test_preserve_device_custom_fields(
        self, create_testbed_file: Callable[[str], Path]
    ) -> None:
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

        user_testbed_path = create_testbed_file(user_testbed_yaml)

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

    def test_single_device_testbed_with_base(
        self, create_testbed_file: Callable[[str], Path]
    ) -> None:
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

        user_testbed_path = create_testbed_file(user_testbed_yaml)

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


class TestTestbedErrorHandling:
    """Test error handling for user-provided testbed loading.

    These tests verify that invalid testbed YAML files are handled gracefully
    with user-friendly error messages, as specified in issue #480.
    """

    def test_malformed_yaml_syntax(
        self, create_testbed_file: Callable[[str], Path], sample_device: dict[str, Any]
    ) -> None:
        """Test that malformed YAML raises ValueError with helpful message."""
        # YAML with invalid syntax (missing colon after 'cli')
        malformed_yaml = """
testbed:
  name: broken
devices:
  router1:
    os: iosxe
    connections:
      cli
        invalid: structure
"""
        testbed_path = create_testbed_file(malformed_yaml)

        with pytest.raises(ValueError, match="Invalid YAML syntax"):
            TestbedGenerator.generate_consolidated_testbed_yaml(
                [sample_device], base_testbed_path=testbed_path
            )

    def test_malformed_yaml_syntax_single_device(
        self, create_testbed_file: Callable[[str], Path], sample_device: dict[str, Any]
    ) -> None:
        """Test that malformed YAML raises ValueError for single device method."""
        malformed_yaml = "key: [unclosed bracket"
        testbed_path = create_testbed_file(malformed_yaml)

        with pytest.raises(ValueError, match="Invalid YAML syntax"):
            TestbedGenerator.generate_testbed_yaml(
                sample_device, base_testbed_path=testbed_path
            )

    def test_empty_yaml_file(
        self, create_testbed_file: Callable[[str], Path], sample_device: dict[str, Any]
    ) -> None:
        """Test that empty YAML file raises ValueError."""
        testbed_path = create_testbed_file("")

        with pytest.raises(ValueError, match="is empty"):
            TestbedGenerator.generate_consolidated_testbed_yaml(
                [sample_device], base_testbed_path=testbed_path
            )

    def test_empty_yaml_file_single_device(
        self, create_testbed_file: Callable[[str], Path], sample_device: dict[str, Any]
    ) -> None:
        """Test that empty YAML file raises ValueError for single device method."""
        testbed_path = create_testbed_file("")

        with pytest.raises(ValueError, match="is empty"):
            TestbedGenerator.generate_testbed_yaml(
                sample_device, base_testbed_path=testbed_path
            )

    def test_yaml_with_only_comments(
        self, create_testbed_file: Callable[[str], Path], sample_device: dict[str, Any]
    ) -> None:
        """Test that YAML file with only comments is treated as empty."""
        comments_only_yaml = """
# This is a comment
# Another comment
"""
        testbed_path = create_testbed_file(comments_only_yaml)

        with pytest.raises(ValueError, match="is empty"):
            TestbedGenerator.generate_consolidated_testbed_yaml(
                [sample_device], base_testbed_path=testbed_path
            )

    def test_yaml_contains_list_instead_of_dict(
        self, create_testbed_file: Callable[[str], Path], sample_device: dict[str, Any]
    ) -> None:
        """Test that YAML containing a list raises ValueError."""
        list_yaml = """
- item1
- item2
- item3
"""
        testbed_path = create_testbed_file(list_yaml)

        with pytest.raises(ValueError, match="must contain a YAML mapping.*got list"):
            TestbedGenerator.generate_consolidated_testbed_yaml(
                [sample_device], base_testbed_path=testbed_path
            )

    def test_yaml_contains_string_instead_of_dict(
        self, create_testbed_file: Callable[[str], Path], sample_device: dict[str, Any]
    ) -> None:
        """Test that YAML containing a plain string raises ValueError."""
        string_yaml = "just a plain string"
        testbed_path = create_testbed_file(string_yaml)

        with pytest.raises(ValueError, match="must contain a YAML mapping.*got str"):
            TestbedGenerator.generate_consolidated_testbed_yaml(
                [sample_device], base_testbed_path=testbed_path
            )

    def test_yaml_contains_integer_instead_of_dict(
        self, create_testbed_file: Callable[[str], Path], sample_device: dict[str, Any]
    ) -> None:
        """Test that YAML containing just a number raises ValueError."""
        integer_yaml = "42"
        testbed_path = create_testbed_file(integer_yaml)

        with pytest.raises(ValueError, match="must contain a YAML mapping.*got int"):
            TestbedGenerator.generate_consolidated_testbed_yaml(
                [sample_device], base_testbed_path=testbed_path
            )

    def test_devices_key_is_string_instead_of_dict(
        self, create_testbed_file: Callable[[str], Path], sample_device: dict[str, Any]
    ) -> None:
        """Test that 'devices' as string raises ValueError."""
        invalid_devices_yaml = """
testbed:
  name: test_testbed
devices: "this should be a dict"
"""
        testbed_path = create_testbed_file(invalid_devices_yaml)

        with pytest.raises(ValueError, match="'devices'.*must be a mapping.*got str"):
            TestbedGenerator.generate_consolidated_testbed_yaml(
                [sample_device], base_testbed_path=testbed_path
            )

    def test_devices_key_is_list_instead_of_dict(
        self, create_testbed_file: Callable[[str], Path], sample_device: dict[str, Any]
    ) -> None:
        """Test that 'devices' as list raises ValueError."""
        invalid_devices_yaml = """
testbed:
  name: test_testbed
devices:
  - router1
  - router2
"""
        testbed_path = create_testbed_file(invalid_devices_yaml)

        with pytest.raises(ValueError, match="'devices'.*must be a mapping.*got list"):
            TestbedGenerator.generate_consolidated_testbed_yaml(
                [sample_device], base_testbed_path=testbed_path
            )

    def test_devices_key_is_integer_instead_of_dict(
        self, create_testbed_file: Callable[[str], Path], sample_device: dict[str, Any]
    ) -> None:
        """Test that 'devices' as integer raises ValueError."""
        invalid_devices_yaml = """
testbed:
  name: test_testbed
devices: 123
"""
        testbed_path = create_testbed_file(invalid_devices_yaml)

        with pytest.raises(ValueError, match="'devices'.*must be a mapping.*got int"):
            TestbedGenerator.generate_consolidated_testbed_yaml(
                [sample_device], base_testbed_path=testbed_path
            )

    def test_error_message_includes_file_path(
        self, create_testbed_file: Callable[[str], Path], sample_device: dict[str, Any]
    ) -> None:
        """Test that error messages include the file path for easier debugging."""
        testbed_path = create_testbed_file("")

        with pytest.raises(ValueError) as exc_info:
            TestbedGenerator.generate_consolidated_testbed_yaml(
                [sample_device], base_testbed_path=testbed_path
            )

        # Verify the file path is in the error message
        assert str(testbed_path) in str(exc_info.value)

    def test_load_user_testbed_guarantees_testbed_key(
        self, create_testbed_file: Callable[[str], Path]
    ) -> None:
        """Test that _load_user_testbed() creates 'testbed' key if missing."""
        # YAML without 'testbed' key
        yaml_without_testbed = """
devices:
  router1:
    os: iosxe
    connections:
      cli:
        protocol: ssh
        ip: 10.1.1.1
"""
        testbed_path = create_testbed_file(yaml_without_testbed)

        result = TestbedGenerator._load_user_testbed(testbed_path)

        assert "testbed" in result
        assert isinstance(result["testbed"], dict)
        assert "devices" in result
        assert "router1" in result["devices"]

    def test_load_user_testbed_guarantees_devices_key(
        self, create_testbed_file: Callable[[str], Path]
    ) -> None:
        """Test that _load_user_testbed() creates 'devices' key if missing."""
        # YAML without 'devices' key
        yaml_without_devices = """
testbed:
  name: my_testbed
  credentials:
    default:
      username: admin
      password: cisco123
"""
        testbed_path = create_testbed_file(yaml_without_devices)

        result = TestbedGenerator._load_user_testbed(testbed_path)

        assert "devices" in result
        assert isinstance(result["devices"], dict)
        assert "testbed" in result
        assert result["testbed"]["name"] == "my_testbed"

    def test_load_user_testbed_guarantees_both_keys_minimal_yaml(
        self, create_testbed_file: Callable[[str], Path]
    ) -> None:
        """Test that _load_user_testbed() creates both keys from minimal YAML."""
        # Minimal valid YAML - just an empty dict effectively
        minimal_yaml = """
custom_key: some_value
"""
        testbed_path = create_testbed_file(minimal_yaml)

        result = TestbedGenerator._load_user_testbed(testbed_path)

        assert "testbed" in result
        assert isinstance(result["testbed"], dict)
        assert "devices" in result
        assert isinstance(result["devices"], dict)
        # Original content should be preserved
        assert result["custom_key"] == "some_value"
