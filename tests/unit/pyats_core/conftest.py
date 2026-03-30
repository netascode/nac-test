# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Shared fixtures for pyats_core broker tests."""

import asyncio
import tempfile
from collections.abc import Callable, Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nac_test.pyats_core.broker.connection_broker import ConnectionBroker


@pytest.fixture
def socket_dir() -> Generator[Path, None, None]:
    """Short-path temp dir suitable for Unix socket paths (macOS 104-char limit)."""
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
    socket_dir: Path, tmp_path: Path
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
