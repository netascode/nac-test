# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for ConnectionBroker.

Async methods are tested using asyncio.run() since pytest-asyncio is not
installed in this project (see test_subprocess_runner.py for the same pattern).
"""

import asyncio
import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nac_test.pyats_core.broker.broker_client import BrokerClient, BrokerCommandExecutor
from nac_test.pyats_core.broker.connection_broker import ConnectionBroker


@pytest.fixture
def broker(tmp_path: Path) -> ConnectionBroker:
    """Return a ConnectionBroker with a pre-wired fake testbed (no real pyATS)."""
    b = ConnectionBroker(output_dir=tmp_path)
    b.testbed = MagicMock()
    b.testbed.devices = {"router-1": MagicMock(), "router-2": MagicMock()}
    for hostname in b.testbed.devices:
        b.connection_locks[hostname] = asyncio.Lock()
    return b


# ---------------------------------------------------------------------------
# _create_connection — error logging (#539)
# ---------------------------------------------------------------------------


def _run_failing_connect(
    broker: ConnectionBroker, hostname: str, exc: Exception
) -> None:
    """Drive _create_connection to failure via a mocked device.connect()."""

    async def _run() -> None:
        loop = asyncio.get_event_loop()
        assert broker.testbed is not None
        broker.testbed.devices[hostname].connect.side_effect = exc
        with patch(
            "nac_test.pyats_core.broker.connection_broker.get_or_create_event_loop",
            return_value=loop,
        ):
            await broker._create_connection(hostname)

    with pytest.raises(type(exc)):
        asyncio.run(_run())


def test_create_connection_logs_fixed_format_error(
    broker: ConnectionBroker, caplog: pytest.LogCaptureFixture
) -> None:
    """Error log uses fixed format: 'Failed to connect to {hostname}: {type}: {msg}'."""
    with caplog.at_level(logging.ERROR):
        _run_failing_connect(broker, "router-1", ConnectionError("timed out after 60s"))

    assert len(caplog.records) == 1
    assert "Failed to connect to router-1" in caplog.records[0].message
    assert "ConnectionError" in caplog.records[0].message
    assert "timed out after 60s" in caplog.records[0].message


def test_create_connection_omits_redundant_hostname(
    broker: ConnectionBroker, caplog: pytest.LogCaptureFixture
) -> None:
    """Hostname prefix is suppressed when pyATS already embeds it in the error."""
    with caplog.at_level(logging.ERROR):
        _run_failing_connect(
            broker, "router-1", ConnectionError("failed to connect to router-1")
        )

    assert len(caplog.records) == 1
    msg = caplog.records[0].message
    # The hostname prefix must NOT be prepended (pyATS already includes it)
    assert not msg.startswith("Failed to connect to router-1:")
    assert "ConnectionError" in msg
    assert "failed to connect to router-1" in msg


# ---------------------------------------------------------------------------
# _is_connection_healthy
# ---------------------------------------------------------------------------


class TestIsConnectionHealthy:
    def test_returns_false_when_attribute_raises(
        self, broker: ConnectionBroker
    ) -> None:
        """If pyATS connection attributes raise, treat as unhealthy (no crash)."""
        conn = MagicMock()
        type(conn).connected = property(
            lambda self: (_ for _ in ()).throw(Exception("boom"))
        )
        assert broker._is_connection_healthy(conn) is False

    def test_returns_false_when_attribute_missing(
        self, broker: ConnectionBroker
    ) -> None:
        """If a connection object lacks expected attributes, treat as unhealthy."""
        conn = object()
        assert broker._is_connection_healthy(conn) is False


# ---------------------------------------------------------------------------
# _process_request routing
# ---------------------------------------------------------------------------


class TestProcessRequest:
    def test_ping(self, broker: ConnectionBroker) -> None:
        result = asyncio.run(broker._process_request({"command": "ping"}))
        assert result == {"status": "success", "result": "pong"}

    def test_unknown_command(self, broker: ConnectionBroker) -> None:
        result = asyncio.run(broker._process_request({"command": "frobnicate"}))
        assert result["status"] == "error"
        assert "frobnicate" in result["error"]

    def test_connect_missing_hostname(self, broker: ConnectionBroker) -> None:
        result = asyncio.run(broker._process_request({"command": "connect"}))
        assert result["status"] == "error"
        assert "hostname" in result.get("error", "").lower()

    def test_execute_missing_params(self, broker: ConnectionBroker) -> None:
        result = asyncio.run(
            broker._process_request({"command": "execute", "hostname": "router-1"})
        )
        assert result["status"] == "error"
        assert "cmd" in result.get("error", "").lower()

    def test_connect_failure_propagates_error_message(
        self, broker: ConnectionBroker
    ) -> None:
        """Error message from _ensure_connection is surfaced in the response."""
        broker._ensure_connection = AsyncMock(  # type: ignore[method-assign]
            return_value=(False, "failed to connect to router-1")
        )
        result = asyncio.run(
            broker._process_request({"command": "connect", "hostname": "router-1"})
        )
        assert result["status"] == "error"
        assert "router-1" in result["error"]

    def test_execute_calls_execute_command(self, broker: ConnectionBroker) -> None:
        broker._execute_command = AsyncMock(return_value="show version output")  # type: ignore[method-assign]
        result = asyncio.run(
            broker._process_request(
                {"command": "execute", "hostname": "router-1", "cmd": "show version"}
            )
        )
        assert result == {"status": "success", "result": "show version output"}
        broker._execute_command.assert_called_once_with("router-1", "show version")


# ---------------------------------------------------------------------------
# _get_connection — cache hit/miss and stats
# ---------------------------------------------------------------------------


class TestGetConnection:
    def test_returns_existing_healthy_connection(
        self, broker: ConnectionBroker
    ) -> None:
        conn = MagicMock()
        broker.connected_devices["router-1"] = conn
        broker._is_connection_healthy = MagicMock(return_value=True)  # type: ignore[method-assign]

        result = asyncio.run(broker._get_connection("router-1"))

        assert result is conn
        assert broker.stats_connection_cache_hits == 1
        assert broker.stats_connection_cache_misses == 0

    def test_reconnects_when_unhealthy(self, broker: ConnectionBroker) -> None:
        stale_conn = MagicMock()
        fresh_conn = MagicMock()
        broker.connected_devices["router-1"] = stale_conn
        broker._is_connection_healthy = MagicMock(return_value=False)  # type: ignore[method-assign]
        broker._create_connection = AsyncMock(return_value=fresh_conn)  # type: ignore[method-assign]

        result = asyncio.run(broker._get_connection("router-1"))

        assert result is fresh_conn
        assert (
            "router-1" not in broker.connected_devices
            or broker.connected_devices["router-1"] is fresh_conn
        )

    def test_creates_new_connection_when_none_exists(
        self, broker: ConnectionBroker
    ) -> None:
        fresh_conn = MagicMock()
        broker._create_connection = AsyncMock(return_value=fresh_conn)  # type: ignore[method-assign]

        result = asyncio.run(broker._get_connection("router-1"))

        assert result is fresh_conn
        assert broker.stats_connection_cache_misses == 1


# ---------------------------------------------------------------------------
# _execute_command — command cache hit/miss
# ---------------------------------------------------------------------------


class TestExecuteCommand:
    def test_cache_hit_skips_device(self, broker: ConnectionBroker) -> None:
        cache = MagicMock()
        cache.get.return_value = "cached output"
        broker.command_cache["router-1"] = cache
        broker._get_connection = AsyncMock()  # type: ignore[method-assign]

        result = asyncio.run(broker._execute_command("router-1", "show version"))

        assert result == "cached output"
        broker._get_connection.assert_not_called()
        assert broker.stats_command_cache_hits == 1

    def test_cache_miss_executes_and_stores(self, broker: ConnectionBroker) -> None:
        cache = MagicMock()
        cache.get.return_value = None
        broker.command_cache["router-1"] = cache

        conn = MagicMock()
        broker._get_connection = AsyncMock(return_value=conn)  # type: ignore[method-assign]

        async def _run() -> str:
            loop = asyncio.get_event_loop()
            with patch(
                "nac_test.pyats_core.broker.connection_broker.get_or_create_event_loop",
                return_value=loop,
            ):
                with patch.object(
                    loop,
                    "run_in_executor",
                    new_callable=AsyncMock,
                    return_value="live output",
                ):
                    return await broker._execute_command("router-1", "show version")

        result = asyncio.run(_run())

        assert result == "live output"
        cache.set.assert_called_once_with("show version", "live output")
        assert broker.stats_command_cache_misses == 1

    def test_cache_miss_raises_when_connection_fails(
        self, broker: ConnectionBroker
    ) -> None:
        cache = MagicMock()
        cache.get.return_value = None
        broker.command_cache["router-1"] = cache
        broker._get_connection = AsyncMock(  # type: ignore[method-assign]
            side_effect=ConnectionError("No testbed loaded for router-1")
        )

        with pytest.raises(ConnectionError):
            asyncio.run(broker._execute_command("router-1", "show version"))


# ---------------------------------------------------------------------------
# BrokerCommandExecutor
# ---------------------------------------------------------------------------


class TestBrokerCommandExecutor:
    def test_connect_raises_when_ensure_connection_fails(self) -> None:
        client = MagicMock(spec=BrokerClient)
        client.ensure_connection = AsyncMock(return_value=False)
        executor = BrokerCommandExecutor("router-1", client)

        with pytest.raises(ConnectionError):
            asyncio.run(executor.connect())

    def test_connect_succeeds_when_ensure_connection_true(self) -> None:
        client = MagicMock(spec=BrokerClient)
        client.ensure_connection = AsyncMock(return_value=True)
        executor = BrokerCommandExecutor("router-1", client)

        asyncio.run(executor.connect())  # should not raise


# ---------------------------------------------------------------------------
# _create_connection — success path
# ---------------------------------------------------------------------------


def test_create_connection_stores_device_on_success(
    broker: ConnectionBroker, tmp_path: Path
) -> None:
    """Successful connect stores the device in connected_devices."""

    async def _run() -> None:
        loop = asyncio.get_event_loop()
        assert broker.testbed is not None
        broker.testbed.devices["router-1"].connect.return_value = None
        with patch(
            "nac_test.pyats_core.broker.connection_broker.get_or_create_event_loop",
            return_value=loop,
        ):
            await broker._create_connection("router-1")

    asyncio.run(_run())
    assert "router-1" in broker.connected_devices


# ---------------------------------------------------------------------------
# _execute_command — reconnect on failure
# ---------------------------------------------------------------------------


def test_execute_command_disconnects_on_execution_failure(
    broker: ConnectionBroker,
) -> None:
    """When command execution raises, the device is disconnected before re-raising."""
    cache = MagicMock()
    cache.get.return_value = None
    broker.command_cache["router-1"] = cache
    broker._get_connection = AsyncMock(return_value=MagicMock())  # type: ignore[method-assign]
    broker._disconnect_device = AsyncMock()  # type: ignore[method-assign]

    async def _run() -> None:
        loop = asyncio.get_event_loop()
        with patch(
            "nac_test.pyats_core.broker.connection_broker.get_or_create_event_loop",
            return_value=loop,
        ):
            with patch.object(
                loop,
                "run_in_executor",
                new_callable=AsyncMock,
                side_effect=Exception("timeout"),
            ):
                await broker._execute_command("router-1", "show version")

    with pytest.raises(Exception, match="timeout"):
        asyncio.run(_run())

    broker._disconnect_device.assert_called_once_with("router-1")


# ---------------------------------------------------------------------------
# _process_request — remaining paths
# ---------------------------------------------------------------------------


def test_process_request_status(broker: ConnectionBroker) -> None:
    """Status command returns broker status dict."""
    broker._get_broker_status = AsyncMock(return_value={"connected_devices": []})  # type: ignore[method-assign]
    result = asyncio.run(broker._process_request({"command": "status"}))
    assert result["status"] == "success"
    assert "connected_devices" in result["result"]


def test_process_request_exception_returns_error(broker: ConnectionBroker) -> None:
    """Unexpected exception in request handling returns error response, does not raise."""
    broker._ensure_connection = AsyncMock(side_effect=RuntimeError("unexpected"))  # type: ignore[method-assign]
    result = asyncio.run(
        broker._process_request({"command": "connect", "hostname": "router-1"})
    )
    assert result["status"] == "error"
    assert "unexpected" in result["error"]


# ---------------------------------------------------------------------------
# BrokerClient._get_socket_path
# ---------------------------------------------------------------------------


class TestBrokerClientGetSocketPath:
    def test_uses_env_var_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NAC_TEST_BROKER_SOCKET", "/tmp/my.sock")
        client = BrokerClient()
        assert client.socket_path == Path("/tmp/my.sock")

    def test_falls_back_to_glob(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("NAC_TEST_BROKER_SOCKET", raising=False)
        sock = tmp_path / "nac_test_broker_1234.sock"
        sock.touch()
        with patch("tempfile.gettempdir", return_value=str(tmp_path)):
            client = BrokerClient()
        assert client.socket_path == sock

    def test_raises_when_no_socket_found(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("NAC_TEST_BROKER_SOCKET", raising=False)
        with patch("tempfile.gettempdir", return_value=str(tmp_path)):
            with pytest.raises(ConnectionError, match="No broker socket found"):
                BrokerClient()


# ---------------------------------------------------------------------------
# BrokerClient — command passthroughs
# ---------------------------------------------------------------------------


class TestBrokerClientPassthroughs:
    """Verify that high-level methods send the correct command/params to _send_request."""

    def _make_client(self) -> tuple[BrokerClient, Any]:
        client = BrokerClient.__new__(BrokerClient)
        client._connected = True
        client._connection_lock = asyncio.Lock()
        mock = AsyncMock()
        client._send_request = mock  # type: ignore[method-assign]
        return client, mock

    def test_ping_returns_false_on_failure(self) -> None:
        client, mock = self._make_client()
        mock.side_effect = ConnectionError("gone")
        assert asyncio.run(client.ping()) is False


# ---------------------------------------------------------------------------
# Connection health recovery (relocated from integration tests — no socket involved)
# ---------------------------------------------------------------------------


class TestConnectionHealthRecovery:
    def test_reconnects_when_cached_connection_is_unhealthy(
        self, broker: ConnectionBroker
    ) -> None:
        """When a cached connection is unhealthy, _get_connection replaces it."""
        stale_device = MagicMock()
        stale_device.connected = False
        stale_device.spawn = False

        broker.connected_devices["router-1"] = stale_device

        async def _run() -> Any:
            loop = asyncio.get_event_loop()
            with patch(
                "nac_test.pyats_core.broker.connection_broker.get_or_create_event_loop",
                return_value=loop,
            ):

                async def fake_executor(executor: Any, func: Any, *args: Any) -> Any:
                    return func(*args)

                with patch.object(loop, "run_in_executor", side_effect=fake_executor):
                    return await broker._get_connection("router-1")

        result = asyncio.run(_run())
        assert broker.testbed is not None
        assert result is broker.testbed.devices["router-1"]


# ---------------------------------------------------------------------------
# Disconnect cleanup (relocated from integration tests — no socket involved)
# ---------------------------------------------------------------------------


class TestDisconnectCleanup:
    def test_disconnect_cleans_up_even_when_device_disconnect_raises(
        self, broker: ConnectionBroker
    ) -> None:
        """_disconnect_device removes the device even if device.disconnect() raises."""
        device = MagicMock()
        device.disconnect.side_effect = Exception("device hung")
        broker.connected_devices["router-1"] = device

        async def _run() -> None:
            loop = asyncio.get_event_loop()
            with patch(
                "nac_test.pyats_core.broker.connection_broker.get_or_create_event_loop",
                return_value=loop,
            ):

                async def fake_executor(executor: Any, func: Any, *args: Any) -> Any:
                    return func(*args)

                with patch.object(loop, "run_in_executor", side_effect=fake_executor):
                    await broker._disconnect_device("router-1")

        asyncio.run(_run())

        assert "router-1" not in broker.connected_devices
