# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for TestbedGenerator with custom testbed merging."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from nac_test.pyats_core.execution.device.testbed_generator import TestbedGenerator

from .conftest import assert_connection_has_optimizations


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
        assert_connection_has_optimizations(
            testbed["devices"]["router1"]["connections"]["cli"]
        )
        assert_connection_has_optimizations(
            testbed["devices"]["router2"]["connections"]["cli"]
        )

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
        assert_connection_has_optimizations(
            testbed["devices"]["router1"]["connections"]["cli"]
        )


class TestTestbedErrorHandling:
    """Test error handling for user-provided testbed loading.

    These tests verify that invalid testbed YAML files are handled gracefully
    with user-friendly error messages, as specified in issue #480.
    """

    YAML_WITH_DEVICES = """
devices:
  router1:
    os: iosxe
    connections:
      cli:
        protocol: ssh
        ip: 10.1.1.1
"""

    YAML_WITH_TESTBED = """
testbed:
  name: my_testbed
  credentials:
    default:
      username: admin
      password: cisco123
"""

    YAML_MINIMAL = """
custom_key: some_value
"""

    @pytest.mark.parametrize(
        "yaml_content,method",
        [
            (
                "testbed:\n  name: broken\ndevices:\n  router1:\n    os: iosxe\n"
                "    connections:\n      cli\n        invalid: structure\n",
                "consolidated",
            ),
            (
                "key: [unclosed bracket",
                "consolidated",
            ),
            (
                "key: [unclosed bracket",
                "single",
            ),
        ],
        ids=[
            "malformed-missing-colon-consolidated",
            "malformed-unclosed-bracket-consolidated",
            "malformed-unclosed-bracket-single",
        ],
    )
    def test_malformed_yaml_syntax(
        self,
        create_testbed_file: Callable[[str], Path],
        sample_device: dict[str, Any],
        yaml_content: str,
        method: str,
    ) -> None:
        """Test that malformed YAML raises ValueError with helpful message."""
        testbed_path = create_testbed_file(yaml_content)

        with pytest.raises(ValueError, match="Invalid YAML syntax"):
            if method == "consolidated":
                TestbedGenerator.generate_consolidated_testbed_yaml(
                    [sample_device], base_testbed_path=testbed_path
                )
            else:
                TestbedGenerator.generate_testbed_yaml(
                    sample_device, base_testbed_path=testbed_path
                )

    @pytest.mark.parametrize(
        "yaml_content,method",
        [
            ("", "consolidated"),
            ("", "single"),
            (
                "# This is a comment\n# Another comment\n",
                "consolidated",
            ),
        ],
        ids=[
            "empty-file-consolidated",
            "empty-file-single",
            "comments-only",
        ],
    )
    def test_empty_yaml_content(
        self,
        create_testbed_file: Callable[[str], Path],
        sample_device: dict[str, Any],
        yaml_content: str,
        method: str,
    ) -> None:
        """Test that empty YAML content raises ValueError."""
        testbed_path = create_testbed_file(yaml_content)

        with pytest.raises(ValueError, match="is empty"):
            if method == "consolidated":
                TestbedGenerator.generate_consolidated_testbed_yaml(
                    [sample_device], base_testbed_path=testbed_path
                )
            else:
                TestbedGenerator.generate_testbed_yaml(
                    sample_device, base_testbed_path=testbed_path
                )

    @pytest.mark.parametrize(
        "yaml_content,expected_type",
        [
            ("- item1\n- item2\n- item3\n", "list"),
            ("just a plain string", "str"),
            ("42", "int"),
        ],
        ids=["list", "string", "integer"],
    )
    def test_invalid_yaml_root_type(
        self,
        create_testbed_file: Callable[[str], Path],
        sample_device: dict[str, Any],
        yaml_content: str,
        expected_type: str,
    ) -> None:
        """Test that YAML with invalid root type raises ValueError."""
        testbed_path = create_testbed_file(yaml_content)

        with pytest.raises(
            ValueError, match=f"must contain a YAML mapping.*got {expected_type}"
        ):
            TestbedGenerator.generate_consolidated_testbed_yaml(
                [sample_device], base_testbed_path=testbed_path
            )

    @pytest.mark.parametrize(
        "yaml_content,expected_type",
        [
            (
                'testbed:\n  name: test_testbed\ndevices: "this should be a dict"\n',
                "str",
            ),
            (
                "testbed:\n  name: test_testbed\ndevices:\n  - router1\n  - router2\n",
                "list",
            ),
            (
                "testbed:\n  name: test_testbed\ndevices: 123\n",
                "int",
            ),
        ],
        ids=["string", "list", "integer"],
    )
    def test_invalid_devices_key_type(
        self,
        create_testbed_file: Callable[[str], Path],
        sample_device: dict[str, Any],
        yaml_content: str,
        expected_type: str,
    ) -> None:
        """Test that 'devices' key with invalid type raises ValueError."""
        testbed_path = create_testbed_file(yaml_content)

        with pytest.raises(
            ValueError, match=f"'devices'.*must be a mapping.*got {expected_type}"
        ):
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

    @pytest.mark.parametrize(
        "yaml_content,check_testbed_key,check_devices_key,extra_assertions",
        [
            (
                YAML_WITH_DEVICES,
                True,
                False,
                {"devices": {"router1": dict}},
            ),
            (
                YAML_WITH_TESTBED,
                False,
                True,
                {"testbed": {"name": "my_testbed"}},
            ),
            (
                YAML_MINIMAL,
                True,
                True,
                {"custom_key": "some_value"},
            ),
        ],
        ids=[
            "missing-testbed-key",
            "missing-devices-key",
            "missing-both-keys",
        ],
    )
    def test_load_user_testbed_guarantees_keys(
        self,
        create_testbed_file: Callable[[str], Path],
        yaml_content: str,
        check_testbed_key: bool,
        check_devices_key: bool,
        extra_assertions: dict[str, Any],
    ) -> None:
        """Test that _load_user_testbed() guarantees 'testbed' and 'devices' keys."""
        testbed_path = create_testbed_file(yaml_content)

        result = TestbedGenerator._load_user_testbed(testbed_path)

        # Always verify both keys exist
        assert "testbed" in result
        assert isinstance(result["testbed"], dict)
        assert "devices" in result
        assert isinstance(result["devices"], dict)

        # Verify extra assertions based on test case
        for key, expected in extra_assertions.items():
            if isinstance(expected, dict):
                for subkey, subval in expected.items():
                    if subval is dict:
                        assert subkey in result[key]
                    else:
                        assert result[key][subkey] == subval
            else:
                assert result[key] == expected

    def test_unicode_decode_error(
        self, tmp_path: Path, sample_device: dict[str, Any]
    ) -> None:
        """Test that non-UTF-8 files raise ValueError with encoding message."""
        testbed_file = tmp_path / "invalid_encoding.yaml"
        testbed_file.write_bytes(b"testbed:\n  name: \xff\xfe invalid utf-8\n")

        with pytest.raises(ValueError, match="invalid UTF-8 encoding"):
            TestbedGenerator.generate_consolidated_testbed_yaml(
                [sample_device], base_testbed_path=testbed_file
            )
