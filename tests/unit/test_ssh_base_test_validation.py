# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for SSHTestBase device validation."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from nac_test.pyats_core.common.ssh_base_test import SSHTestBase


@pytest.fixture()
def temp_data_model_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Create a temporary data model file and set the environment variable.

    Uses tmp_path for automatic cleanup and monkeypatch for env var management.
    """
    data_model_path = tmp_path / "test_data.json"
    data_model_path.write_text(json.dumps({"test": "data"}))
    monkeypatch.setenv(
        "MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH", str(data_model_path)
    )
    return data_model_path


class TestSSHTestBaseValidation:
    """Test that SSHTestBase properly validates device info."""

    def test_validation_called_for_valid_device(
        self,
        iosxe_controller_env: None,
        temp_data_model_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that validation is called and passes for valid device info."""
        # Create a valid device info dict
        valid_device = {
            "hostname": "test-router",
            "host": "192.168.1.1",
            "os": "iosxe",
            "username": "admin",
            "password": "secret123",
        }

        # Setup environment with device info
        monkeypatch.setenv("DEVICE_INFO", json.dumps(valid_device))

        # Create test instance
        test_instance = SSHTestBase()
        # The parent attribute is set in PyATS, we need to mock it properly
        mock_parent = Mock()
        mock_parent.name = "test_parent"
        test_instance.parent = mock_parent
        test_instance.logger = Mock()
        test_instance.failed = Mock()

        # Mock the parent setup and async setup to avoid actual connection attempts
        with (
            patch("nac_test.pyats_core.common.base_test.NACTestBase.setup"),
            patch.object(test_instance, "_async_setup"),
        ):
            # Run setup
            test_instance.setup()

        # Verify failed was not called (validation passed)
        test_instance.failed.assert_not_called()

        # Verify device_info was set correctly
        assert test_instance.device_info == valid_device

    def test_validation_fails_for_missing_fields(
        self,
        iosxe_controller_env: None,
        temp_data_model_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that validation fails and reports missing fields."""
        # Create an invalid device info dict (missing username and password)
        invalid_device = {
            "hostname": "test-router",
            "host": "192.168.1.1",
            "os": "iosxe",
        }

        # Setup environment with device info
        monkeypatch.setenv("DEVICE_INFO", json.dumps(invalid_device))

        # Create test instance
        test_instance = SSHTestBase()
        # The parent attribute is set in PyATS, we need to mock it properly
        mock_parent = Mock()
        mock_parent.name = "test_parent"
        test_instance.parent = mock_parent
        test_instance.logger = Mock()
        test_instance.failed = Mock()

        # Mock the parent setup to avoid controller URL lookup
        with patch("nac_test.pyats_core.common.base_test.NACTestBase.setup"):
            # Run setup
            test_instance.setup()

            # Verify failed was called with appropriate error message
            test_instance.failed.assert_called_once()
            error_msg = test_instance.failed.call_args[0][0]

            # Check that the error message contains expected information
            assert "Framework Error: Device validation failed" in error_msg
            assert "Missing required fields: ['password', 'username']" in error_msg
            assert "Device validation failed: 'test-router'" in error_msg
            assert (
                "This indicates a bug in the device resolver implementation"
                in error_msg
            )

    def test_validation_not_called_for_json_parse_error(
        self,
        iosxe_controller_env: None,
        temp_data_model_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that validation is not called if JSON parsing fails."""
        # Setup environment with invalid JSON
        monkeypatch.setenv("DEVICE_INFO", "not valid json")

        # Create test instance
        test_instance = SSHTestBase()
        # The parent attribute is set in PyATS, we need to mock it properly
        mock_parent = Mock()
        mock_parent.name = "test_parent"
        test_instance.parent = mock_parent
        test_instance.logger = Mock()
        test_instance.failed = Mock()

        # Patch validate_device_inventory to track if it's called and mock parent setup
        with (
            patch(
                "nac_test.pyats_core.common.ssh_base_test.validate_device_inventory"
            ) as mock_validate,
            patch("nac_test.pyats_core.common.base_test.NACTestBase.setup"),
        ):
            # Run setup
            test_instance.setup()

            # Verify validation was NOT called (failed at JSON parsing)
            mock_validate.assert_not_called()

            # Verify failed was called for JSON parse error
            test_instance.failed.assert_called_once()
            error_msg = test_instance.failed.call_args[0][0]
            assert "Could not parse device info JSON" in error_msg
