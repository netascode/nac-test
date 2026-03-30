# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Failure-mode integration tests for ConnectionBroker and BrokerClient.

These tests spin up a real ConnectionBroker with a real Unix socket but with
pyATS device connections mocked at the device.connect() boundary. This lets us
exercise the actual socket protocol, client/broker interaction, and error
handling paths that unit tests cannot reach.

Async methods are tested using asyncio.run() — same pattern as the rest of the
unit test suite (see test_subprocess_runner.py).
"""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from nac_test.pyats_core.broker.broker_client import BrokerClient
from nac_test.pyats_core.broker.connection_broker import ConnectionBroker


def _patch_executor(loop: asyncio.AbstractEventLoop) -> Any:
    """Patch run_in_executor to call device methods synchronously in tests."""

    async def fake_executor(executor, func, *args):  # type: ignore[no-untyped-def]
        return func(*args)

    return patch.object(loop, "run_in_executor", side_effect=fake_executor)


def test_ensure_connection_returns_false_when_broker_not_running(
    socket_dir: Path,
) -> None:
    """ensure_connection returns False (does not raise) when broker is unreachable."""
    client = BrokerClient(socket_path=socket_dir / "no_such.sock")

    result = asyncio.run(client.ensure_connection("router-1"))

    assert result is False


def test_connect_command_returns_error_when_device_unreachable(
    make_broker: Any, bad_device: MagicMock
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
                    async with BrokerClient(socket_path=broker.socket_path) as client:
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


def test_disconnect_cleans_up_even_when_device_disconnect_raises(
    make_broker: Any, good_device: MagicMock
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


def test_shutdown_disconnects_all_connected_devices(
    make_broker: Any, good_device: MagicMock
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
