# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Shared fixtures for unit tests."""

import os
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch

from nac_test.pyats_core.constants import (
    PYATS_GRACEFUL_DISCONNECT_WAIT_SECONDS,
    PYATS_POST_DISCONNECT_WAIT_SECONDS,
)

CONTROLLER_ENV_PREFIXES = ("ACI_", "SDWAN_", "CC_", "MERAKI_", "FMC_", "ISE_")


def assert_connection_has_optimizations(connection: dict[str, Any]) -> None:
    """Verify connection includes expected optimization settings.

    This helper consolidates assertions for connection optimization settings,
    making it easier to maintain tests when new optimizations are added.

    Args:
        connection: The connection dict from testbed["devices"][hostname]["connections"]["cli"]
    """
    assert connection["arguments"]["init_config_commands"] == []
    assert connection["arguments"]["operating_mode"] is True
    assert (
        connection["settings"]["GRACEFUL_DISCONNECT_WAIT_SEC"]
        == PYATS_GRACEFUL_DISCONNECT_WAIT_SECONDS
    )
    assert (
        connection["settings"]["POST_DISCONNECT_WAIT_SEC"]
        == PYATS_POST_DISCONNECT_WAIT_SECONDS
    )


@pytest.fixture()
def clean_controller_env(monkeypatch: MonkeyPatch) -> None:
    """Clear all controller-related environment variables.

    Ensures tests run in isolation regardless of the caller's shell environment.
    """
    for key in list(os.environ.keys()):
        if any(prefix in key for prefix in CONTROLLER_ENV_PREFIXES):
            monkeypatch.delenv(key, raising=False)
