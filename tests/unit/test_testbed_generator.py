# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for PyATS testbed generator."""

from typing import Any

import pytest
import yaml

from nac_test.pyats_core.execution.device.testbed_generator import TestbedGenerator


def assert_connection_has_optimizations(connection: dict[str, Any]) -> None:
    """Verify connection includes expected optimization settings.

    This helper consolidates assertions for connection optimization settings,
    making it easier to maintain tests when new optimizations are added.

    Args:
        connection: The connection dict from testbed["devices"][hostname]["connections"]["cli"]
    """
    assert connection["arguments"]["init_config_commands"] == []
    assert connection["arguments"]["operating_mode"] is True
    assert connection["settings"]["POST_DISCONNECT_WAIT_SEC"] == 0


class TestGenerateTestbedYaml:
    """Test cases for generate_testbed_yaml method."""

    def test_basic_device(self) -> None:
        """Test basic device with only required fields."""
        device = {
            "hostname": "test-router",
            "host": "10.1.1.1",
            "os": "iosxe",
            "username": "admin",
            "password": "secret",
        }

        yaml_output = TestbedGenerator.generate_testbed_yaml(device)
        testbed = yaml.safe_load(yaml_output)

        assert testbed["testbed"]["name"] == "testbed_test-router"
        assert testbed["testbed"]["credentials"]["default"]["username"] == "admin"
        assert testbed["testbed"]["credentials"]["default"]["password"] == "secret"

        device_config = testbed["devices"]["test-router"]
        assert device_config["os"] == "iosxe"
        assert device_config["type"] == "router"  # default
        assert device_config["alias"] == "test-router"  # default to hostname
        assert device_config["connections"]["cli"]["protocol"] == "ssh"
        assert device_config["connections"]["cli"]["ip"] == "10.1.1.1"
        assert device_config["connections"]["cli"]["port"] == 22

    def test_connection_arguments(self) -> None:
        """Test that connection arguments include init_config_commands and operating_mode."""
        device = {
            "hostname": "test-device",
            "host": "10.1.1.1",
            "os": "iosxe",
            "username": "admin",
            "password": "secret",
        }

        yaml_output = TestbedGenerator.generate_testbed_yaml(device)
        testbed = yaml.safe_load(yaml_output)

        connection = testbed["devices"]["test-device"]["connections"]["cli"]
        assert "arguments" in connection
        assert_connection_has_optimizations(connection)

    def test_custom_abstraction(self) -> None:
        """Test that custom.abstraction.order is set correctly."""
        device = {
            "hostname": "test-device",
            "host": "10.1.1.1",
            "os": "iosxe",
            "username": "admin",
            "password": "secret",
        }

        yaml_output = TestbedGenerator.generate_testbed_yaml(device)
        testbed = yaml.safe_load(yaml_output)

        device_config = testbed["devices"]["test-device"]
        assert "custom" in device_config
        assert "abstraction" in device_config["custom"]
        assert device_config["custom"]["abstraction"]["order"] == ["os"]

    def test_no_custom_platform_list(self) -> None:
        """Test that custom.platform is NOT created."""
        device = {
            "hostname": "test-device",
            "host": "10.1.1.1",
            "os": "iosxe",
            "platform": "sdwan",
            "model": "c8000v",
            "username": "admin",
            "password": "secret",
        }

        yaml_output = TestbedGenerator.generate_testbed_yaml(device)
        testbed = yaml.safe_load(yaml_output)

        device_config = testbed["devices"]["test-device"]
        assert "platform" not in device_config["custom"]

    def test_platform_field(self) -> None:
        """Test that platform field is included when provided."""
        device = {
            "hostname": "test-device",
            "host": "10.1.1.1",
            "os": "iosxe",
            "platform": "sdwan",
            "username": "admin",
            "password": "secret",
        }

        yaml_output = TestbedGenerator.generate_testbed_yaml(device)
        testbed = yaml.safe_load(yaml_output)

        device_config = testbed["devices"]["test-device"]
        assert device_config["platform"] == "sdwan"

    def test_platform_not_included_when_absent(self) -> None:
        """Test that platform field is NOT included when not provided (no default)."""
        device = {
            "hostname": "test-device",
            "host": "10.1.1.1",
            "os": "iosxe",
            "username": "admin",
            "password": "secret",
        }

        yaml_output = TestbedGenerator.generate_testbed_yaml(device)
        testbed = yaml.safe_load(yaml_output)

        device_config = testbed["devices"]["test-device"]
        assert "platform" not in device_config

    def test_model_field_requires_platform(self) -> None:
        """Test that model is only included when platform is also present."""
        # Model without platform - model should not be included
        device_no_platform = {
            "hostname": "test-device1",
            "host": "10.1.1.1",
            "os": "iosxe",
            "model": "c8000v",
            "username": "admin",
            "password": "secret",
        }

        yaml_output = TestbedGenerator.generate_testbed_yaml(device_no_platform)
        testbed = yaml.safe_load(yaml_output)
        assert "model" not in testbed["devices"]["test-device1"]

        # Model with platform - both should be included
        device_with_platform = {
            "hostname": "test-device2",
            "host": "10.1.1.2",
            "os": "iosxe",
            "platform": "sdwan",
            "model": "c8000v",
            "username": "admin",
            "password": "secret",
        }

        yaml_output = TestbedGenerator.generate_testbed_yaml(device_with_platform)
        testbed = yaml.safe_load(yaml_output)
        device_config = testbed["devices"]["test-device2"]
        assert device_config["platform"] == "sdwan"
        assert device_config["model"] == "c8000v"

    def test_series_field_independent(self) -> None:
        """Test that series field is independent of platform and model."""
        # Series without platform or model
        device_series_only = {
            "hostname": "test-device1",
            "host": "10.1.1.1",
            "os": "iosxe",
            "series": "catalyst",
            "username": "admin",
            "password": "secret",
        }

        yaml_output = TestbedGenerator.generate_testbed_yaml(device_series_only)
        testbed = yaml.safe_load(yaml_output)
        device_config = testbed["devices"]["test-device1"]
        assert device_config["series"] == "catalyst"
        assert "platform" not in device_config
        assert "model" not in device_config

        # Series with platform and model
        device_all = {
            "hostname": "test-device2",
            "host": "10.1.1.2",
            "os": "iosxe",
            "platform": "cat9k",
            "model": "c9300",
            "series": "catalyst",
            "username": "admin",
            "password": "secret",
        }

        yaml_output = TestbedGenerator.generate_testbed_yaml(device_all)
        testbed = yaml.safe_load(yaml_output)
        device_config = testbed["devices"]["test-device2"]
        assert device_config["platform"] == "cat9k"
        assert device_config["model"] == "c9300"
        assert device_config["series"] == "catalyst"

    def test_series_not_included_when_absent(self) -> None:
        """Test that series field is NOT included when not provided."""
        device = {
            "hostname": "test-device",
            "host": "10.1.1.1",
            "os": "iosxe",
            "username": "admin",
            "password": "secret",
        }

        yaml_output = TestbedGenerator.generate_testbed_yaml(device)
        testbed = yaml.safe_load(yaml_output)

        device_config = testbed["devices"]["test-device"]
        assert "series" not in device_config

    def test_optional_fields(self) -> None:
        """Test device with all optional fields."""
        device = {
            "hostname": "my-router",
            "host": "192.168.1.1",
            "os": "nxos",
            "platform": "n9k",
            "model": "n9000",
            "series": "nexus",
            "type": "switch",
            "alias": "core-switch-1",
            "port": 2222,
            "username": "cisco",
            "password": "cisco123",
        }

        yaml_output = TestbedGenerator.generate_testbed_yaml(device)
        testbed = yaml.safe_load(yaml_output)

        device_config = testbed["devices"]["my-router"]
        assert device_config["alias"] == "core-switch-1"
        assert device_config["os"] == "nxos"
        assert device_config["type"] == "switch"
        assert device_config["platform"] == "n9k"
        assert device_config["model"] == "n9000"
        assert device_config["series"] == "nexus"
        assert device_config["connections"]["cli"]["port"] == 2222

    def test_connection_options_override(self) -> None:
        """Test that connection_options can override protocol and port."""
        device = {
            "hostname": "test-device",
            "host": "10.1.1.1",
            "os": "iosxe",
            "username": "admin",
            "password": "secret",
            "connection_options": {"protocol": "telnet", "port": 23},
        }

        yaml_output = TestbedGenerator.generate_testbed_yaml(device)
        testbed = yaml.safe_load(yaml_output)

        connection = testbed["devices"]["test-device"]["connections"]["cli"]
        assert connection["protocol"] == "telnet"
        assert connection["port"] == 23
        assert_connection_has_optimizations(connection)

    def test_ssh_options(self) -> None:
        """Test that ssh_options are included when provided."""
        device = {
            "hostname": "test-device",
            "host": "10.1.1.1",
            "os": "iosxe",
            "username": "admin",
            "password": "secret",
            "ssh_options": "-o StrictHostKeyChecking=no",
        }

        yaml_output = TestbedGenerator.generate_testbed_yaml(device)
        testbed = yaml.safe_load(yaml_output)

        connection = testbed["devices"]["test-device"]["connections"]["cli"]
        assert connection["ssh_options"] == "-o StrictHostKeyChecking=no"

    def test_mock_device_with_command(self) -> None:
        """Test mock device with command parameter."""
        device = {
            "hostname": "mock-device",
            "os": "iosxe",
            "username": "admin",
            "password": "secret",
            "command": "/path/to/mock_script.py --hostname mock-device iosxe",
        }

        yaml_output = TestbedGenerator.generate_testbed_yaml(device)
        testbed = yaml.safe_load(yaml_output)

        connection = testbed["devices"]["mock-device"]["connections"]["cli"]
        assert "command" in connection
        assert (
            connection["command"]
            == "/path/to/mock_script.py --hostname mock-device iosxe"
        )
        assert "ip" not in connection
        assert_connection_has_optimizations(connection)


class TestGenerateConsolidatedTestbedYaml:
    """Test cases for generate_consolidated_testbed_yaml method."""

    def test_multiple_devices(self) -> None:
        """Test consolidated testbed with multiple devices."""
        devices = [
            {
                "hostname": "router1",
                "host": "10.1.1.1",
                "os": "iosxe",
                "username": "admin",
                "password": "secret",
            },
            {
                "hostname": "router2",
                "host": "10.1.1.2",
                "os": "nxos",
                "username": "admin",
                "password": "secret",
            },
        ]

        yaml_output = TestbedGenerator.generate_consolidated_testbed_yaml(devices)
        testbed = yaml.safe_load(yaml_output)

        assert testbed["testbed"]["name"] == "nac_test_consolidated_testbed"
        assert len(testbed["devices"]) == 2
        assert "router1" in testbed["devices"]
        assert "router2" in testbed["devices"]

    def test_empty_devices_list(self) -> None:
        """Test that empty devices list raises ValueError."""
        with pytest.raises(ValueError, match="At least one device is required"):
            TestbedGenerator.generate_consolidated_testbed_yaml([])

    def test_devices_have_connection_optimizations(self) -> None:
        """Test that all devices in consolidated testbed have connection optimizations."""
        devices = [
            {
                "hostname": "router1",
                "host": "10.1.1.1",
                "os": "iosxe",
                "username": "admin",
                "password": "secret",
            },
            {
                "hostname": "router2",
                "host": "10.1.1.2",
                "os": "nxos",
                "username": "admin",
                "password": "secret",
            },
        ]

        yaml_output = TestbedGenerator.generate_consolidated_testbed_yaml(devices)
        testbed = yaml.safe_load(yaml_output)

        for hostname in ["router1", "router2"]:
            device_config = testbed["devices"][hostname]
            connection = device_config["connections"]["cli"]
            assert_connection_has_optimizations(connection)
            assert device_config["custom"]["abstraction"]["order"] == ["os"]

    def test_devices_with_mixed_optional_fields(self) -> None:
        """Test consolidated testbed with devices having different optional fields."""
        devices = [
            {
                "hostname": "sdwan-router",
                "host": "10.1.1.1",
                "os": "iosxe",
                "platform": "sdwan",
                "model": "c8000v",
                "username": "admin",
                "password": "secret",
            },
            {
                "hostname": "cat-switch",
                "host": "10.1.1.2",
                "os": "iosxe",
                "platform": "cat9k",
                "series": "catalyst",
                "username": "admin",
                "password": "secret",
            },
            {
                "hostname": "basic-router",
                "host": "10.1.1.3",
                "os": "iosxe",
                "username": "admin",
                "password": "secret",
            },
        ]

        yaml_output = TestbedGenerator.generate_consolidated_testbed_yaml(devices)
        testbed = yaml.safe_load(yaml_output)

        # Check SDWAN router
        sdwan = testbed["devices"]["sdwan-router"]
        assert sdwan["platform"] == "sdwan"
        assert sdwan["model"] == "c8000v"
        assert "series" not in sdwan

        # Check Catalyst switch
        cat = testbed["devices"]["cat-switch"]
        assert cat["platform"] == "cat9k"
        assert "model" not in cat  # No model without platform being present first
        assert cat["series"] == "catalyst"

        # Check basic router
        basic = testbed["devices"]["basic-router"]
        assert "platform" not in basic
        assert "model" not in basic
        assert "series" not in basic

    def test_default_credentials_from_first_device(self) -> None:
        """Test that testbed-level default credentials come from first device."""
        devices = [
            {
                "hostname": "router1",
                "host": "10.1.1.1",
                "os": "iosxe",
                "username": "first",
                "password": "firstpass",
            },
            {
                "hostname": "router2",
                "host": "10.1.1.2",
                "os": "iosxe",
                "username": "second",
                "password": "secondpass",
            },
        ]

        yaml_output = TestbedGenerator.generate_consolidated_testbed_yaml(devices)
        testbed = yaml.safe_load(yaml_output)

        # Testbed-level credentials should be from first device
        assert testbed["testbed"]["credentials"]["default"]["username"] == "first"
        assert testbed["testbed"]["credentials"]["default"]["password"] == "firstpass"

        # But each device should have its own credentials
        assert (
            testbed["devices"]["router1"]["credentials"]["default"]["username"]
            == "first"
        )
        assert (
            testbed["devices"]["router2"]["credentials"]["default"]["username"]
            == "second"
        )


class TestBuildDeviceConfig:
    """Test cases for _build_device_config helper method."""

    def test_build_device_config_basic(self) -> None:
        """Test _build_device_config with basic device."""
        device = {
            "hostname": "test-device",
            "host": "10.1.1.1",
            "os": "iosxe",
            "username": "admin",
            "password": "secret",
        }

        config = TestbedGenerator._build_device_config(device)

        assert config["alias"] == "test-device"
        assert config["os"] == "iosxe"
        assert config["type"] == "router"
        assert config["connections"]["cli"]["protocol"] == "ssh"
        assert config["custom"]["abstraction"]["order"] == ["os"]

    def test_build_device_config_all_optional_fields(self) -> None:
        """Test _build_device_config with all optional fields."""
        device = {
            "hostname": "test-device",
            "host": "10.1.1.1",
            "os": "iosxe",
            "platform": "sdwan",
            "model": "c8000v",
            "series": "catalyst",
            "type": "switch",
            "alias": "my-device",
            "username": "admin",
            "password": "secret",
        }

        config = TestbedGenerator._build_device_config(device)

        assert config["alias"] == "my-device"
        assert config["type"] == "switch"
        assert config["platform"] == "sdwan"
        assert config["model"] == "c8000v"
        assert config["series"] == "catalyst"
