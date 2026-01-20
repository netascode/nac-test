# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for SSHTestBase device validation."""

import json
import os
import tempfile
from unittest.mock import Mock, patch

from nac_test.pyats_core.common.ssh_base_test import SSHTestBase


class TestSSHTestBaseValidation:
    """Test that SSHTestBase properly validates device info."""

    def test_validation_called_for_valid_device(self) -> None:
        """Test that validation is called and passes for valid device info."""
        # Create a valid device info dict
        valid_device = {
            "hostname": "test-router",
            "host": "192.168.1.1",
            "os": "iosxe",
            "username": "admin",
            "password": "secret123",
        }

        # Create a temporary test data file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"test": "data"}, f)
            temp_file = f.name

        try:
            # Setup environment
            os.environ["DEVICE_INFO"] = json.dumps(valid_device)
            os.environ["MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH"] = temp_file

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
        finally:
            # Clean up temp file
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_validation_fails_for_missing_fields(self) -> None:
        """Test that validation fails and reports missing fields."""
        # Create an invalid device info dict (missing username and password)
        invalid_device = {
            "hostname": "test-router",
            "host": "192.168.1.1",
            "os": "iosxe",
        }

        # Create a temporary test data file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"test": "data"}, f)
            temp_file = f.name

        try:
            # Setup environment
            os.environ["DEVICE_INFO"] = json.dumps(invalid_device)
            os.environ["MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH"] = temp_file

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
        finally:
            # Clean up temp file
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_validation_not_called_for_json_parse_error(self) -> None:
        """Test that validation is not called if JSON parsing fails."""
        # Create a temporary test data file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"test": "data"}, f)
            temp_file = f.name

        try:
            # Setup environment with invalid JSON
            os.environ["DEVICE_INFO"] = "not valid json"
            os.environ["MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH"] = temp_file

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
        finally:
            # Clean up temp file
            if os.path.exists(temp_file):
                os.unlink(temp_file)
