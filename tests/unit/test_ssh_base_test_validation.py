# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for SSHTestBase device validation and broker socket handling."""

import asyncio
import json
import socket as _socket
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from nac_test.pyats_core.common.ssh_base_test import SSHTestBase


@pytest.fixture()
def temp_data_model_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Create a temporary data model file and set the environment variable."""
    data_model_path = tmp_path / "test_data.json"
    data_model_path.write_text(json.dumps({"test": "data"}))
    monkeypatch.setenv(
        "MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH", str(data_model_path)
    )
    return data_model_path


class TestSSHTestBaseValidation:
    """Test that SSHTestBase properly validates device info."""

    def _make_instance(self) -> SSHTestBase:
        instance = SSHTestBase()
        instance.logger = Mock()
        instance.failed = Mock()
        return instance

    def test_validation_called_for_valid_device(
        self,
        iosxe_controller_env: None,
        temp_data_model_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Validation passes for a fully-populated device info dict."""
        valid_device = {
            "hostname": "test-router",
            "host": "192.168.1.1",
            "os": "iosxe",
            "username": "admin",
            "password": "secret123",
        }
        monkeypatch.setenv("DEVICE_INFO", json.dumps(valid_device))
        instance = self._make_instance()

        mock_parent = Mock()
        mock_parent.broker_client = Mock()

        with (
            patch("nac_test.pyats_core.common.base_test.NACTestBase.setup"),
            patch.object(SSHTestBase, "parent", mock_parent, create=True),
            patch.object(instance, "_async_setup", new_callable=AsyncMock),
        ):
            instance.setup()

        instance.failed.assert_not_called()
        assert instance.device_info == valid_device

    def test_validation_fails_for_missing_fields(
        self,
        iosxe_controller_env: None,
        temp_data_model_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Validation fails with a clear message when required fields are absent."""
        invalid_device = {
            "hostname": "test-router",
            "host": "192.168.1.1",
            "os": "iosxe",
        }
        monkeypatch.setenv("DEVICE_INFO", json.dumps(invalid_device))
        instance = self._make_instance()

        with patch("nac_test.pyats_core.common.base_test.NACTestBase.setup"):
            instance.setup()

        instance.failed.assert_called_once()
        error_msg = instance.failed.call_args[0][0]
        assert "Framework Error: Device validation failed" in error_msg
        assert "Missing required fields: ['password', 'username']" in error_msg
        assert "Device validation failed: 'test-router'" in error_msg
        assert "This indicates a bug in the device resolver implementation" in error_msg

    def test_validation_not_called_for_json_parse_error(
        self,
        iosxe_controller_env: None,
        temp_data_model_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Validation is skipped when JSON parsing fails."""
        monkeypatch.setenv("DEVICE_INFO", "not valid json")
        instance = self._make_instance()

        with (
            patch(
                "nac_test.pyats_core.common.ssh_base_test.validate_device_inventory"
            ) as mock_validate,
            patch("nac_test.pyats_core.common.base_test.NACTestBase.setup"),
        ):
            instance.setup()

        mock_validate.assert_not_called()
        instance.failed.assert_called_once()
        assert "Could not parse device info JSON" in instance.failed.call_args[0][0]


class TestAsyncSetupBrokerSocketValidation:
    def test_uses_broker_when_socket_exists(
        self, monkeypatch: pytest.MonkeyPatch, socket_dir: Path, ssh_instance: Any
    ) -> None:
        """When NAC_TEST_BROKER_SOCKET points to a valid Unix socket, broker path is taken."""
        sock = socket_dir / "broker.sock"
        with _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM) as s:
            s.bind(str(sock))
        monkeypatch.setenv("NAC_TEST_BROKER_SOCKET", str(sock))

        mock_executor = Mock()
        mock_executor.connect = AsyncMock()

        with (
            patch.object(
                SSHTestBase,
                "testbed_device",
                new_callable=lambda: property(lambda self: None),
            ),
            patch(
                "nac_test.pyats_core.common.ssh_base_test.BrokerCommandExecutor",
                return_value=mock_executor,
            ),
            patch("nac_test.pyats_core.common.ssh_base_test.CommandCache"),
            patch.object(
                ssh_instance, "_create_execute_command_method", return_value=Mock()
            ),
        ):
            ssh_instance.device_info = {"hostname": "router-1"}
            asyncio.run(ssh_instance._async_setup("router-1"))

        ssh_instance.broker_client.connect.assert_called_once()
        mock_executor.connect.assert_called_once()
        ssh_instance.logger.warning.assert_not_called()

    @pytest.mark.parametrize(
        ("path_factory", "description"),
        [
            (lambda p: p / "no_such.sock", "non-existent path"),
            (
                lambda p: (p / "regular_file.sock").touch() or p / "regular_file.sock",
                "regular file",
            ),
            (lambda p: (p / "a_dir").mkdir() or p / "a_dir", "directory"),
        ],
        ids=["missing", "regular-file", "directory"],
    )
    def test_falls_back_for_non_socket_paths(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        ssh_instance: Any,
        path_factory: Any,
        description: str,
    ) -> None:
        """Fallback and warning are triggered whenever NAC_TEST_BROKER_SOCKET does not
        point to a valid Unix socket (missing path, regular file, or directory)."""
        bad_path = path_factory(tmp_path)
        monkeypatch.setenv("NAC_TEST_BROKER_SOCKET", str(bad_path))

        mock_testbed_device = Mock()
        mock_loop = Mock()
        mock_loop.run_in_executor = AsyncMock(return_value=None)

        with (
            patch.object(
                SSHTestBase,
                "testbed_device",
                new_callable=lambda: property(lambda self: mock_testbed_device),
            ),
            patch(
                "nac_test.pyats_core.common.ssh_base_test.get_or_create_event_loop",
                return_value=mock_loop,
            ),
            patch("nac_test.pyats_core.common.ssh_base_test.CommandCache"),
            patch.object(
                ssh_instance, "_create_execute_command_method", return_value=Mock()
            ),
        ):
            ssh_instance.device_info = {"hostname": "router-1"}
            asyncio.run(ssh_instance._async_setup("router-1"))

        ssh_instance.logger.warning.assert_called_once()
        assert "falling back" in ssh_instance.logger.warning.call_args[0][0]
        ssh_instance.broker_client.connect.assert_not_called()
        assert ssh_instance.connection is mock_testbed_device

    def test_raises_when_socket_missing_and_no_testbed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, ssh_instance: Any
    ) -> None:
        """When socket is absent and no testbed device is available, ConnectionError
        is raised."""
        monkeypatch.setenv("NAC_TEST_BROKER_SOCKET", str(tmp_path / "no_such.sock"))

        with patch.object(
            SSHTestBase,
            "testbed_device",
            new_callable=lambda: property(lambda self: None),
        ):
            with pytest.raises(ConnectionError):
                asyncio.run(ssh_instance._async_setup("router-1"))
