# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Failure-mode integration tests for ConnectionBroker and BrokerClient.

These tests spin up a real ConnectionBroker with a real Unix socket but with
pyATS device connections mocked at the device.connect() boundary. This lets us
exercise the actual socket protocol, client/broker interaction, and error
handling paths that unit tests cannot reach.

Async methods are tested using asyncio.run() — same pattern as the rest of the
unit test suite (see test_subprocess_runner.py).

Note: This file is intended to live under tests/integration/ (see
tests/integration/test_broker.py for broader end-to-end broker validation).
"""

import asyncio
import socket as _socket
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from nac_test.pyats_core.broker.broker_client import BrokerClient
from nac_test.pyats_core.broker.connection_broker import ConnectionBroker


@pytest.fixture
def socket_dir() -> Any:
    """Short-path temp dir suitable for Unix socket paths (macOS 104-char limit)."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def good_device() -> MagicMock:
    """A device whose connect() succeeds."""
    device = MagicMock()
    device.connected = True
    device.spawn = True
    device.connect.return_value = None
    device.execute.return_value = "output"
    return device


@pytest.fixture
def bad_device() -> MagicMock:
    """A device whose connect() always fails."""
    device = MagicMock()
    device.connect.side_effect = ConnectionError(
        'failed to connect to bad-router\nFailed while bringing device to "any" state'
    )
    return device


@pytest.fixture
def make_broker(
    socket_dir: Path,
    tmp_path: Path,
) -> Callable[[dict[str, MagicMock]], ConnectionBroker]:
    """Factory fixture: call make_broker(devices) to get a wired ConnectionBroker."""

    def _factory(devices: dict[str, MagicMock]) -> ConnectionBroker:
        broker = ConnectionBroker(
            socket_path=socket_dir / "b.sock",
            output_dir=tmp_path,
        )
        broker.testbed = MagicMock()
        broker.testbed.devices = devices
        for hostname in devices:
            broker.connection_locks[hostname] = asyncio.Lock()
        return broker

    return _factory


def _patch_executor(loop: asyncio.AbstractEventLoop) -> Any:
    """Patch run_in_executor to call device methods synchronously in tests."""

    async def fake_executor(executor, func, *args):  # type: ignore[no-untyped-def]
        return func(*args)

    return patch.object(loop, "run_in_executor", side_effect=fake_executor)


class TestBrokerUnavailable:
    def test_ensure_connection_returns_false_when_broker_not_running(
        self,
        tmp_path: Path,
    ) -> None:
        """ensure_connection returns False (does not raise) when broker is unreachable."""
        client = BrokerClient(socket_path=tmp_path / "no_such.sock")

        result = asyncio.run(client.ensure_connection("router-1"))

        assert result is False

    def test_ensure_connection_returns_false_for_stale_socket_file(
        self,
        socket_dir: Any,
    ) -> None:
        """If a Unix socket file exists but no server is listening (stale socket),
        ensure_connection should fail gracefully and not hang."""
        stale_path = Path(socket_dir) / "stale.sock"
        with _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM) as s:
            s.bind(str(stale_path))
            s.listen(1)

        client = BrokerClient(socket_path=stale_path)
        result = asyncio.run(
            asyncio.wait_for(client.ensure_connection("router-1"), timeout=1.0)
        )
        assert result is False


class TestConnectFailure:
    def test_connect_command_returns_error_when_device_unreachable(
        self,
        make_broker: Any,
        bad_device: MagicMock,
    ) -> None:
        """When device.connect() fails the broker returns an error response with the
        actual exception message — not the generic 'Unknown broker error' fallback."""
        broker: ConnectionBroker = make_broker({"bad-router": bad_device})

        async def _run() -> dict[str, Any]:
            await broker._start_socket_server()
            try:
                loop = asyncio.get_event_loop()
                with patch(
                    "nac_test.pyats_core.broker.connection_broker.get_or_create_event_loop",
                    return_value=loop,
                ):
                    with _patch_executor(loop):
                        async with BrokerClient(
                            socket_path=broker.socket_path
                        ) as client:
                            try:
                                return await client._send_request(
                                    {"command": "connect", "hostname": "bad-router"}
                                )
                            except ConnectionError as e:
                                return {"status": "error", "error": str(e)}
            finally:
                assert broker.server is not None
                broker.server.close()
                await broker.server.wait_closed()

        result = asyncio.run(_run())
        assert result["status"] == "error"
        assert result.get("error", "") != "Unknown broker error"
        assert "bad-router" in result.get("error", "")


class TestSocketDeletedMidRun:
    def test_existing_client_still_works_after_socket_unlinked(
        self,
        make_broker: Any,
    ) -> None:
        broker: ConnectionBroker = make_broker({})

        async def _run() -> str:
            await broker._start_socket_server()
            loop = asyncio.get_event_loop()
            try:
                with patch(
                    "nac_test.pyats_core.broker.connection_broker.get_or_create_event_loop",
                    return_value=loop,
                ):
                    async with BrokerClient(socket_path=broker.socket_path) as client:
                        broker.socket_path.unlink()
                        result = await asyncio.wait_for(
                            client._send_request({"command": "ping"}), timeout=1.0
                        )
                        assert result == {"status": "success", "result": "pong"}
                        return str(result["result"])
            finally:
                assert broker.server is not None
                broker.server.close()
                await broker.server.wait_closed()

        assert asyncio.run(_run()) == "pong"

    def test_new_client_fails_after_socket_unlinked(
        self,
        make_broker: Any,
    ) -> None:
        broker: ConnectionBroker = make_broker({})

        async def _run() -> bool:
            await broker._start_socket_server()
            loop = asyncio.get_event_loop()
            try:
                with patch(
                    "nac_test.pyats_core.broker.connection_broker.get_or_create_event_loop",
                    return_value=loop,
                ):
                    async with BrokerClient(socket_path=broker.socket_path) as client:
                        await asyncio.wait_for(
                            client._send_request({"command": "ping"}), timeout=1.0
                        )
                        broker.socket_path.unlink()

                        new_client = BrokerClient(socket_path=broker.socket_path)
                        return await asyncio.wait_for(
                            new_client.ensure_connection("router-1"),
                            timeout=1.0,
                        )
            finally:
                assert broker.server is not None
                broker.server.close()
                await broker.server.wait_closed()

        assert asyncio.run(_run()) is False


class TestConnectionHealthCheckFailure:
    def test_reconnects_when_cached_connection_is_unhealthy(
        self,
        make_broker: Any,
        good_device: MagicMock,
    ) -> None:
        stale_device = MagicMock()
        stale_device.connected = False
        stale_device.spawn = False

        broker: ConnectionBroker = make_broker({"router-1": good_device})
        broker.connected_devices["router-1"] = stale_device

        async def _run() -> None:
            loop = asyncio.get_event_loop()
            with patch(
                "nac_test.pyats_core.broker.connection_broker.get_or_create_event_loop",
                return_value=loop,
            ):
                with _patch_executor(loop):
                    conn = await broker._get_connection("router-1")
                    assert conn is good_device

        asyncio.run(_run())


class TestConcurrentAccess:
    def test_concurrent_connect_requests_only_connect_once(
        self,
        make_broker: Any,
        good_device: MagicMock,
    ) -> None:
        broker: ConnectionBroker = make_broker({"router-1": good_device})

        async def _run() -> None:
            await broker._start_socket_server()
            try:
                loop = asyncio.get_event_loop()
                with patch(
                    "nac_test.pyats_core.broker.connection_broker.get_or_create_event_loop",
                    return_value=loop,
                ):
                    # Avoid threads; run the connect lambda synchronously
                    with _patch_executor(loop):
                        async with (
                            BrokerClient(socket_path=broker.socket_path) as c1,
                            BrokerClient(socket_path=broker.socket_path) as c2,
                        ):
                            results = await asyncio.gather(
                                c1.ensure_connection("router-1"),
                                c2.ensure_connection("router-1"),
                            )
                            assert results == [True, True]
            finally:
                assert broker.server is not None
                broker.server.close()
                await broker.server.wait_closed()

        asyncio.run(_run())

        # Both clients raced to connect; the broker should only call device.connect once.
        assert good_device.connect.call_count == 1


class TestDisconnectCleanup:
    def test_disconnect_cleans_up_even_when_device_disconnect_raises(
        self,
        make_broker: Any,
        good_device: MagicMock,
    ) -> None:
        """_disconnect_device_internal removes the device even if device.disconnect() raises."""
        broker: ConnectionBroker = make_broker({"router-1": good_device})
        broker.connected_devices["router-1"] = good_device
        good_device.disconnect.side_effect = Exception("device hung")

        async def _run() -> None:
            loop = asyncio.get_event_loop()
            with patch(
                "nac_test.pyats_core.broker.connection_broker.get_or_create_event_loop",
                return_value=loop,
            ):
                with _patch_executor(loop):
                    await broker._disconnect_device("router-1")

        asyncio.run(_run())

        assert "router-1" not in broker.connected_devices


class TestShutdownCleanup:
    def test_shutdown_disconnects_all_connected_devices(
        self,
        make_broker: Any,
        good_device: MagicMock,
    ) -> None:
        """shutdown() disconnects all devices and removes the socket file."""
        broker: ConnectionBroker = make_broker({"router-1": good_device})
        broker.connected_devices["router-1"] = good_device

        async def _run() -> None:
            await broker._start_socket_server()
            loop = asyncio.get_event_loop()
            with patch(
                "nac_test.pyats_core.broker.connection_broker.get_or_create_event_loop",
                return_value=loop,
            ):
                with _patch_executor(loop):
                    await broker.shutdown()

        asyncio.run(_run())

        assert broker.connected_devices == {}
        assert not broker.socket_path.exists()
