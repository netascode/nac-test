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
from nac_test.pyats_core.constants import DEVICE_EXECUTE_TIMEOUT


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


class TestPatchDeviceExecuteForBroker:
    """Test _patch_device_execute_for_broker method."""

    def test_patches_testbed_device_execute(self, ssh_instance: Any) -> None:
        """After calling the method, testbed_device.execute is replaced with the broker_execute closure."""
        mock_device = Mock()
        original_execute = mock_device.execute
        ssh_instance.hostname = "router-1"

        with (
            patch.object(
                SSHTestBase,
                "testbed_device",
                new_callable=lambda: property(lambda self: mock_device),
            ),
            patch("nac_test.pyats_core.common.ssh_base_test.get_or_create_event_loop"),
        ):
            ssh_instance._patch_device_execute_for_broker()

        assert mock_device.execute is not original_execute
        assert callable(mock_device.execute)

    def test_patched_execute_calls_broker(self, ssh_instance: Any) -> None:
        """The patched execute calls broker_client.execute_command via run_coroutine_threadsafe."""
        mock_device = Mock()
        ssh_instance.hostname = "router-1"
        ssh_instance.broker_client.execute_command = AsyncMock(
            return_value="command output"
        )

        mock_future = Mock()
        mock_future.result = Mock(return_value="command output")

        with (
            patch.object(
                SSHTestBase,
                "testbed_device",
                new_callable=lambda: property(lambda self: mock_device),
            ),
            patch("nac_test.pyats_core.common.ssh_base_test.get_or_create_event_loop"),
            patch(
                "nac_test.pyats_core.common.ssh_base_test.asyncio.run_coroutine_threadsafe",
                return_value=mock_future,
            ) as mock_run_coro,
        ):
            ssh_instance._patch_device_execute_for_broker()
            result = mock_device.execute("show version")

        assert result == "command output"
        mock_run_coro.assert_called_once()
        mock_future.result.assert_called_once_with(timeout=DEVICE_EXECUTE_TIMEOUT)

    def test_asserts_without_testbed_device(self, ssh_instance: Any) -> None:
        """Raises AssertionError when testbed_device is None."""
        ssh_instance.hostname = "router-1"

        with (
            patch.object(
                SSHTestBase,
                "testbed_device",
                new_callable=lambda: property(lambda self: None),
            ),
            pytest.raises(AssertionError, match="testbed_device must be set"),
        ):
            ssh_instance._patch_device_execute_for_broker()

    def test_asserts_without_hostname(self, ssh_instance: Any) -> None:
        """Raises AssertionError when hostname is None."""
        mock_device = Mock()
        ssh_instance.hostname = None

        with (
            patch.object(
                SSHTestBase,
                "testbed_device",
                new_callable=lambda: property(lambda self: mock_device),
            ),
            pytest.raises(AssertionError, match="hostname must be set"),
        ):
            ssh_instance._patch_device_execute_for_broker()


class TestParseOutput:
    """Test parse_output method."""

    def test_returns_none_without_testbed_device(self, ssh_instance: Any) -> None:
        """When testbed_device is None/falsy, returns None immediately."""
        with patch.object(
            SSHTestBase,
            "testbed_device",
            new_callable=lambda: property(lambda self: None),
        ):
            result = asyncio.run(ssh_instance.parse_output("show version"))

        assert result is None

    def test_parses_with_output(self, ssh_instance: Any) -> None:
        """Calls testbed_device.parse(cmd, output=output) via executor, returns dict result."""
        mock_device = Mock()
        mock_loop = Mock()
        parsed_result = {"key": "value"}
        mock_loop.run_in_executor = AsyncMock(return_value=parsed_result)

        with (
            patch.object(
                SSHTestBase,
                "testbed_device",
                new_callable=lambda: property(lambda self: mock_device),
            ),
            patch(
                "nac_test.pyats_core.common.ssh_base_test.get_or_create_event_loop",
                return_value=mock_loop,
            ),
        ):
            result = asyncio.run(
                ssh_instance.parse_output("show version", output="raw output")
            )

        assert result == parsed_result
        mock_loop.run_in_executor.assert_called_once()
        # Verify the partial was called with output parameter
        call_args = mock_loop.run_in_executor.call_args
        assert call_args[0][0] is None  # executor=None

    def test_parses_without_output(self, ssh_instance: Any) -> None:
        """Calls testbed_device.parse(cmd) via executor, returns dict result."""
        mock_device = Mock()
        mock_loop = Mock()
        parsed_result = {"key": "value"}
        mock_loop.run_in_executor = AsyncMock(return_value=parsed_result)

        with (
            patch.object(
                SSHTestBase,
                "testbed_device",
                new_callable=lambda: property(lambda self: mock_device),
            ),
            patch(
                "nac_test.pyats_core.common.ssh_base_test.get_or_create_event_loop",
                return_value=mock_loop,
            ),
        ):
            result = asyncio.run(ssh_instance.parse_output("show version"))

        assert result == parsed_result
        mock_loop.run_in_executor.assert_called_once()

    def test_returns_none_on_exception(self, ssh_instance: Any) -> None:
        """When parse raises, logs warning and returns None."""
        mock_device = Mock()
        mock_loop = Mock()
        mock_loop.run_in_executor = AsyncMock(side_effect=Exception("Parser error"))

        with (
            patch.object(
                SSHTestBase,
                "testbed_device",
                new_callable=lambda: property(lambda self: mock_device),
            ),
            patch(
                "nac_test.pyats_core.common.ssh_base_test.get_or_create_event_loop",
                return_value=mock_loop,
            ),
        ):
            result = asyncio.run(ssh_instance.parse_output("show version"))

        assert result is None
        ssh_instance.logger.warning.assert_called_once()
        assert "Genie parser failed" in ssh_instance.logger.warning.call_args[0][0]

    def test_returns_none_when_parse_returns_none(self, ssh_instance: Any) -> None:
        """When parse() returns None, returns None."""
        mock_device = Mock()
        mock_loop = Mock()
        mock_loop.run_in_executor = AsyncMock(return_value=None)

        with (
            patch.object(
                SSHTestBase,
                "testbed_device",
                new_callable=lambda: property(lambda self: mock_device),
            ),
            patch(
                "nac_test.pyats_core.common.ssh_base_test.get_or_create_event_loop",
                return_value=mock_loop,
            ),
        ):
            result = asyncio.run(ssh_instance.parse_output("show version"))

        assert result is None
